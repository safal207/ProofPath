#!/usr/bin/env python3
"""OpenAI-compatible Gonka execution adapter for ProofPath Compute Witness.

The adapter is intentionally dependency-free and conservative:

- credentials are read only from environment variables;
- HTTPS is required except for localhost development endpoints;
- identical requests can be executed multiple times;
- primary failures may use an explicitly configured fallback;
- local receipts contain hashes and execution metadata, not API keys or prompts;
- the receipt does not claim GPU identity, on-chain settlement, or zkML proof.
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import json
import os
import re
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Protocol

SHA256_PREFIX = "sha256:"
WHITESPACE_RE = re.compile(r"\s+")


class Transport(Protocol):
    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> tuple[int, dict[str, Any], dict[str, str]]:
        """POST JSON and return status, decoded body, and selected headers."""


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    api_key: str
    model: str


@dataclass(frozen=True)
class GonkaConfig:
    primary: ProviderConfig
    replicas: int = 3
    timeout_seconds: float = 30.0
    agreement_threshold: float = 0.85
    fallback: ProviderConfig | None = None

    @classmethod
    def from_env(cls) -> "GonkaConfig":
        base_url = _required_env("GONKA_BASE_URL")
        api_key = _required_env("GONKA_API_KEY")
        model = _required_env("GONKA_MODEL")

        fallback_url = os.getenv("GONKA_FALLBACK_BASE_URL", "").strip()
        fallback_key = os.getenv("GONKA_FALLBACK_API_KEY", "").strip()
        fallback_model = os.getenv("GONKA_FALLBACK_MODEL", "").strip()
        fallback: ProviderConfig | None = None
        if any((fallback_url, fallback_key, fallback_model)):
            if not all((fallback_url, fallback_key, fallback_model)):
                raise ValueError(
                    "fallback requires GONKA_FALLBACK_BASE_URL, "
                    "GONKA_FALLBACK_API_KEY, and GONKA_FALLBACK_MODEL"
                )
            fallback = ProviderConfig(
                name="fallback",
                base_url=fallback_url,
                api_key=fallback_key,
                model=fallback_model,
            )

        replicas = _env_int("GONKA_REPLICAS", 3, minimum=1, maximum=10)
        timeout_seconds = _env_float(
            "GONKA_TIMEOUT_SECONDS", 30.0, minimum=0.1, maximum=300.0
        )
        agreement_threshold = _env_float(
            "GONKA_AGREEMENT_THRESHOLD", 0.85, minimum=0.0, maximum=1.0
        )
        return cls(
            primary=ProviderConfig(
                name="gonka",
                base_url=base_url,
                api_key=api_key,
                model=model,
            ),
            replicas=replicas,
            timeout_seconds=timeout_seconds,
            agreement_threshold=agreement_threshold,
            fallback=fallback,
        )


class UrllibTransport:
    """Small stdlib transport with bounded reads and explicit TLS defaults."""

    def __init__(self, max_response_bytes: int = 2_000_000) -> None:
        self.max_response_bytes = max_response_bytes

    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> tuple[int, dict[str, Any], dict[str, str]]:
        body = canonical_json_bytes(payload)
        request = urllib.request.Request(
            url=url,
            data=body,
            headers=headers,
            method="POST",
        )
        context = ssl.create_default_context()
        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout_seconds,
                context=context,
            ) as response:
                raw = response.read(self.max_response_bytes + 1)
                if len(raw) > self.max_response_bytes:
                    raise RuntimeError("provider response exceeded maximum size")
                decoded = _decode_json_object(raw, url)
                selected_headers = _selected_response_headers(response.headers)
                return int(response.status), decoded, selected_headers
        except urllib.error.HTTPError as exc:
            raw = exc.read(self.max_response_bytes + 1)
            body_obj: dict[str, Any]
            if len(raw) > self.max_response_bytes:
                body_obj = {"error": "provider response exceeded maximum size"}
            else:
                try:
                    body_obj = _decode_json_object(raw, url)
                except RuntimeError:
                    body_obj = {"error": raw.decode("utf-8", errors="replace")[:1000]}
            return int(exc.code), body_obj, _selected_response_headers(exc.headers)
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            raise RuntimeError(f"provider request failed: {type(exc).__name__}") from exc


class GonkaComputeWitnessAdapter:
    def __init__(
        self,
        config: GonkaConfig,
        transport: Transport | None = None,
        now: Callable[[], dt.datetime] | None = None,
        uuid_factory: Callable[[], uuid.UUID] | None = None,
    ) -> None:
        self.config = config
        self.transport = transport or UrllibTransport()
        self.now = now or (lambda: dt.datetime.now(dt.timezone.utc))
        self.uuid_factory = uuid_factory or uuid.uuid4

        _validate_provider(config.primary)
        if config.fallback is not None:
            _validate_provider(config.fallback)
        if config.replicas < 1 or config.replicas > 10:
            raise ValueError("replicas must be between 1 and 10")
        if not 0.0 <= config.agreement_threshold <= 1.0:
            raise ValueError("agreement_threshold must be between 0 and 1")

    def run(
        self,
        claim_id: str,
        prompt: str,
        *,
        replicas: int | None = None,
        system_prompt: str = "Return a concise, evidence-aware answer.",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        claim_id = claim_id.strip()
        prompt = prompt.strip()
        system_prompt = system_prompt.strip()
        if not claim_id:
            raise ValueError("claim_id is required")
        if not prompt:
            raise ValueError("prompt is required")
        if not system_prompt:
            raise ValueError("system_prompt is required")

        replica_count = replicas if replicas is not None else self.config.replicas
        if replica_count < 1 or replica_count > 10:
            raise ValueError("replicas must be between 1 and 10")

        semantic_request = {
            "profile": "proofpath.gonka.request.v0.1",
            "claim_id": claim_id,
            "model": self.config.primary.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
        request_hash = sha256_canonical_json(semantic_request)
        prompt_hash = sha256_text(prompt)
        run_id = f"gonka-run-{self.uuid_factory().hex}"
        started_at = _format_time(self.now())

        outputs: list[dict[str, Any]] = []
        executions: list[dict[str, Any]] = []

        for index in range(replica_count):
            execution_id = f"{run_id}-r{index + 1}"
            result = self._execute_replica(
                execution_id=execution_id,
                semantic_request=semantic_request,
            )
            executions.append(result["receipt"])
            if result["content"] is not None:
                outputs.append(
                    {
                        "execution_id": execution_id,
                        "provider": result["receipt"]["provider"],
                        "model": result["receipt"]["model"],
                        "content": result["content"],
                    }
                )

        agreement_score = compute_agreement_score(
            [item["content"] for item in outputs]
        )
        success_count = len(outputs)
        verdict = _derive_verdict(
            success_count=success_count,
            requested=replica_count,
            agreement_score=agreement_score,
            agreement_threshold=self.config.agreement_threshold,
        )
        completed_at = _format_time(self.now())

        receipt_core = {
            "profile": "proofpath.gonka.compute-receipt.v0.1",
            "run_id": run_id,
            "claim_id": claim_id,
            "request_hash": request_hash,
            "prompt_hash": prompt_hash,
            "requested_replicas": replica_count,
            "successful_replicas": success_count,
            "agreement_score": agreement_score,
            "agreement_threshold": self.config.agreement_threshold,
            "verdict": verdict,
            "started_at": started_at,
            "completed_at": completed_at,
            "metadata": metadata or {},
            "executions": executions,
            "proof_level": "provider-response-hash-v0.1",
            "limitations": [
                "Does not prove GPU hardware identity.",
                "Does not prove on-chain settlement or validator consensus.",
                "Does not prove model execution correctness.",
                "Independence depends on broker and routing configuration.",
            ],
        }
        receipt = {
            **receipt_core,
            "receipt_hash": sha256_canonical_json(receipt_core),
        }
        return {"outputs": outputs, "receipt": receipt}

    def _execute_replica(
        self,
        *,
        execution_id: str,
        semantic_request: dict[str, Any],
    ) -> dict[str, Any]:
        primary_result = self._call_provider(
            provider=self.config.primary,
            execution_id=execution_id,
            semantic_request=semantic_request,
            fallback_used=False,
        )
        if primary_result["content"] is not None:
            return primary_result
        if self.config.fallback is None:
            return primary_result

        fallback_result = self._call_provider(
            provider=self.config.fallback,
            execution_id=execution_id,
            semantic_request=semantic_request,
            fallback_used=True,
        )
        fallback_result["receipt"]["primary_error"] = primary_result["receipt"].get(
            "error"
        )
        return fallback_result

    def _call_provider(
        self,
        *,
        provider: ProviderConfig,
        execution_id: str,
        semantic_request: dict[str, Any],
        fallback_used: bool,
    ) -> dict[str, Any]:
        endpoint = _chat_completions_endpoint(provider.base_url)
        payload = {
            "model": provider.model,
            "messages": semantic_request["messages"],
            "temperature": semantic_request["temperature"],
        }
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "ProofPath-Gonka-Compute-Witness/0.1",
        }
        started_at = _format_time(self.now())
        try:
            status, body, response_headers = self.transport.post_json(
                endpoint,
                headers,
                payload,
                self.config.timeout_seconds,
            )
            completed_at = _format_time(self.now())
            if status < 200 or status >= 300:
                return {
                    "content": None,
                    "receipt": _execution_receipt(
                        execution_id=execution_id,
                        provider=provider,
                        status="ERROR",
                        started_at=started_at,
                        completed_at=completed_at,
                        http_status=status,
                        response_headers=response_headers,
                        fallback_used=fallback_used,
                        error=f"provider returned HTTP {status}",
                    ),
                }
            content = _extract_content(body)
            response_hash = sha256_canonical_json(body)
            output_hash = sha256_text(content)
            return {
                "content": content,
                "receipt": _execution_receipt(
                    execution_id=execution_id,
                    provider=provider,
                    status="SUCCESS",
                    started_at=started_at,
                    completed_at=completed_at,
                    http_status=status,
                    response_headers=response_headers,
                    fallback_used=fallback_used,
                    response_hash=response_hash,
                    output_hash=output_hash,
                    provider_request_id=_provider_request_id(body, response_headers),
                ),
            }
        except (RuntimeError, ValueError) as exc:
            completed_at = _format_time(self.now())
            return {
                "content": None,
                "receipt": _execution_receipt(
                    execution_id=execution_id,
                    provider=provider,
                    status="ERROR",
                    started_at=started_at,
                    completed_at=completed_at,
                    fallback_used=fallback_used,
                    error=str(exc),
                ),
            }


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_canonical_json(value: Any) -> str:
    return SHA256_PREFIX + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_text(value: str) -> str:
    return SHA256_PREFIX + hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_output(value: str) -> str:
    return WHITESPACE_RE.sub(" ", value.strip().lower())


def compute_agreement_score(outputs: list[str]) -> float:
    normalized = [normalize_output(item) for item in outputs if item.strip()]
    if not normalized:
        return 0.0
    if len(normalized) == 1:
        return 1.0

    scores: list[float] = []
    for left_index, left in enumerate(normalized):
        for right in normalized[left_index + 1 :]:
            scores.append(difflib.SequenceMatcher(a=left, b=right).ratio())
    return round(sum(scores) / len(scores), 6)


def _execution_receipt(
    *,
    execution_id: str,
    provider: ProviderConfig,
    status: str,
    started_at: str,
    completed_at: str,
    fallback_used: bool,
    http_status: int | None = None,
    response_headers: dict[str, str] | None = None,
    response_hash: str | None = None,
    output_hash: str | None = None,
    provider_request_id: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "execution_id": execution_id,
        "provider": provider.name,
        "model": provider.model,
        "endpoint_origin": _origin(provider.base_url),
        "status": status,
        "started_at": started_at,
        "completed_at": completed_at,
        "http_status": http_status,
        "fallback_used": fallback_used,
        "provider_request_id": provider_request_id,
        "response_hash": response_hash,
        "output_hash": output_hash,
        "response_headers": response_headers or {},
        "error": error,
    }


def _derive_verdict(
    *,
    success_count: int,
    requested: int,
    agreement_score: float,
    agreement_threshold: float,
) -> str:
    if success_count == 0:
        return "NO_SUCCESSFUL_EXECUTION"
    if success_count < requested:
        return "DEGRADED"
    if agreement_score >= agreement_threshold:
        return "CONSENSUS"
    return "DIVERGENT"


def _extract_content(body: dict[str, Any]) -> str:
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("provider response has no choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise ValueError("provider response choice must be an object")

    message = first.get("message")
    content: Any = None
    if isinstance(message, dict):
        content = message.get("content")
    if content is None:
        content = first.get("text")
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                text_parts.append(item["text"])
        content = "".join(text_parts)
    if not isinstance(content, str) or not content.strip():
        raise ValueError("provider response has no text content")
    return content.strip()


def _provider_request_id(
    body: dict[str, Any], response_headers: dict[str, str]
) -> str | None:
    body_id = body.get("id")
    if isinstance(body_id, str) and body_id.strip():
        return body_id
    for key in ("x-request-id", "request-id"):
        value = response_headers.get(key)
        if value:
            return value
    return None


def _chat_completions_endpoint(base_url: str) -> str:
    parsed = urllib.parse.urlparse(base_url.rstrip("/"))
    path = parsed.path.rstrip("/")
    if path.endswith("/chat/completions"):
        final_path = path
    elif path.endswith("/v1"):
        final_path = path + "/chat/completions"
    else:
        final_path = path + "/v1/chat/completions"
    return urllib.parse.urlunparse(
        (parsed.scheme, parsed.netloc, final_path, "", "", "")
    )


def _origin(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _validate_provider(provider: ProviderConfig) -> None:
    if not provider.name.strip():
        raise ValueError("provider name is required")
    if not provider.api_key.strip():
        raise ValueError(f"{provider.name} API key is required")
    if not provider.model.strip():
        raise ValueError(f"{provider.name} model is required")

    parsed = urllib.parse.urlparse(provider.base_url)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise ValueError(f"{provider.name} base URL must be an absolute HTTP(S) URL")
    hostname = (parsed.hostname or "").lower()
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and hostname not in local_hosts:
        raise ValueError(
            f"{provider.name} base URL must use HTTPS except for localhost"
        )
    if parsed.username or parsed.password:
        raise ValueError(f"{provider.name} base URL must not contain credentials")


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    value = default if raw is None else int(raw)
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    raw = os.getenv(name)
    value = default if raw is None else float(raw)
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _decode_json_object(raw: bytes, url: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"provider returned invalid JSON from {_origin(url)}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"provider returned non-object JSON from {_origin(url)}")
    return value


def _selected_response_headers(headers: Any) -> dict[str, str]:
    selected: dict[str, str] = {}
    if headers is None:
        return selected
    for key in ("x-request-id", "request-id", "date", "server"):
        value = headers.get(key)
        if value:
            selected[key] = str(value)
    return selected


def _format_time(value: dt.datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _read_prompt(args: argparse.Namespace) -> str:
    if args.prompt is not None:
        return args.prompt
    if args.prompt_file is not None:
        return args.prompt_file.read_text(encoding="utf-8")
    raise ValueError("provide --prompt or --prompt-file")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run an OpenAI-compatible Gonka Compute Witness pilot"
    )
    parser.add_argument("--claim-id", required=True)
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt")
    prompt_group.add_argument(
        "--prompt-file", type=lambda value: __import__("pathlib").Path(value)
    )
    parser.add_argument("--replicas", type=int)
    parser.add_argument(
        "--include-outputs",
        action="store_true",
        help="Include raw model outputs in stdout. Receipts never contain them.",
    )
    args = parser.parse_args()

    try:
        adapter = GonkaComputeWitnessAdapter(GonkaConfig.from_env())
        result = adapter.run(
            claim_id=args.claim_id,
            prompt=_read_prompt(args),
            replicas=args.replicas,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 2

    printable = result if args.include_outputs else {"receipt": result["receipt"]}
    print(json.dumps(printable, indent=2, ensure_ascii=False))
    return 0 if result["receipt"]["successful_replicas"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

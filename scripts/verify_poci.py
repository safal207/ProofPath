#!/usr/bin/env python3
"""Dependency-free offline verifier for ProofPath PoCI v0.1."""
from __future__ import annotations

import argparse, copy, hashlib, hmac, json, re, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PROFILE = "proofpath.poci.v0.1"
SCHEMA = "0.1.0"
CANON = "proofpath.poci.canonical-json.v0.1"
DOMAIN = b"proofpath:poci:v0.1:envelope\n"
RANK = {"ACCEPT": 0, "HOLD": 1, "BLOCK": 2, "CHALLENGE": 3}
EXIT = {"ACCEPT": 0, "HOLD": 2, "BLOCK": 3, "CHALLENGE": 4}
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
TOP = {"protocol","envelope_id","created_at","intent","authority","causal_context","proposal","execution","observed_result","witnesses","verification","evidence_integrity","extensions"}
REQUIRED = TOP - {"extensions"}
PRIORITY = {
 "POCI_PROFILE_UNSUPPORTED":10,"AUTHORITY_MISSING":20,"POCI_REQUIRED_EVIDENCE_MISSING":30,"POCI_SCHEMA_INVALID":40,
 "INTENT_EXPIRED":100,"INTENT_REPLAYED":110,"AUTHORITY_SCOPE_VIOLATION":130,"IRREVERSIBLE_APPROVAL_MISSING":150,
 "CAUSAL_PARENT_MISMATCH":200,"CAUSAL_PARENT_MISSING":210,"PROPOSAL_EXECUTION_MISMATCH":300,
 "EXECUTION_RECEIPT_MISSING":310,"EXECUTION_RECEIPT_DIGEST_MISMATCH":320,"OBSERVED_RESULT_MISSING":330,"RESULT_DIGEST_MISMATCH":340,
 "WITNESS_CONFLICT":400,"WITNESS_EQUIVOCATION":410,"WITNESS_QUORUM_UNMET":420,"ENVELOPE_ROOT_MISMATCH":430,
 "ARTIFACT_DIGEST_MISMATCH":440,"VERIFIER_INTERNAL_FAIL_CLOSED":999,
}

class DuplicateKeyError(ValueError): pass

def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out: raise DuplicateKeyError(f"duplicate JSON key: {key}")
        out[key] = value
    return out

def load_json(path: Path) -> dict[str, Any]:
    try: value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)
    except (OSError, json.JSONDecodeError, DuplicateKeyError) as exc: raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict): raise ValueError(f"expected JSON object in {path}")
    return value

def timestamp(value):
    if not isinstance(value, str) or not STAMP.fullmatch(value): return None
    try: return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError: return None

def _floats(value):
    if isinstance(value, float): return True
    if isinstance(value, dict): return any(_floats(v) for v in value.values())
    if isinstance(value, list): return any(_floats(v) for v in value)
    return False

def canonical_json_bytes(value):
    if _floats(value): raise ValueError("floating-point values are forbidden")
    return json.dumps(value, sort_keys=True, separators=(",",":"), ensure_ascii=False, allow_nan=False).encode()

def compute_envelope_root(envelope):
    normalized = copy.deepcopy(envelope)
    normalized.setdefault("evidence_integrity", {})["envelope_root"] = None
    return "sha256:" + hashlib.sha256(DOMAIN + canonical_json_bytes(normalized)).hexdigest()

def normalized_json_bytes(value): return canonical_json_bytes(value) + b"\n"
def _dict(value): return value if isinstance(value, dict) else {}
def _list(value): return value if isinstance(value, list) else []
def _finding(code, decision, path, message): return {"code":code,"decision":decision,"path":path,"message":message}

def _add(items, seen, code, decision, path, message):
    if (code,path) not in seen:
        items.append(_finding(code,decision,path,message)); seen.add((code,path))

def _structure(envelope):
    out, seen = [], set(); protocol = _dict(envelope.get("protocol"))
    if protocol.get("profile_id") != PROFILE: _add(out,seen,"POCI_PROFILE_UNSUPPORTED","BLOCK","$.protocol.profile_id","unsupported profile")
    if "authority" not in envelope: _add(out,seen,"AUTHORITY_MISSING","BLOCK","$.authority","authority section is absent")
    for key in sorted(REQUIRED):
        if key not in envelope and key != "authority": _add(out,seen,"POCI_REQUIRED_EVIDENCE_MISSING","BLOCK",f"$.{key}","required section is absent")
    for key in sorted(set(envelope)-TOP): _add(out,seen,"POCI_SCHEMA_INVALID","BLOCK",f"$.{key}","unknown top-level property")
    if protocol and protocol.get("schema_version") != SCHEMA: _add(out,seen,"POCI_SCHEMA_INVALID","BLOCK","$.protocol.schema_version","unsupported schema version")
    types = {"protocol":dict,"intent":dict,"authority":dict,"causal_context":dict,"proposal":dict,"execution":dict,"observed_result":dict,"witnesses":list,"verification":dict,"evidence_integrity":dict}
    for key, kind in types.items():
        if key in envelope and not isinstance(envelope[key], kind): _add(out,seen,"POCI_SCHEMA_INVALID","BLOCK",f"$.{key}",f"expected {kind.__name__}")
    if timestamp(envelope.get("created_at")) is None: _add(out,seen,"POCI_SCHEMA_INVALID","BLOCK","$.created_at","invalid UTC timestamp")
    integrity = _dict(envelope.get("evidence_integrity"))
    if integrity and integrity.get("hash_algorithm") != "sha256": _add(out,seen,"POCI_SCHEMA_INVALID","BLOCK","$.evidence_integrity.hash_algorithm","must be sha256")
    if integrity and integrity.get("canonicalization_profile") != CANON: _add(out,seen,"POCI_SCHEMA_INVALID","BLOCK","$.evidence_integrity.canonicalization_profile","unsupported canonicalization profile")
    if _floats(envelope): _add(out,seen,"POCI_SCHEMA_INVALID","BLOCK","$","floating-point values are forbidden")
    def visit(value, path):
        if isinstance(value, dict):
            for key, item in value.items():
                child=f"{path}.{key}"
                if (key=="digest" or key.endswith("_digest")) and item is not None and (not isinstance(item,str) or not DIGEST.fullmatch(item)):
                    _add(out,seen,"POCI_SCHEMA_INVALID","BLOCK",child,"invalid digest format")
                visit(item,child)
        elif isinstance(value,list):
            for i,item in enumerate(value): visit(item,f"{path}[{i}]")
    visit(envelope,"$")
    return out

def _artifact_map(envelope):
    return {x.get("artifact_id"):x.get("digest") for x in _list(_dict(envelope.get("evidence_integrity")).get("artifacts")) if isinstance(x,dict)}

def _semantic(envelope, at):
    out, seen = [], set(); intent=_dict(envelope.get("intent")); auth=_dict(envelope.get("authority")); causal=_dict(envelope.get("causal_context")); proposal=_dict(envelope.get("proposal")); execution=_dict(envelope.get("execution")); observed=_dict(envelope.get("observed_result")); witnesses=[x for x in _list(envelope.get("witnesses")) if isinstance(x,dict)]
    start,end=timestamp(intent.get("valid_from")),timestamp(intent.get("expires_at"))
    if start is None or end is None or start>=end: _add(out,seen,"POCI_SCHEMA_INVALID","BLOCK","$.intent","invalid validity interval")
    elif at<start or at>=end: _add(out,seen,"INTENT_EXPIRED","BLOCK","$.intent.expires_at","intent is outside validity window")
    used=_list(_dict(_dict(envelope.get("extensions")).get("proofpath.fixture")).get("used_nonces"))
    if intent.get("nonce") in used: _add(out,seen,"INTENT_REPLAYED","BLOCK","$.intent.nonce","nonce already consumed")
    if auth:
        if auth.get("principal_id")!=intent.get("principal_id"): _add(out,seen,"AUTHORITY_SCOPE_VIOLATION","BLOCK","$.authority.principal_id","principal mismatch")
        if auth.get("agent_id")!=proposal.get("agent_id"): _add(out,seen,"AUTHORITY_SCOPE_VIOLATION","BLOCK","$.authority.agent_id","agent mismatch")
        if auth.get("executor_id")!=execution.get("executor_id"): _add(out,seen,"AUTHORITY_SCOPE_VIOLATION","BLOCK","$.authority.executor_id","executor mismatch")
        if auth.get("action_kind") not in {intent.get("action_kind")} or auth.get("action_kind")!=proposal.get("action_kind"): _add(out,seen,"AUTHORITY_SCOPE_VIOLATION","BLOCK","$.authority.action_kind","action kind mismatch")
        if not set(_list(proposal.get("scope"))).issubset(set(_list(auth.get("scope")))): _add(out,seen,"AUTHORITY_SCOPE_VIOLATION","BLOCK","$.proposal.scope","proposal exceeds scope")
        if auth.get("reversibility")=="irreversible" and auth.get("approval_required") is True and not auth.get("approval_ref"): _add(out,seen,"IRREVERSIBLE_APPROVAL_MISSING","BLOCK","$.authority.approval_ref","approval evidence is absent")
    if causal.get("required") is True:
        missing=causal.get("parent_type") in {None,"none"} or causal.get("parent_id") is None or causal.get("parent_digest") is None
        if missing: _add(out,seen,"CAUSAL_PARENT_MISSING","HOLD","$.causal_context","required causal parent is absent")
        elif causal.get("relationship") in {None,"none"}: _add(out,seen,"CAUSAL_PARENT_MISMATCH","BLOCK","$.causal_context.relationship","parent is non-authorizing")
    if execution:
        if execution.get("proposal_id")!=proposal.get("proposal_id"): _add(out,seen,"PROPOSAL_EXECUTION_MISMATCH","CHALLENGE","$.execution.proposal_id","execution is not bound to proposal")
        if execution.get("status")=="succeeded" and not execution.get("receipt_ref"): _add(out,seen,"EXECUTION_RECEIPT_MISSING","BLOCK","$.execution.receipt_ref","successful execution lacks receipt")
        ref=_dict(execution.get("receipt_ref")); claimed=execution.get("receipt_digest")
        if ref and isinstance(claimed,str) and ref.get("digest")!=claimed: _add(out,seen,"EXECUTION_RECEIPT_DIGEST_MISMATCH","CHALLENGE","$.execution.receipt_digest","receipt digests differ")
    if observed:
        if observed.get("status")=="observed" and not observed.get("result_ref"): _add(out,seen,"OBSERVED_RESULT_MISSING","BLOCK","$.observed_result.result_ref","observed result lacks evidence")
        ref=_dict(observed.get("result_ref")); claimed=observed.get("result_digest")
        if ref and isinstance(claimed,str) and ref.get("digest")!=claimed: _add(out,seen,"RESULT_DIGEST_MISMATCH","CHALLENGE","$.observed_result.result_digest","result digests differ")
    if not witnesses: _add(out,seen,"WITNESS_QUORUM_UNMET","HOLD","$.witnesses","at least one witness is required")
    else:
        if len({x.get("verdict") for x in witnesses})>1: _add(out,seen,"WITNESS_CONFLICT","CHALLENGE","$.witnesses","witness verdicts conflict")
        by_id={}
        for i,w in enumerate(witnesses):
            by_id.setdefault(w.get("witness_id"),set()).add(w.get("statement_digest")); ref=_dict(w.get("statement_ref"))
            if ref and ref.get("digest")!=w.get("statement_digest"): _add(out,seen,"ARTIFACT_DIGEST_MISMATCH","CHALLENGE",f"$.witnesses[{i}].statement_digest","witness digests differ")
        if any(len(x)>1 for x in by_id.values()): _add(out,seen,"WITNESS_EQUIVOCATION","CHALLENGE","$.witnesses","witness identity equivocated")
    committed=_artifact_map(envelope)
    refs=[("$.intent.signature_ref",intent.get("signature_ref")),("$.execution.receipt_ref",execution.get("receipt_ref")),("$.observed_result.result_ref",observed.get("result_ref"))]+[(f"$.witnesses[{i}].statement_ref",w.get("statement_ref")) for i,w in enumerate(witnesses)]
    for path,raw in refs:
        ref=_dict(raw); aid,digest=ref.get("artifact_id"),ref.get("digest")
        if aid and digest and committed.get(aid)!=digest: _add(out,seen,"ARTIFACT_DIGEST_MISMATCH","CHALLENGE",path,"artifact commitment missing or different")
    return out

def _sort_key(item): return (-RANK[item["decision"]],PRIORITY.get(item["code"],500),item["code"],item["path"])
def verify_envelope(envelope, at=None):
    evaluation=at or timestamp(envelope.get("created_at")) or datetime(1970,1,1,tzinfo=timezone.utc)
    unique={}
    for finding in _structure(envelope)+_semantic(envelope,evaluation): unique.setdefault((finding["code"],finding["path"]),finding)
    findings=sorted(unique.values(),key=_sort_key)
    try: computed=compute_envelope_root(envelope)
    except (TypeError,ValueError) as exc: findings.append(_finding("VERIFIER_INTERNAL_FAIL_CLOSED","BLOCK","$",str(exc))); computed=None
    declared=_dict(envelope.get("evidence_integrity")).get("envelope_root")
    if isinstance(declared,str) and computed is not None and (not DIGEST.fullmatch(declared) or not hmac.compare_digest(declared,computed)):
        findings.append(_finding("ENVELOPE_ROOT_MISMATCH","CHALLENGE","$.evidence_integrity.envelope_root","declared root differs"))
    findings=sorted(findings,key=_sort_key); primary=findings[0] if findings else None; decision=primary["decision"] if primary else "ACCEPT"
    return {"profile_id":_dict(envelope.get("protocol")).get("profile_id"),"envelope_id":envelope.get("envelope_id"),"decision":decision,"primary_reason_code":primary["code"] if primary else None,"reason_codes":sorted({x["code"] for x in findings}),"findings":findings,"computed_envelope_root":computed,"declared_envelope_root":declared,"valid":decision=="ACCEPT"}

def verify_manifest(path):
    manifest=load_json(path); cases=manifest.get("cases")
    if not isinstance(cases,list) or not cases: raise ValueError("manifest needs non-empty cases")
    results=[]
    for entry in cases:
        result=verify_envelope(load_json(path.parent/entry["file"])); ok=result["decision"]==entry.get("expected_decision") and result["primary_reason_code"]==entry.get("expected_primary_reason_code")
        results.append({"file":entry["file"],"expected_decision":entry.get("expected_decision"),"actual_decision":result["decision"],"expected_primary_reason_code":entry.get("expected_primary_reason_code"),"actual_primary_reason_code":result["primary_reason_code"],"computed_envelope_root":result["computed_envelope_root"],"passed":ok})
    return {"profile_id":manifest.get("profile_id"),"fixture_contract_version":manifest.get("fixture_contract_version"),"cases":results,"passed":all(x["passed"] for x in results),"case_count":len(results)}

def _at(value):
    parsed=timestamp(value)
    if value is not None and parsed is None: raise ValueError("--at must use YYYY-MM-DDTHH:MM:SSZ")
    return parsed

def main(argv: Iterable[str]|None=None):
    parser=argparse.ArgumentParser(description="Verify ProofPath PoCI v0.1 evidence offline"); parser.add_argument("path",type=Path); parser.add_argument("--manifest",action="store_true"); parser.add_argument("--at"); parser.add_argument("--pretty",action="store_true"); parser.add_argument("--allow-non-accept",action="store_true"); args=parser.parse_args(list(argv) if argv is not None else None)
    try:
        result=verify_manifest(args.path.resolve()) if args.manifest else verify_envelope(load_json(args.path.resolve()),_at(args.at)); code=(0 if result["passed"] else 1) if args.manifest else EXIT[result["decision"]]
        if args.allow_non_accept: code=0
    except (OSError,ValueError,KeyError,TypeError) as exc:
        result={"profile_id":PROFILE,"decision":"BLOCK","primary_reason_code":"VERIFIER_INTERNAL_FAIL_CLOSED","reason_codes":["VERIFIER_INTERNAL_FAIL_CLOSED"],"findings":[_finding("VERIFIER_INTERNAL_FAIL_CLOSED","BLOCK","$",str(exc))],"valid":False}; code=1
    if args.pretty: print(json.dumps(result,indent=2,ensure_ascii=False))
    else: sys.stdout.buffer.write(normalized_json_bytes(result))
    return code

if __name__=="__main__": raise SystemExit(main())

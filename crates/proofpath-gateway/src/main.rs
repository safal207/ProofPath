use axum::{
    body::Bytes,
    extract::State,
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use proofpath_verifier::{verify, Decision, RequestContext};
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::{env, net::SocketAddr, path::PathBuf, sync::Arc};
use tokio::{fs::OpenOptions, io::AsyncWriteExt, sync::Mutex};
use uuid::Uuid;

#[derive(Debug, Clone)]
struct AppState {
    protected_api_name: Arc<str>,
    upstream_url: Arc<str>,
    client: reqwest::Client,
    audit: AuditLog,
}

#[derive(Debug, Clone)]
struct AuditLog {
    path: Arc<PathBuf>,
    last_hash: Arc<Mutex<String>>,
}

#[derive(Debug, Serialize)]
struct GatewayResponse {
    protected_api: String,
    upstream_url: String,
    proofpath: proofpath_verifier::VerificationResult,
    forwarded: bool,
    upstream_status: Option<u16>,
    audit_hash: String,
    message: String,
}

#[derive(Debug, Serialize)]
struct AuditRecord {
    audit_id: Uuid,
    previous_hash: String,
    intent_id: Option<String>,
    causal_parent: Option<String>,
    scope: Option<String>,
    decision: Decision,
    reason: Option<proofpath_verifier::ReasonCode>,
    forwarded: bool,
    upstream_url: String,
    upstream_status: Option<u16>,
    hash: String,
}

#[tokio::main]
async fn main() {
    let upstream_url = env::var("PROOFPATH_UPSTREAM_URL")
        .unwrap_or_else(|_| "http://127.0.0.1:9797/protected".to_owned());
    let audit_path = env::var("PROOFPATH_AUDIT_LOG")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("proofpath-audit.jsonl"));

    let state = AppState {
        protected_api_name: Arc::from("demo-protected-api"),
        upstream_url: Arc::from(upstream_url),
        client: reqwest::Client::new(),
        audit: AuditLog {
            path: Arc::new(audit_path),
            last_hash: Arc::new(Mutex::new("GENESIS".to_owned())),
        },
    };

    let app = Router::new()
        .route("/health", get(health))
        .route("/gateway", post(gateway))
        .route("/demo/protected", post(gateway))
        .with_state(state);

    let addr = SocketAddr::from(([127, 0, 0, 1], 8787));
    let listener = tokio::net::TcpListener::bind(addr)
        .await
        .expect("bind gateway listener");

    println!("ProofPath gateway listening on http://{addr}");
    axum::serve(listener, app).await.expect("run gateway");
}

async fn health() -> impl IntoResponse {
    (StatusCode::OK, "proofpath-gateway: ok")
}

async fn gateway(
    State(state): State<AppState>,
    headers: HeaderMap,
    body: Bytes,
) -> impl IntoResponse {
    let ctx = request_context_from_headers(&headers);
    let result = verify(&ctx);
    let accepted = result.decision == Decision::Accept;
    let status = status_for_decision(result.decision);

    let mut upstream_status = None;
    let mut forwarded = false;

    if accepted {
        if let Ok(status) = forward_to_upstream(&state, &headers, body).await {
            upstream_status = Some(status.as_u16());
            forwarded = true;
        }
    }

    let audit_hash = state
        .audit
        .append(&result, forwarded, state.upstream_url.as_ref(), upstream_status)
        .await
        .unwrap_or_else(|_| "AUDIT_WRITE_FAILED".to_owned());

    let message = if forwarded {
        "ProofPath accepted the action and forwarded it to the protected API."
    } else if accepted {
        "ProofPath accepted the action, but upstream forwarding failed."
    } else {
        "ProofPath rejected or blocked the action before it reached the protected API."
    };

    let response = GatewayResponse {
        protected_api: state.protected_api_name.to_string(),
        upstream_url: state.upstream_url.to_string(),
        proofpath: result,
        forwarded,
        upstream_status,
        audit_hash,
        message: message.to_owned(),
    };

    (status, Json(response))
}

async fn forward_to_upstream(
    state: &AppState,
    headers: &HeaderMap,
    body: Bytes,
) -> Result<reqwest::StatusCode, reqwest::Error> {
    let mut request = state.client.post(state.upstream_url.as_ref()).body(body.to_vec());

    for (name, value) in headers {
        if let Ok(value) = value.to_str() {
            request = request.header(name.as_str(), value);
        }
    }

    request.send().await.map(|response| response.status())
}

impl AuditLog {
    async fn append(
        &self,
        result: &proofpath_verifier::VerificationResult,
        forwarded: bool,
        upstream_url: &str,
        upstream_status: Option<u16>,
    ) -> std::io::Result<String> {
        let mut previous_hash = self.last_hash.lock().await;
        let audit_id = Uuid::new_v4();
        let hash = compute_hash(
            &previous_hash,
            &audit_id,
            result,
            forwarded,
            upstream_url,
            upstream_status,
        );

        let record = AuditRecord {
            audit_id,
            previous_hash: previous_hash.clone(),
            intent_id: result.intent_id.clone(),
            causal_parent: result.causal_parent.clone(),
            scope: result.scope.clone(),
            decision: result.decision,
            reason: result.reason,
            forwarded,
            upstream_url: upstream_url.to_owned(),
            upstream_status,
            hash: hash.clone(),
        };

        let line = serde_json::to_string(&record).expect("serialize audit record");
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(self.path.as_ref())
            .await?;
        file.write_all(line.as_bytes()).await?;
        file.write_all(b"\n").await?;

        *previous_hash = hash.clone();
        Ok(hash)
    }
}

fn compute_hash(
    previous_hash: &str,
    audit_id: &Uuid,
    result: &proofpath_verifier::VerificationResult,
    forwarded: bool,
    upstream_url: &str,
    upstream_status: Option<u16>,
) -> String {
    let payload = serde_json::json!({
        "previous_hash": previous_hash,
        "audit_id": audit_id,
        "intent_id": result.intent_id.as_deref(),
        "causal_parent": result.causal_parent.as_deref(),
        "scope": result.scope.as_deref(),
        "decision": result.decision,
        "reason": result.reason,
        "forwarded": forwarded,
        "upstream_url": upstream_url,
        "upstream_status": upstream_status,
    });

    let mut hasher = Sha256::new();
    hasher.update(payload.to_string().as_bytes());
    format!("sha256:{:x}", hasher.finalize())
}

fn request_context_from_headers(headers: &HeaderMap) -> RequestContext {
    let mut ctx = RequestContext::new();

    for (name, value) in headers {
        if let Ok(value) = value.to_str() {
            ctx = ctx.with_header(name.as_str(), value);
        }
    }

    ctx
}

fn status_for_decision(decision: Decision) -> StatusCode {
    match decision {
        Decision::Accept | Decision::Audit => StatusCode::OK,
        Decision::Hold => StatusCode::ACCEPTED,
        Decision::Reject => StatusCode::BAD_REQUEST,
        Decision::Block => StatusCode::FORBIDDEN,
    }
}

#[cfg(test)]
mod tests {
    use super::{compute_hash, status_for_decision};
    use axum::http::StatusCode;
    use proofpath_verifier::{verify, Decision, RequestContext};
    use uuid::Uuid;

    #[test]
    fn maps_accept_to_ok() {
        assert_eq!(status_for_decision(Decision::Accept), StatusCode::OK);
    }

    #[test]
    fn maps_reject_to_bad_request() {
        assert_eq!(status_for_decision(Decision::Reject), StatusCode::BAD_REQUEST);
    }

    #[test]
    fn maps_block_to_forbidden() {
        assert_eq!(status_for_decision(Decision::Block), StatusCode::FORBIDDEN);
    }

    #[test]
    fn audit_hash_is_deterministic_for_same_payload() {
        let ctx = RequestContext::new()
            .with_header("x-proofpath-intent-id", "intent_1")
            .with_header("x-proofpath-causal-parent", "decision_1")
            .with_header("x-proofpath-scope", "profile.update")
            .with_header("x-proofpath-reversibility", "reversible");
        let result = verify(&ctx);
        let audit_id = Uuid::nil();

        let first = compute_hash("GENESIS", &audit_id, &result, true, "http://upstream", Some(200));
        let second = compute_hash("GENESIS", &audit_id, &result, true, "http://upstream", Some(200));

        assert_eq!(first, second);
    }
}

use axum::{
    extract::State,
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use proofpath_verifier::{verify, Decision, RequestContext};
use serde::Serialize;
use std::{net::SocketAddr, sync::Arc};

#[derive(Debug, Clone)]
struct AppState {
    protected_api_name: Arc<str>,
}

#[derive(Debug, Serialize)]
struct GatewayResponse {
    protected_api: String,
    proofpath: proofpath_verifier::VerificationResult,
    forwarded: bool,
    message: String,
}

#[tokio::main]
async fn main() {
    let state = AppState {
        protected_api_name: Arc::from("demo-protected-api"),
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

async fn gateway(State(state): State<AppState>, headers: HeaderMap) -> impl IntoResponse {
    let ctx = request_context_from_headers(&headers);
    let result = verify(&ctx);
    let accepted = result.decision == Decision::Accept;
    let status = status_for_decision(result.decision);

    let message = if accepted {
        "ProofPath accepted the action. The request would be forwarded to the protected API."
    } else {
        "ProofPath rejected or blocked the action before it reached the protected API."
    };

    let response = GatewayResponse {
        protected_api: state.protected_api_name.to_string(),
        proofpath: result,
        forwarded: accepted,
        message: message.to_owned(),
    };

    (status, Json(response))
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
    use super::status_for_decision;
    use axum::http::StatusCode;
    use proofpath_verifier::Decision;

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
}

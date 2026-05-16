//! Minimal `ProofPath` verifier.
//!
//! This crate validates the first `ProofPath` HTTP action context profile.
//! It intentionally starts small: required headers, reversibility values,
//! decision outcomes, and structured reason codes.

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

/// Header name for the declared intent id.
pub const HEADER_INTENT_ID: &str = "x-proofpath-intent-id";

/// Header name for the causal parent id.
pub const HEADER_CAUSAL_PARENT: &str = "x-proofpath-causal-parent";

/// Header name for the minimal action scope.
pub const HEADER_SCOPE: &str = "x-proofpath-scope";

/// Header name for reversibility classification.
pub const HEADER_REVERSIBILITY: &str = "x-proofpath-reversibility";

/// Header name for optional human approval reference.
pub const HEADER_HUMAN_APPROVAL: &str = "x-proofpath-human-approval";

/// Input model for the verifier.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct RequestContext {
    headers: BTreeMap<String, String>,
}

impl RequestContext {
    /// Create an empty request context.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Insert a header. Header names are normalized to lowercase.
    #[must_use]
    pub fn with_header(mut self, name: impl Into<String>, value: impl Into<String>) -> Self {
        self.headers
            .insert(name.into().to_ascii_lowercase(), value.into());
        self
    }

    /// Get a normalized header value.
    #[must_use]
    pub fn header(&self, name: &str) -> Option<&str> {
        self.headers
            .get(&name.to_ascii_lowercase())
            .map(String::as_str)
    }
}

/// `ProofPath` action reversibility class.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Reversibility {
    Reversible,
    Compensatable,
    Irreversible,
}

impl Reversibility {
    fn parse(value: &str) -> Option<Self> {
        match value.trim().to_ascii_lowercase().as_str() {
            "reversible" => Some(Self::Reversible),
            "compensatable" => Some(Self::Compensatable),
            "irreversible" => Some(Self::Irreversible),
            _ => None,
        }
    }
}

/// Verifier decision.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Decision {
    Accept,
    Hold,
    Reject,
    Block,
    Audit,
}

/// Structured reason codes.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ReasonCode {
    MissingIntent,
    MissingCausalParent,
    MissingScope,
    MissingReversibility,
    InvalidReversibility,
    IrreversibleActionRequiresApproval,
}

/// Verifier output.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct VerificationResult {
    pub decision: Decision,
    pub reason: Option<ReasonCode>,
    pub intent_id: Option<String>,
    pub causal_parent: Option<String>,
    pub scope: Option<String>,
    pub reversibility: Option<Reversibility>,
    pub human_approval: Option<String>,
    pub causal_valid: bool,
    pub scope_valid: bool,
}

impl VerificationResult {
    fn reject(reason: ReasonCode, ctx: &RequestContext) -> Self {
        Self {
            decision: Decision::Reject,
            reason: Some(reason),
            intent_id: value(ctx, HEADER_INTENT_ID),
            causal_parent: value(ctx, HEADER_CAUSAL_PARENT),
            scope: value(ctx, HEADER_SCOPE),
            reversibility: ctx
                .header(HEADER_REVERSIBILITY)
                .and_then(Reversibility::parse),
            human_approval: value(ctx, HEADER_HUMAN_APPROVAL),
            causal_valid: false,
            scope_valid: false,
        }
    }

    fn block(
        reason: ReasonCode,
        ctx: &RequestContext,
        reversibility: Option<Reversibility>,
    ) -> Self {
        Self {
            decision: Decision::Block,
            reason: Some(reason),
            intent_id: value(ctx, HEADER_INTENT_ID),
            causal_parent: value(ctx, HEADER_CAUSAL_PARENT),
            scope: value(ctx, HEADER_SCOPE),
            reversibility,
            human_approval: value(ctx, HEADER_HUMAN_APPROVAL),
            causal_valid: ctx.header(HEADER_CAUSAL_PARENT).is_some(),
            scope_valid: ctx.header(HEADER_SCOPE).is_some(),
        }
    }
}

/// Compute Witness job manifest projected into the Rust verifier.
///
/// This is intentionally a receipt-draft adapter input, not a final audit packet.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ComputeWitnessJobManifest {
    pub profile: String,
    pub job_id: String,
    pub agent_id: String,
    pub intent_id: String,
    pub causal_parent: Option<String>,
    pub scope: String,
    pub reversibility: Reversibility,
    pub human_approval: Option<String>,
    pub model_hash: String,
    pub runtime_hash: String,
    pub input_hash: String,
    pub expected_output_kind: String,
    pub requested_at: Option<String>,
}

/// Draft receipt produced by projecting a Compute Witness manifest through the Rust verifier.
///
/// This type deliberately omits `audit_hash` and final audit anchoring.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ComputeWitnessReceiptDraft {
    pub job_id: String,
    pub agent_id: String,
    pub intent_id: Option<String>,
    pub causal_parent: Option<String>,
    pub scope: Option<String>,
    pub model_hash: String,
    pub runtime_hash: String,
    pub input_hash: String,
    pub expected_output_kind: String,
    pub decision: Decision,
    pub reason: Option<ReasonCode>,
}

/// Project a Compute Witness job manifest into the generic ProofPath request context.
#[must_use]
pub fn manifest_to_request_context(manifest: &ComputeWitnessJobManifest) -> RequestContext {
    let mut ctx = RequestContext::new()
        .with_header(HEADER_INTENT_ID, manifest.intent_id.clone())
        .with_header(HEADER_SCOPE, manifest.scope.clone())
        .with_header(
            HEADER_REVERSIBILITY,
            reversibility_wire_value(manifest.reversibility),
        );

    if let Some(causal_parent) = manifest.causal_parent.as_deref() {
        ctx = ctx.with_header(HEADER_CAUSAL_PARENT, causal_parent);
    }

    if let Some(human_approval) = manifest.human_approval.as_deref() {
        ctx = ctx.with_header(HEADER_HUMAN_APPROVAL, human_approval);
    }

    ctx
}

/// Verify a Compute Witness manifest using the generic ProofPath verifier.
#[must_use]
pub fn verify_compute_manifest(manifest: &ComputeWitnessJobManifest) -> ComputeWitnessReceiptDraft {
    let ctx = manifest_to_request_context(manifest);
    let result = verify(&ctx);

    ComputeWitnessReceiptDraft {
        job_id: manifest.job_id.clone(),
        agent_id: manifest.agent_id.clone(),
        intent_id: result.intent_id,
        causal_parent: result.causal_parent,
        scope: result.scope,
        model_hash: manifest.model_hash.clone(),
        runtime_hash: manifest.runtime_hash.clone(),
        input_hash: manifest.input_hash.clone(),
        expected_output_kind: manifest.expected_output_kind.clone(),
        decision: result.decision,
        reason: result.reason,
    }
}

/// Verify a request context using the minimal v0.1 rules.
#[must_use]
pub fn verify(ctx: &RequestContext) -> VerificationResult {
    if is_blank(ctx.header(HEADER_INTENT_ID)) {
        return VerificationResult::reject(ReasonCode::MissingIntent, ctx);
    }

    if is_blank(ctx.header(HEADER_CAUSAL_PARENT)) {
        return VerificationResult::reject(ReasonCode::MissingCausalParent, ctx);
    }

    if is_blank(ctx.header(HEADER_SCOPE)) {
        return VerificationResult::reject(ReasonCode::MissingScope, ctx);
    }

    let Some(reversibility_raw) = ctx.header(HEADER_REVERSIBILITY) else {
        return VerificationResult::reject(ReasonCode::MissingReversibility, ctx);
    };

    let Some(reversibility) = Reversibility::parse(reversibility_raw) else {
        return VerificationResult::reject(ReasonCode::InvalidReversibility, ctx);
    };

    if reversibility == Reversibility::Irreversible && is_blank(ctx.header(HEADER_HUMAN_APPROVAL)) {
        return VerificationResult::block(
            ReasonCode::IrreversibleActionRequiresApproval,
            ctx,
            Some(reversibility),
        );
    }

    VerificationResult {
        decision: Decision::Accept,
        reason: None,
        intent_id: value(ctx, HEADER_INTENT_ID),
        causal_parent: value(ctx, HEADER_CAUSAL_PARENT),
        scope: value(ctx, HEADER_SCOPE),
        reversibility: Some(reversibility),
        human_approval: value(ctx, HEADER_HUMAN_APPROVAL),
        causal_valid: true,
        scope_valid: true,
    }
}

fn reversibility_wire_value(reversibility: Reversibility) -> &'static str {
    match reversibility {
        Reversibility::Reversible => "reversible",
        Reversibility::Compensatable => "compensatable",
        Reversibility::Irreversible => "irreversible",
    }
}

fn value(ctx: &RequestContext, name: &str) -> Option<String> {
    ctx.header(name)
        .map(str::trim)
        .filter(|v| !v.is_empty())
        .map(ToOwned::to_owned)
}

fn is_blank(value: Option<&str>) -> bool {
    value.is_none_or(|v| v.trim().is_empty())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn valid_irreversible_context() -> RequestContext {
        RequestContext::new()
            .with_header(HEADER_INTENT_ID, "intent_9f21")
            .with_header(HEADER_CAUSAL_PARENT, "decision_71ab")
            .with_header(HEADER_SCOPE, "payments.transfer.once")
            .with_header(HEADER_REVERSIBILITY, "irreversible")
            .with_header(HEADER_HUMAN_APPROVAL, "approval_11fa")
    }

    fn accepted_compute_manifest() -> ComputeWitnessJobManifest {
        ComputeWitnessJobManifest {
            profile: "proofpath.compute-witness.v0.1".to_owned(),
            job_id: "job_demo_accept_001".to_owned(),
            agent_id: "agent_demo_runner".to_owned(),
            intent_id: "intent_demo_inference".to_owned(),
            causal_parent: Some("decision_compute_budget_approved_001".to_owned()),
            scope: "compute.inference.demo.once".to_owned(),
            reversibility: Reversibility::Reversible,
            human_approval: None,
            model_hash: "sha256:1111111111111111111111111111111111111111111111111111111111111111"
                .to_owned(),
            runtime_hash: "sha256:2222222222222222222222222222222222222222222222222222222222222222"
                .to_owned(),
            input_hash: "sha256:3333333333333333333333333333333333333333333333333333333333333333"
                .to_owned(),
            expected_output_kind: "text.summary".to_owned(),
            requested_at: Some("2026-05-16T07:30:00Z".to_owned()),
        }
    }

    #[test]
    fn accepts_valid_irreversible_request_with_approval() {
        let result = verify(&valid_irreversible_context());

        assert_eq!(result.decision, Decision::Accept);
        assert_eq!(result.reason, None);
        assert_eq!(result.reversibility, Some(Reversibility::Irreversible));
        assert!(result.causal_valid);
        assert!(result.scope_valid);
    }

    #[test]
    fn rejects_missing_intent() {
        let ctx = valid_irreversible_context().with_header(HEADER_INTENT_ID, "");
        let result = verify(&ctx);

        assert_eq!(result.decision, Decision::Reject);
        assert_eq!(result.reason, Some(ReasonCode::MissingIntent));
    }

    #[test]
    fn rejects_missing_causal_parent() {
        let ctx = valid_irreversible_context().with_header(HEADER_CAUSAL_PARENT, "");
        let result = verify(&ctx);

        assert_eq!(result.decision, Decision::Reject);
        assert_eq!(result.reason, Some(ReasonCode::MissingCausalParent));
    }

    #[test]
    fn rejects_missing_scope() {
        let ctx = valid_irreversible_context().with_header(HEADER_SCOPE, "");
        let result = verify(&ctx);

        assert_eq!(result.decision, Decision::Reject);
        assert_eq!(result.reason, Some(ReasonCode::MissingScope));
    }

    #[test]
    fn rejects_invalid_reversibility() {
        let ctx = valid_irreversible_context().with_header(HEADER_REVERSIBILITY, "forever");
        let result = verify(&ctx);

        assert_eq!(result.decision, Decision::Reject);
        assert_eq!(result.reason, Some(ReasonCode::InvalidReversibility));
    }

    #[test]
    fn blocks_irreversible_request_without_human_approval() {
        let ctx = RequestContext::new()
            .with_header(HEADER_INTENT_ID, "intent_9f21")
            .with_header(HEADER_CAUSAL_PARENT, "decision_71ab")
            .with_header(HEADER_SCOPE, "payments.transfer.once")
            .with_header(HEADER_REVERSIBILITY, "irreversible");
        let result = verify(&ctx);

        assert_eq!(result.decision, Decision::Block);
        assert_eq!(
            result.reason,
            Some(ReasonCode::IrreversibleActionRequiresApproval)
        );
    }

    #[test]
    fn accepts_reversible_request_without_human_approval() {
        let ctx = RequestContext::new()
            .with_header(HEADER_INTENT_ID, "intent_9f21")
            .with_header(HEADER_CAUSAL_PARENT, "decision_71ab")
            .with_header(HEADER_SCOPE, "profile.update")
            .with_header(HEADER_REVERSIBILITY, "reversible");
        let result = verify(&ctx);

        assert_eq!(result.decision, Decision::Accept);
        assert_eq!(result.reason, None);
        assert_eq!(result.reversibility, Some(Reversibility::Reversible));
    }

    #[test]
    fn projects_compute_manifest_to_request_context() {
        let manifest = accepted_compute_manifest();
        let ctx = manifest_to_request_context(&manifest);

        assert_eq!(ctx.header(HEADER_INTENT_ID), Some("intent_demo_inference"));
        assert_eq!(
            ctx.header(HEADER_CAUSAL_PARENT),
            Some("decision_compute_budget_approved_001")
        );
        assert_eq!(
            ctx.header(HEADER_SCOPE),
            Some("compute.inference.demo.once")
        );
        assert_eq!(ctx.header(HEADER_REVERSIBILITY), Some("reversible"));
        assert_eq!(ctx.header(HEADER_HUMAN_APPROVAL), None);
    }

    #[test]
    fn verifies_compute_manifest_as_receipt_draft() {
        let manifest = accepted_compute_manifest();
        let receipt = verify_compute_manifest(&manifest);

        assert_eq!(receipt.job_id, "job_demo_accept_001");
        assert_eq!(receipt.agent_id, "agent_demo_runner");
        assert_eq!(receipt.intent_id.as_deref(), Some("intent_demo_inference"));
        assert_eq!(
            receipt.causal_parent.as_deref(),
            Some("decision_compute_budget_approved_001")
        );
        assert_eq!(
            receipt.scope.as_deref(),
            Some("compute.inference.demo.once")
        );
        assert_eq!(receipt.decision, Decision::Accept);
        assert_eq!(receipt.reason, None);
        assert_eq!(
            receipt.model_hash,
            "sha256:1111111111111111111111111111111111111111111111111111111111111111"
        );
    }

    #[test]
    fn compute_manifest_missing_causal_parent_uses_core_reject_semantics() {
        let mut manifest = accepted_compute_manifest();
        manifest.causal_parent = None;

        let receipt = verify_compute_manifest(&manifest);

        assert_eq!(receipt.decision, Decision::Reject);
        assert_eq!(receipt.reason, Some(ReasonCode::MissingCausalParent));
        assert_eq!(receipt.causal_parent, None);
    }

    #[test]
    fn deserializes_compute_manifest_from_json() {
        let raw = r#"
        {
          "profile": "proofpath.compute-witness.v0.1",
          "job_id": "job_demo_accept_001",
          "agent_id": "agent_demo_runner",
          "intent_id": "intent_demo_inference",
          "causal_parent": "decision_compute_budget_approved_001",
          "scope": "compute.inference.demo.once",
          "reversibility": "reversible",
          "human_approval": null,
          "model_hash": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
          "runtime_hash": "sha256:2222222222222222222222222222222222222222222222222222222222222222",
          "input_hash": "sha256:3333333333333333333333333333333333333333333333333333333333333333",
          "expected_output_kind": "text.summary",
          "requested_at": "2026-05-16T07:30:00Z"
        }
        "#;

        let manifest: ComputeWitnessJobManifest = serde_json::from_str(raw).unwrap();
        let receipt = verify_compute_manifest(&manifest);

        assert_eq!(receipt.decision, Decision::Accept);
        assert_eq!(receipt.reason, None);
    }
}

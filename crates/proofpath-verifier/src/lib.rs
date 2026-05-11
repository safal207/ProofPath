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
}

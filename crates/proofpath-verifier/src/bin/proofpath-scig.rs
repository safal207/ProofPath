use serde::Deserialize;
use std::{env, fs, process};

const INVARIANT_RESULTS: &[&str] = &["held", "violated", "unknown"];
const LIFECYCLE_RESULTS: &[&str] = &["passed", "failed", "unknown"];
const CAUSAL_TYPES: &[&str] = &[
    "enabled_by",
    "required",
    "triggered",
    "bypassed",
    "failed_to_prevent",
    "amplified",
    "masked",
    "recovered_by",
    "verified_by",
];

#[derive(Debug, Deserialize)]
struct ScigDocument {
    schema_version: String,
    incident_id: String,
    actor: Entity,
    action: Entity,
    pre_state: Entity,
    control: Control,
    transition: Transition,
    post_state: Entity,
    invariants: Vec<Invariant>,
    cause: Vec<CausalEdge>,
    containment: Lifecycle,
    recovery: Lifecycle,
    verification: Verification,
    evidence: Vec<Evidence>,
}

#[derive(Debug, Deserialize)]
struct Entity {
    id: String,
    #[serde(rename = "type")]
    kind: Option<String>,
}

#[derive(Debug, Deserialize)]
struct Control {
    id: String,
    #[serde(rename = "type")]
    kind: Option<String>,
    expected_outcome: String,
}

#[derive(Debug, Deserialize)]
struct Transition {
    id: String,
    from: String,
    action: String,
    to: String,
    phase: String,
    observed_at: String,
}

#[derive(Debug, Deserialize)]
struct Invariant {
    id: String,
    description: String,
    result: String,
    evidence_reference: Option<String>,
}

#[derive(Debug, Deserialize)]
struct CausalEdge {
    #[serde(rename = "type")]
    kind: String,
    source: String,
    target: String,
    evidence_reference: Option<String>,
}

#[derive(Debug, Deserialize)]
struct Lifecycle {
    action: String,
    result: String,
    target_state: Option<String>,
    evidence_reference: Option<String>,
}

#[derive(Debug, Deserialize)]
struct Verification {
    test_id: String,
    expected: String,
    observed: String,
    result: String,
    evidence_reference: Option<String>,
}

#[derive(Debug, Deserialize)]
struct Evidence {
    id: String,
    #[serde(rename = "type")]
    kind: String,
}

#[derive(Debug)]
struct ValidationReport {
    errors: Vec<String>,
}

impl ValidationReport {
    fn new() -> Self {
        Self { errors: Vec::new() }
    }

    fn require(&mut self, condition: bool, message: impl Into<String>) {
        if !condition {
            self.errors.push(message.into());
        }
    }

    fn is_valid(&self) -> bool {
        self.errors.is_empty()
    }
}

fn non_empty(value: &str) -> bool {
    !value.trim().is_empty()
}

fn evidence_exists(doc: &ScigDocument, id: &str) -> bool {
    doc.evidence.iter().any(|evidence| evidence.id == id)
}

fn validate(doc: &ScigDocument) -> ValidationReport {
    let mut report = ValidationReport::new();

    report.require(doc.schema_version == "0.1", "schema_version must equal 0.1");
    report.require(non_empty(&doc.incident_id), "incident_id must not be empty");
    report.require(non_empty(&doc.actor.id), "actor.id must not be empty");
    report.require(non_empty(&doc.action.id), "action.id must not be empty");
    report.require(
        non_empty(&doc.pre_state.id),
        "pre_state.id must not be empty",
    );
    report.require(
        non_empty(&doc.post_state.id),
        "post_state.id must not be empty",
    );
    report.require(non_empty(&doc.control.id), "control.id must not be empty");
    report.require(
        non_empty(&doc.control.expected_outcome),
        "control.expected_outcome must not be empty",
    );

    report.require(
        non_empty(&doc.transition.id),
        "transition.id must not be empty",
    );
    report.require(
        doc.transition.from == doc.pre_state.id,
        "transition.from must reference pre_state.id",
    );
    report.require(
        doc.transition.to == doc.post_state.id,
        "transition.to must reference post_state.id",
    );
    report.require(
        doc.transition.action == doc.action.id,
        "transition.action must reference action.id",
    );
    report.require(
        non_empty(&doc.transition.phase),
        "transition.phase must not be empty",
    );
    report.require(
        doc.transition.observed_at.contains('T') && doc.transition.observed_at.ends_with('Z'),
        "transition.observed_at must be an RFC3339-like UTC timestamp",
    );

    report.require(
        !doc.invariants.is_empty(),
        "at least one invariant is required",
    );
    report.require(
        !doc.evidence.is_empty(),
        "at least one evidence object is required",
    );

    for invariant in &doc.invariants {
        report.require(non_empty(&invariant.id), "invariant.id must not be empty");
        report.require(
            non_empty(&invariant.description),
            format!("{} description must not be empty", invariant.id),
        );
        report.require(
            INVARIANT_RESULTS.contains(&invariant.result.as_str()),
            format!("{} has invalid invariant result", invariant.id),
        );
        if let Some(reference) = &invariant.evidence_reference {
            report.require(
                evidence_exists(doc, reference),
                format!("{} references missing evidence {reference}", invariant.id),
            );
        }
    }

    for edge in &doc.cause {
        report.require(
            CAUSAL_TYPES.contains(&edge.kind.as_str()),
            format!(
                "causal edge {} -> {} has invalid type {}",
                edge.source, edge.target, edge.kind
            ),
        );
        report.require(
            non_empty(&edge.source),
            "causal edge source must not be empty",
        );
        report.require(
            non_empty(&edge.target),
            "causal edge target must not be empty",
        );
        if let Some(reference) = &edge.evidence_reference {
            report.require(
                evidence_exists(doc, reference),
                format!("causal edge references missing evidence {reference}"),
            );
        }
    }

    validate_lifecycle(doc, &doc.containment, "containment", &mut report);
    validate_lifecycle(doc, &doc.recovery, "recovery", &mut report);

    report.require(
        LIFECYCLE_RESULTS.contains(&doc.verification.result.as_str()),
        "verification.result must be passed, failed, or unknown",
    );
    report.require(
        non_empty(&doc.verification.test_id),
        "verification.test_id must not be empty",
    );
    report.require(
        non_empty(&doc.verification.expected),
        "verification.expected must not be empty",
    );
    report.require(
        non_empty(&doc.verification.observed),
        "verification.observed must not be empty",
    );

    if let Some(reference) = &doc.verification.evidence_reference {
        report.require(
            evidence_exists(doc, reference),
            format!("verification references missing evidence {reference}"),
        );
    }

    if doc.verification.result == "passed" {
        report.require(
            doc.recovery.result == "passed",
            "verification cannot pass unless recovery passed",
        );
        report.require(
            doc.verification.expected == doc.verification.observed,
            "verification passed but expected and observed differ",
        );
    }

    for evidence in &doc.evidence {
        report.require(non_empty(&evidence.id), "evidence.id must not be empty");
        report.require(
            non_empty(&evidence.kind),
            format!("evidence {} type must not be empty", evidence.id),
        );
    }

    let _ = (
        &doc.actor.kind,
        &doc.action.kind,
        &doc.pre_state.kind,
        &doc.post_state.kind,
    );
    let _ = (
        &doc.control.kind,
        &doc.containment.target_state,
        &doc.recovery.target_state,
    );

    report
}

fn validate_lifecycle(
    doc: &ScigDocument,
    lifecycle: &Lifecycle,
    label: &str,
    report: &mut ValidationReport,
) {
    report.require(
        non_empty(&lifecycle.action),
        format!("{label}.action must not be empty"),
    );
    report.require(
        LIFECYCLE_RESULTS.contains(&lifecycle.result.as_str()),
        format!("{label}.result must be passed, failed, or unknown"),
    );
    if let Some(reference) = &lifecycle.evidence_reference {
        report.require(
            evidence_exists(doc, reference),
            format!("{label} references missing evidence {reference}"),
        );
    }
}

fn lifecycle_label(result: &str) -> &'static str {
    match result {
        "passed" => "PASSED",
        "failed" => "FAILED",
        _ => "UNKNOWN",
    }
}

fn invariant_label(result: &str) -> &'static str {
    match result {
        "held" => "HELD",
        "violated" => "VIOLATED",
        _ => "UNKNOWN",
    }
}

fn print_report(doc: &ScigDocument, report: &ValidationReport) {
    println!("SCIG {}", doc.incident_id);
    for invariant in &doc.invariants {
        println!(
            "{:<18} {}",
            invariant.id,
            invariant_label(&invariant.result)
        );
    }
    println!(
        "{:<18} {}",
        "CONTAINMENT",
        lifecycle_label(&doc.containment.result)
    );
    println!(
        "{:<18} {}",
        "RECOVERY",
        lifecycle_label(&doc.recovery.result)
    );
    println!(
        "{:<18} {}",
        "VERIFICATION",
        lifecycle_label(&doc.verification.result)
    );
    println!(
        "{:<18} {}",
        "RESULT",
        if report.is_valid() {
            "VALID"
        } else {
            "INVALID"
        }
    );

    if !report.is_valid() {
        eprintln!("\nValidation errors:");
        for error in &report.errors {
            eprintln!("- {error}");
        }
    }
}

fn run(path: &str) -> Result<bool, String> {
    let raw = fs::read_to_string(path).map_err(|error| format!("cannot read {path}: {error}"))?;
    let document: ScigDocument =
        serde_json::from_str(&raw).map_err(|error| format!("invalid SCIG JSON: {error}"))?;
    let report = validate(&document);
    print_report(&document, &report);
    Ok(report.is_valid())
}

fn main() {
    let mut args = env::args();
    let program = args.next().unwrap_or_else(|| "proofpath-scig".to_string());
    let Some(path) = args.next() else {
        eprintln!("usage: {program} <scig.json>");
        process::exit(2);
    };

    match run(&path) {
        Ok(true) => {}
        Ok(false) => process::exit(1),
        Err(error) => {
            eprintln!("{error}");
            process::exit(2);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn valid_document() -> ScigDocument {
        serde_json::from_str(
            r#"{
              "schema_version":"0.1",
              "incident_id":"TEST-1",
              "actor":{"id":"agent","type":"ai_agent"},
              "action":{"id":"action","type":"tool_call"},
              "pre_state":{"id":"before"},
              "control":{"id":"policy","type":"capability_policy","expected_outcome":"deny"},
              "transition":{"id":"t1","from":"before","action":"action","to":"after","phase":"execution","observed_at":"2026-08-10T11:42:31Z"},
              "post_state":{"id":"after"},
              "invariants":[{"id":"INV-1","description":"must hold","result":"held","evidence_reference":"ev1"}],
              "cause":[{"type":"verified_by","source":"action","target":"VERIFY-1","evidence_reference":"ev1"}],
              "containment":{"action":"block","result":"passed","evidence_reference":"ev1"},
              "recovery":{"action":"restore","result":"passed","evidence_reference":"ev1"},
              "verification":{"test_id":"VERIFY-1","expected":"denied","observed":"denied","result":"passed","evidence_reference":"ev1"},
              "evidence":[{"id":"ev1","type":"test_result"}]
            }"#,
        )
        .expect("fixture should deserialize")
    }

    #[test]
    fn accepts_valid_document() {
        let doc = valid_document();
        let report = validate(&doc);
        assert!(report.is_valid(), "{:?}", report.errors);
    }

    #[test]
    fn rejects_broken_transition_reference() {
        let mut doc = valid_document();
        doc.transition.to = "wrong-state".to_string();
        let report = validate(&doc);
        assert!(!report.is_valid());
        assert!(report
            .errors
            .iter()
            .any(|error| error.contains("transition.to")));
    }

    #[test]
    fn rejects_passing_verification_without_recovery() {
        let mut doc = valid_document();
        doc.recovery.result = "failed".to_string();
        let report = validate(&doc);
        assert!(!report.is_valid());
        assert!(report
            .errors
            .iter()
            .any(|error| error.contains("recovery passed")));
    }

    #[test]
    fn rejects_missing_evidence_reference() {
        let mut doc = valid_document();
        doc.invariants[0].evidence_reference = Some("missing".to_string());
        let report = validate(&doc);
        assert!(!report.is_valid());
        assert!(report
            .errors
            .iter()
            .any(|error| error.contains("missing evidence")));
    }
}

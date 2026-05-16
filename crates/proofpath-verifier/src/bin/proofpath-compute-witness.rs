use proofpath_verifier::{verify_compute_manifest, ComputeWitnessJobManifest};
use std::{env, error::Error, fs};

fn main() -> Result<(), Box<dyn Error>> {
    let Some(path) = env::args().nth(1) else {
        eprintln!("usage: proofpath-compute-witness <job_manifest.json>");
        std::process::exit(2);
    };

    let raw = fs::read_to_string(path)?;
    let manifest: ComputeWitnessJobManifest = serde_json::from_str(&raw)?;
    let receipt = verify_compute_manifest(&manifest);

    println!("{}", serde_json::to_string_pretty(&receipt)?);

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_manifest_and_emits_receipt_draft() {
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

        assert_eq!(receipt.job_id, "job_demo_accept_001");
        assert_eq!(receipt.intent_id.as_deref(), Some("intent_demo_inference"));
    }
}

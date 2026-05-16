//! Compute Witness audit hashing helpers.
//!
//! This module mirrors the Python conformance canonical JSON contract:
//!
//! - object keys are sorted;
//! - no extra whitespace is emitted;
//! - UTF-8 JSON bytes are hashed with SHA-256;
//! - hashes are rendered as `sha256:<lowercase hex>`.

use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};

/// Compute Witness audit log entry.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ComputeWitnessAuditEntry {
    pub profile: String,
    pub audit_id: String,
    pub receipt_id: String,
    pub job_id: String,
    pub agent_id: String,
    pub intent_id: String,
    pub decision: String,
    pub reason: Option<String>,
    pub event_type: String,
    pub previous_audit_hash: Option<String>,
    pub recorded_at: String,
}

/// Compute the canonical Compute Witness audit hash.
///
/// This intentionally operates on `serde_json::Value` so it can preserve the exact
/// fixture contract without requiring every future audit field to be modeled first.
#[must_use]
pub fn compute_audit_hash(value: &Value) -> String {
    let canonical = canonical_json(value);
    let digest = Sha256::digest(canonical.as_bytes());
    format!("sha256:{}", hex_lower(&digest))
}

/// Verify that an audit entry matches the expected `sha256:<hex>` value.
#[must_use]
pub fn verify_audit_hash(value: &Value, expected_audit_hash: &str) -> bool {
    compute_audit_hash(value) == expected_audit_hash
}

fn canonical_json(value: &Value) -> String {
    match value {
        Value::Null => "null".to_owned(),
        Value::Bool(value) => value.to_string(),
        Value::Number(value) => value.to_string(),
        Value::String(value) => {
            serde_json::to_string(value).expect("serializing JSON string cannot fail")
        }
        Value::Array(items) => {
            let body = items
                .iter()
                .map(canonical_json)
                .collect::<Vec<_>>()
                .join(",");
            format!("[{body}]")
        }
        Value::Object(map) => {
            let mut keys = map.keys().collect::<Vec<_>>();
            keys.sort();

            let body = keys
                .into_iter()
                .map(|key| {
                    let encoded_key =
                        serde_json::to_string(key).expect("serializing JSON object key cannot fail");
                    let encoded_value = canonical_json(&map[key]);
                    format!("{encoded_key}:{encoded_value}")
                })
                .collect::<Vec<_>>()
                .join(",");
            format!("{{{body}}}")
        }
    }
}

fn hex_lower(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut output = String::with_capacity(bytes.len() * 2);

    for byte in bytes {
        output.push(char::from(HEX[usize::from(byte >> 4)]));
        output.push(char::from(HEX[usize::from(byte & 0x0f)]));
    }

    output
}

#[cfg(test)]
mod tests {
    use super::*;

    const ACCEPT_AUDIT_LOG: &str =
        include_str!("../../../examples/compute-witness/audit_log.accept.json");
    const ACCEPT_RECEIPT: &str =
        include_str!("../../../examples/compute-witness/compute_receipt.accept.json");

    #[test]
    fn computes_expected_accept_audit_hash() {
        let audit: Value = serde_json::from_str(ACCEPT_AUDIT_LOG).unwrap();
        let receipt: Value = serde_json::from_str(ACCEPT_RECEIPT).unwrap();
        let expected = receipt["audit_hash"].as_str().unwrap();

        assert_eq!(
            compute_audit_hash(&audit),
            "sha256:5f37260103eb5848ffb0fc07c11b4da38d67a2137ebe0898c1ac65d7396ed88f"
        );
        assert!(verify_audit_hash(&audit, expected));
    }

    #[test]
    fn rejects_mismatched_audit_hash() {
        let audit: Value = serde_json::from_str(ACCEPT_AUDIT_LOG).unwrap();

        assert!(!verify_audit_hash(
            &audit,
            "sha256:0000000000000000000000000000000000000000000000000000000000000000"
        ));
    }

    #[test]
    fn deserializes_compute_witness_audit_entry() {
        let audit: ComputeWitnessAuditEntry = serde_json::from_str(ACCEPT_AUDIT_LOG).unwrap();

        assert_eq!(audit.profile, "proofpath.compute-witness.audit-entry.v0.1");
        assert_eq!(audit.audit_id, "audit_demo_accept_001");
        assert_eq!(audit.receipt_id, "cwr_demo_accept_001");
        assert_eq!(audit.reason, None);
    }
}

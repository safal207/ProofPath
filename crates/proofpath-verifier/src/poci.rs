#![allow(clippy::all, clippy::pedantic)]

use serde::de::{self, MapAccess, SeqAccess, Visitor};
use serde::{Deserialize, Deserializer, Serialize};
use serde_json::{Map, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::fmt;
use std::fs;
use std::path::{Path, PathBuf};

pub const PROFILE: &str = "proofpath.poci.v0.1";
pub const SCHEMA_VERSION: &str = "0.1.0";
pub const CANONICALIZATION_PROFILE: &str = "proofpath.poci.canonical-json.v0.1";
const DOMAIN: &[u8] = b"proofpath:poci:v0.1:envelope\n";

const TOP_LEVEL_FIELDS: &[&str] = &[
    "protocol",
    "envelope_id",
    "created_at",
    "intent",
    "authority",
    "causal_context",
    "proposal",
    "execution",
    "observed_result",
    "witnesses",
    "verification",
    "evidence_integrity",
    "extensions",
];

const REQUIRED_FIELDS: &[&str] = &[
    "protocol",
    "envelope_id",
    "created_at",
    "intent",
    "authority",
    "causal_context",
    "proposal",
    "execution",
    "observed_result",
    "witnesses",
    "verification",
    "evidence_integrity",
];

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum PociDecision {
    Accept,
    Hold,
    Block,
    Challenge,
}

impl PociDecision {
    #[must_use]
    pub const fn exit_code(self) -> i32 {
        match self {
            Self::Accept => 0,
            Self::Hold => 2,
            Self::Block => 3,
            Self::Challenge => 4,
        }
    }

    const fn rank(self) -> u8 {
        match self {
            Self::Accept => 0,
            Self::Hold => 1,
            Self::Block => 2,
            Self::Challenge => 3,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Finding {
    pub code: String,
    pub decision: PociDecision,
    pub path: String,
    pub message: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct VerificationOutput {
    pub profile_id: Option<String>,
    pub envelope_id: Option<String>,
    pub decision: PociDecision,
    pub primary_reason_code: Option<String>,
    pub reason_codes: Vec<String>,
    pub findings: Vec<Finding>,
    pub computed_envelope_root: Option<String>,
    pub declared_envelope_root: Option<String>,
    pub valid: bool,
}

#[derive(Debug, Deserialize)]
struct Manifest {
    profile_id: String,
    fixture_contract_version: String,
    cases: Vec<ManifestCase>,
}

#[derive(Debug, Deserialize)]
struct ManifestCase {
    file: String,
    expected_decision: PociDecision,
    expected_primary_reason_code: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ManifestCaseResult {
    pub file: String,
    pub expected_decision: PociDecision,
    pub actual_decision: PociDecision,
    pub expected_primary_reason_code: Option<String>,
    pub actual_primary_reason_code: Option<String>,
    pub computed_envelope_root: Option<String>,
    pub passed: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ManifestReport {
    pub profile_id: String,
    pub fixture_contract_version: String,
    pub cases: Vec<ManifestCaseResult>,
    pub passed: bool,
    pub case_count: usize,
}

#[derive(Debug)]
struct StrictValue(Value);

struct StrictVisitor;

impl<'de> Deserialize<'de> for StrictValue {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        deserializer.deserialize_any(StrictVisitor)
    }
}

impl<'de> Visitor<'de> for StrictVisitor {
    type Value = StrictValue;

    fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("strict JSON without duplicate keys or floating-point numbers")
    }

    fn visit_bool<E>(self, value: bool) -> Result<Self::Value, E>
    where
        E: de::Error,
    {
        Ok(StrictValue(Value::Bool(value)))
    }

    fn visit_i64<E>(self, value: i64) -> Result<Self::Value, E>
    where
        E: de::Error,
    {
        Ok(StrictValue(Value::Number(value.into())))
    }

    fn visit_u64<E>(self, value: u64) -> Result<Self::Value, E>
    where
        E: de::Error,
    {
        Ok(StrictValue(Value::Number(value.into())))
    }

    fn visit_f64<E>(self, _value: f64) -> Result<Self::Value, E>
    where
        E: de::Error,
    {
        Err(E::custom("floating-point values are forbidden"))
    }

    fn visit_str<E>(self, value: &str) -> Result<Self::Value, E>
    where
        E: de::Error,
    {
        Ok(StrictValue(Value::String(value.to_owned())))
    }

    fn visit_string<E>(self, value: String) -> Result<Self::Value, E>
    where
        E: de::Error,
    {
        Ok(StrictValue(Value::String(value)))
    }

    fn visit_none<E>(self) -> Result<Self::Value, E>
    where
        E: de::Error,
    {
        Ok(StrictValue(Value::Null))
    }

    fn visit_unit<E>(self) -> Result<Self::Value, E>
    where
        E: de::Error,
    {
        Ok(StrictValue(Value::Null))
    }

    fn visit_some<D>(self, deserializer: D) -> Result<Self::Value, D::Error>
    where
        D: Deserializer<'de>,
    {
        StrictValue::deserialize(deserializer)
    }

    fn visit_seq<A>(self, mut sequence: A) -> Result<Self::Value, A::Error>
    where
        A: SeqAccess<'de>,
    {
        let mut values = Vec::new();
        while let Some(value) = sequence.next_element::<StrictValue>()? {
            values.push(value.0);
        }
        Ok(StrictValue(Value::Array(values)))
    }

    fn visit_map<A>(self, mut object: A) -> Result<Self::Value, A::Error>
    where
        A: MapAccess<'de>,
    {
        let mut values = Map::new();
        while let Some(key) = object.next_key::<String>()? {
            if values.contains_key(&key) {
                return Err(de::Error::custom(format!("duplicate JSON key: {key}")));
            }
            let value = object.next_value::<StrictValue>()?;
            values.insert(key, value.0);
        }
        Ok(StrictValue(Value::Object(values)))
    }
}

pub fn parse_strict_json(raw: &str) -> Result<Value, String> {
    let mut deserializer = serde_json::Deserializer::from_str(raw);
    let value = StrictValue::deserialize(&mut deserializer).map_err(|error| error.to_string())?;
    deserializer.end().map_err(|error| error.to_string())?;
    Ok(value.0)
}

pub fn read_strict_json(path: &Path) -> Result<Value, String> {
    let raw = fs::read_to_string(path)
        .map_err(|error| format!("failed to read {}: {error}", path.display()))?;
    parse_strict_json(&raw).map_err(|error| format!("invalid JSON in {}: {error}", path.display()))
}

pub fn compute_envelope_root(envelope: &Value) -> Result<String, String> {
    let mut normalized = envelope.clone();
    let root = normalized
        .as_object_mut()
        .ok_or_else(|| "envelope must be a JSON object".to_owned())?;

    match root.get_mut("evidence_integrity") {
        Some(Value::Object(integrity)) => {
            integrity.insert("envelope_root".to_owned(), Value::Null);
        }
        Some(_) => {
            return Err("evidence_integrity must be a JSON object".to_owned());
        }
        None => {
            let mut integrity = Map::new();
            integrity.insert("envelope_root".to_owned(), Value::Null);
            root.insert("evidence_integrity".to_owned(), Value::Object(integrity));
        }
    }

    let canonical = serde_json::to_vec(&normalized).map_err(|error| error.to_string())?;
    let mut hasher = Sha256::new();
    hasher.update(DOMAIN);
    hasher.update(canonical);
    Ok(format!("sha256:{:x}", hasher.finalize()))
}

#[must_use]
pub fn verify_envelope(envelope: &Value) -> VerificationOutput {
    let mut findings = Vec::new();
    let mut seen = BTreeSet::new();

    structural_findings(envelope, &mut findings, &mut seen);
    semantic_findings(envelope, &mut findings, &mut seen);

    let computed_root = match compute_envelope_root(envelope) {
        Ok(root) => Some(root),
        Err(error) => {
            add_finding(
                &mut findings,
                &mut seen,
                "VERIFIER_INTERNAL_FAIL_CLOSED",
                PociDecision::Block,
                "$",
                &error,
            );
            None
        }
    };

    let declared_root = envelope
        .get("evidence_integrity")
        .and_then(Value::as_object)
        .and_then(|value| value.get("envelope_root"))
        .and_then(Value::as_str)
        .map(ToOwned::to_owned);

    if let (Some(declared), Some(computed)) = (&declared_root, &computed_root) {
        if !valid_digest(declared) || declared != computed {
            add_finding(
                &mut findings,
                &mut seen,
                "ENVELOPE_ROOT_MISMATCH",
                PociDecision::Challenge,
                "$.evidence_integrity.envelope_root",
                "declared root differs from the independently computed root",
            );
        }
    }

    findings.sort_by(finding_order);
    let primary = findings.first();
    let decision = primary.map_or(PociDecision::Accept, |finding| finding.decision);
    let primary_reason_code = primary.map(|finding| finding.code.clone());
    let reason_codes = findings
        .iter()
        .map(|finding| finding.code.clone())
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect();

    VerificationOutput {
        profile_id: envelope
            .get("protocol")
            .and_then(Value::as_object)
            .and_then(|value| value.get("profile_id"))
            .and_then(Value::as_str)
            .map(ToOwned::to_owned),
        envelope_id: envelope
            .get("envelope_id")
            .and_then(Value::as_str)
            .map(ToOwned::to_owned),
        decision,
        primary_reason_code,
        reason_codes,
        findings,
        computed_envelope_root: computed_root,
        declared_envelope_root: declared_root,
        valid: decision == PociDecision::Accept,
    }
}

pub fn verify_manifest(path: &Path) -> Result<ManifestReport, String> {
    let manifest_value = read_strict_json(path)?;
    let manifest: Manifest = serde_json::from_value(manifest_value)
        .map_err(|error| format!("invalid manifest {}: {error}", path.display()))?;
    let base = path.parent().unwrap_or_else(|| Path::new("."));
    let mut cases = Vec::with_capacity(manifest.cases.len());

    for expected in manifest.cases {
        let fixture_path = base.join(&expected.file);
        let envelope = read_strict_json(&fixture_path)?;
        let actual = verify_envelope(&envelope);
        let passed = actual.decision == expected.expected_decision
            && actual.primary_reason_code == expected.expected_primary_reason_code;

        cases.push(ManifestCaseResult {
            file: expected.file,
            expected_decision: expected.expected_decision,
            actual_decision: actual.decision,
            expected_primary_reason_code: expected.expected_primary_reason_code,
            actual_primary_reason_code: actual.primary_reason_code,
            computed_envelope_root: actual.computed_envelope_root,
            passed,
        });
    }

    let passed = cases.iter().all(|case| case.passed);
    let case_count = cases.len();
    Ok(ManifestReport {
        profile_id: manifest.profile_id,
        fixture_contract_version: manifest.fixture_contract_version,
        cases,
        passed,
        case_count,
    })
}

fn structural_findings(
    envelope: &Value,
    findings: &mut Vec<Finding>,
    seen: &mut BTreeSet<(String, String)>,
) {
    let Some(root) = envelope.as_object() else {
        add_finding(
            findings,
            seen,
            "POCI_SCHEMA_INVALID",
            PociDecision::Block,
            "$",
            "envelope must be a JSON object",
        );
        return;
    };

    let profile = root
        .get("protocol")
        .and_then(Value::as_object)
        .and_then(|value| value.get("profile_id"))
        .and_then(Value::as_str);
    if profile != Some(PROFILE) {
        add_finding(
            findings,
            seen,
            "POCI_PROFILE_UNSUPPORTED",
            PociDecision::Block,
            "$.protocol.profile_id",
            "unsupported profile",
        );
    }

    if !root.contains_key("authority") {
        add_finding(
            findings,
            seen,
            "AUTHORITY_MISSING",
            PociDecision::Block,
            "$.authority",
            "authority section is absent",
        );
    }

    for field in REQUIRED_FIELDS {
        if *field != "authority" && !root.contains_key(*field) {
            add_finding(
                findings,
                seen,
                "POCI_REQUIRED_EVIDENCE_MISSING",
                PociDecision::Block,
                &format!("$.{field}"),
                "required section is absent",
            );
        }
    }

    for field in root.keys() {
        if !TOP_LEVEL_FIELDS.contains(&field.as_str()) {
            add_finding(
                findings,
                seen,
                "POCI_SCHEMA_INVALID",
                PociDecision::Block,
                &format!("$.{field}"),
                "unknown top-level property",
            );
        }
    }

    let schema = root
        .get("protocol")
        .and_then(Value::as_object)
        .and_then(|value| value.get("schema_version"))
        .and_then(Value::as_str);
    if root.get("protocol").is_some() && schema != Some(SCHEMA_VERSION) {
        add_finding(
            findings,
            seen,
            "POCI_SCHEMA_INVALID",
            PociDecision::Block,
            "$.protocol.schema_version",
            "unsupported schema version",
        );
    }

    check_object_type(root, "protocol", findings, seen);
    check_object_type(root, "intent", findings, seen);
    check_object_type(root, "authority", findings, seen);
    check_object_type(root, "causal_context", findings, seen);
    check_object_type(root, "proposal", findings, seen);
    check_object_type(root, "execution", findings, seen);
    check_object_type(root, "observed_result", findings, seen);
    check_object_type(root, "verification", findings, seen);
    check_object_type(root, "evidence_integrity", findings, seen);

    if root.get("witnesses").is_some_and(|value| !value.is_array()) {
        add_finding(
            findings,
            seen,
            "POCI_SCHEMA_INVALID",
            PociDecision::Block,
            "$.witnesses",
            "expected array",
        );
    }

    if !valid_timestamp(root.get("created_at").and_then(Value::as_str)) {
        add_finding(
            findings,
            seen,
            "POCI_SCHEMA_INVALID",
            PociDecision::Block,
            "$.created_at",
            "invalid UTC timestamp",
        );
    }

    if let Some(integrity) = root.get("evidence_integrity").and_then(Value::as_object) {
        if integrity.get("hash_algorithm").and_then(Value::as_str) != Some("sha256") {
            add_finding(
                findings,
                seen,
                "POCI_SCHEMA_INVALID",
                PociDecision::Block,
                "$.evidence_integrity.hash_algorithm",
                "must be sha256",
            );
        }
        if integrity
            .get("canonicalization_profile")
            .and_then(Value::as_str)
            != Some(CANONICALIZATION_PROFILE)
        {
            add_finding(
                findings,
                seen,
                "POCI_SCHEMA_INVALID",
                PociDecision::Block,
                "$.evidence_integrity.canonicalization_profile",
                "unsupported canonicalization profile",
            );
        }
    }

    visit_digest_fields(envelope, "$", findings, seen);
}

fn semantic_findings(
    envelope: &Value,
    findings: &mut Vec<Finding>,
    seen: &mut BTreeSet<(String, String)>,
) {
    let root = envelope.as_object();
    let intent = root
        .and_then(|value| value.get("intent"))
        .and_then(Value::as_object);
    let authority = root
        .and_then(|value| value.get("authority"))
        .and_then(Value::as_object);
    let causal = root
        .and_then(|value| value.get("causal_context"))
        .and_then(Value::as_object);
    let proposal = root
        .and_then(|value| value.get("proposal"))
        .and_then(Value::as_object);
    let execution = root
        .and_then(|value| value.get("execution"))
        .and_then(Value::as_object);
    let observed = root
        .and_then(|value| value.get("observed_result"))
        .and_then(Value::as_object);
    let witnesses = root
        .and_then(|value| value.get("witnesses"))
        .and_then(Value::as_array)
        .map_or(&[][..], Vec::as_slice);

    let evaluation = root
        .and_then(|value| value.get("created_at"))
        .and_then(Value::as_str)
        .unwrap_or("1970-01-01T00:00:00Z");
    let valid_from = intent
        .and_then(|value| value.get("valid_from"))
        .and_then(Value::as_str);
    let expires_at = intent
        .and_then(|value| value.get("expires_at"))
        .and_then(Value::as_str);

    if !valid_timestamp(valid_from)
        || !valid_timestamp(expires_at)
        || valid_from.is_some_and(|start| expires_at.is_some_and(|end| start >= end))
    {
        add_finding(
            findings,
            seen,
            "POCI_SCHEMA_INVALID",
            PociDecision::Block,
            "$.intent",
            "invalid validity interval",
        );
    } else if valid_from.is_some_and(|start| evaluation < start)
        || expires_at.is_some_and(|end| evaluation >= end)
    {
        add_finding(
            findings,
            seen,
            "INTENT_EXPIRED",
            PociDecision::Block,
            "$.intent.expires_at",
            "intent is outside validity window",
        );
    }

    let nonce = intent
        .and_then(|value| value.get("nonce"))
        .and_then(Value::as_str);
    let used_nonces = root
        .and_then(|value| value.get("extensions"))
        .and_then(Value::as_object)
        .and_then(|value| value.get("proofpath.fixture"))
        .and_then(Value::as_object)
        .and_then(|value| value.get("used_nonces"))
        .and_then(Value::as_array);
    if nonce.is_some_and(|candidate| {
        used_nonces
            .is_some_and(|values| values.iter().any(|value| value.as_str() == Some(candidate)))
    }) {
        add_finding(
            findings,
            seen,
            "INTENT_REPLAYED",
            PociDecision::Block,
            "$.intent.nonce",
            "nonce already consumed",
        );
    }

    if let Some(authority) = authority {
        if text(authority, "principal_id") != intent.and_then(|value| text(value, "principal_id")) {
            add_finding(
                findings,
                seen,
                "AUTHORITY_SCOPE_VIOLATION",
                PociDecision::Block,
                "$.authority.principal_id",
                "principal mismatch",
            );
        }
        if text(authority, "agent_id") != proposal.and_then(|value| text(value, "agent_id")) {
            add_finding(
                findings,
                seen,
                "AUTHORITY_SCOPE_VIOLATION",
                PociDecision::Block,
                "$.authority.agent_id",
                "agent mismatch",
            );
        }
        if text(authority, "executor_id") != execution.and_then(|value| text(value, "executor_id"))
        {
            add_finding(
                findings,
                seen,
                "AUTHORITY_SCOPE_VIOLATION",
                PociDecision::Block,
                "$.authority.executor_id",
                "executor mismatch",
            );
        }
        let authority_kind = text(authority, "action_kind");
        if authority_kind != intent.and_then(|value| text(value, "action_kind"))
            || authority_kind != proposal.and_then(|value| text(value, "action_kind"))
        {
            add_finding(
                findings,
                seen,
                "AUTHORITY_SCOPE_VIOLATION",
                PociDecision::Block,
                "$.authority.action_kind",
                "action kind mismatch",
            );
        }

        let allowed_scope = string_set(authority.get("scope"));
        let proposed_scope =
            proposal.map_or_else(BTreeSet::new, |value| string_set(value.get("scope")));
        if !proposed_scope.is_subset(&allowed_scope) {
            add_finding(
                findings,
                seen,
                "AUTHORITY_SCOPE_VIOLATION",
                PociDecision::Block,
                "$.proposal.scope",
                "proposal exceeds authority scope",
            );
        }

        if text(authority, "reversibility") == Some("irreversible")
            && authority.get("approval_required").and_then(Value::as_bool) == Some(true)
            && authority.get("approval_ref").is_none_or(Value::is_null)
        {
            add_finding(
                findings,
                seen,
                "IRREVERSIBLE_APPROVAL_MISSING",
                PociDecision::Block,
                "$.authority.approval_ref",
                "approval evidence is absent",
            );
        }
    }

    if causal
        .and_then(|value| value.get("required"))
        .and_then(Value::as_bool)
        == Some(true)
    {
        let missing = causal.is_none_or(|value| {
            text(value, "parent_type").is_none_or(|kind| kind == "none")
                || value.get("parent_id").is_none_or(Value::is_null)
                || value.get("parent_digest").is_none_or(Value::is_null)
        });
        if missing {
            add_finding(
                findings,
                seen,
                "CAUSAL_PARENT_MISSING",
                PociDecision::Hold,
                "$.causal_context",
                "required causal parent is absent",
            );
        } else if causal
            .and_then(|value| text(value, "relationship"))
            .is_none_or(|relationship| relationship == "none")
        {
            add_finding(
                findings,
                seen,
                "CAUSAL_PARENT_MISMATCH",
                PociDecision::Block,
                "$.causal_context.relationship",
                "parent is non-authorizing",
            );
        }
    }

    if let Some(execution) = execution {
        if text(execution, "proposal_id") != proposal.and_then(|value| text(value, "proposal_id")) {
            add_finding(
                findings,
                seen,
                "PROPOSAL_EXECUTION_MISMATCH",
                PociDecision::Challenge,
                "$.execution.proposal_id",
                "execution is not bound to proposal",
            );
        }
        if text(execution, "status") == Some("succeeded")
            && execution.get("receipt_ref").is_none_or(Value::is_null)
        {
            add_finding(
                findings,
                seen,
                "EXECUTION_RECEIPT_MISSING",
                PociDecision::Block,
                "$.execution.receipt_ref",
                "successful execution lacks receipt",
            );
        }
        let reference_digest = execution
            .get("receipt_ref")
            .and_then(Value::as_object)
            .and_then(|value| text(value, "digest"));
        let claimed_digest = text(execution, "receipt_digest");
        if reference_digest.is_some()
            && claimed_digest.is_some()
            && reference_digest != claimed_digest
        {
            add_finding(
                findings,
                seen,
                "EXECUTION_RECEIPT_DIGEST_MISMATCH",
                PociDecision::Challenge,
                "$.execution.receipt_digest",
                "receipt digests differ",
            );
        }
    }

    if let Some(observed) = observed {
        if text(observed, "status") == Some("observed")
            && observed.get("result_ref").is_none_or(Value::is_null)
        {
            add_finding(
                findings,
                seen,
                "OBSERVED_RESULT_MISSING",
                PociDecision::Block,
                "$.observed_result.result_ref",
                "observed result lacks evidence",
            );
        }
        let reference_digest = observed
            .get("result_ref")
            .and_then(Value::as_object)
            .and_then(|value| text(value, "digest"));
        let claimed_digest = text(observed, "result_digest");
        if reference_digest.is_some()
            && claimed_digest.is_some()
            && reference_digest != claimed_digest
        {
            add_finding(
                findings,
                seen,
                "RESULT_DIGEST_MISMATCH",
                PociDecision::Challenge,
                "$.observed_result.result_digest",
                "result digests differ",
            );
        }
    }

    if witnesses.is_empty() {
        add_finding(
            findings,
            seen,
            "WITNESS_QUORUM_UNMET",
            PociDecision::Hold,
            "$.witnesses",
            "at least one witness is required",
        );
    } else {
        let verdicts = witnesses
            .iter()
            .filter_map(Value::as_object)
            .filter_map(|value| text(value, "verdict"))
            .collect::<BTreeSet<_>>();
        if verdicts.len() > 1 {
            add_finding(
                findings,
                seen,
                "WITNESS_CONFLICT",
                PociDecision::Challenge,
                "$.witnesses",
                "witness verdicts conflict",
            );
        }

        let mut statements: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
        for (index, witness) in witnesses.iter().enumerate() {
            let Some(witness) = witness.as_object() else {
                continue;
            };
            let witness_id = text(witness, "witness_id").unwrap_or("").to_owned();
            let statement_digest = text(witness, "statement_digest").unwrap_or("").to_owned();
            statements
                .entry(witness_id)
                .or_default()
                .insert(statement_digest);

            let reference_digest = witness
                .get("statement_ref")
                .and_then(Value::as_object)
                .and_then(|value| text(value, "digest"));
            if reference_digest.is_some() && reference_digest != text(witness, "statement_digest") {
                add_finding(
                    findings,
                    seen,
                    "ARTIFACT_DIGEST_MISMATCH",
                    PociDecision::Challenge,
                    &format!("$.witnesses[{index}].statement_digest"),
                    "witness statement digests differ",
                );
            }
        }
        if statements.values().any(|values| values.len() > 1) {
            add_finding(
                findings,
                seen,
                "WITNESS_EQUIVOCATION",
                PociDecision::Challenge,
                "$.witnesses",
                "witness identity equivocated",
            );
        }
    }

    let committed = artifact_map(envelope);
    check_artifact_reference(
        "$.intent.signature_ref",
        intent.and_then(|value| value.get("signature_ref")),
        &committed,
        findings,
        seen,
    );
    check_artifact_reference(
        "$.execution.receipt_ref",
        execution.and_then(|value| value.get("receipt_ref")),
        &committed,
        findings,
        seen,
    );
    check_artifact_reference(
        "$.observed_result.result_ref",
        observed.and_then(|value| value.get("result_ref")),
        &committed,
        findings,
        seen,
    );
    for (index, witness) in witnesses.iter().enumerate() {
        check_artifact_reference(
            &format!("$.witnesses[{index}].statement_ref"),
            witness
                .as_object()
                .and_then(|value| value.get("statement_ref")),
            &committed,
            findings,
            seen,
        );
    }
}

fn check_object_type(
    root: &Map<String, Value>,
    field: &str,
    findings: &mut Vec<Finding>,
    seen: &mut BTreeSet<(String, String)>,
) {
    if root.get(field).is_some_and(|value| !value.is_object()) {
        add_finding(
            findings,
            seen,
            "POCI_SCHEMA_INVALID",
            PociDecision::Block,
            &format!("$.{field}"),
            "expected object",
        );
    }
}

fn visit_digest_fields(
    value: &Value,
    path: &str,
    findings: &mut Vec<Finding>,
    seen: &mut BTreeSet<(String, String)>,
) {
    match value {
        Value::Object(object) => {
            for (key, child) in object {
                let child_path = format!("{path}.{key}");
                if (key == "digest" || key.ends_with("_digest"))
                    && !child.is_null()
                    && child.as_str().is_none_or(|digest| !valid_digest(digest))
                {
                    add_finding(
                        findings,
                        seen,
                        "POCI_SCHEMA_INVALID",
                        PociDecision::Block,
                        &child_path,
                        "invalid digest format",
                    );
                }
                visit_digest_fields(child, &child_path, findings, seen);
            }
        }
        Value::Array(values) => {
            for (index, child) in values.iter().enumerate() {
                visit_digest_fields(child, &format!("{path}[{index}]"), findings, seen);
            }
        }
        _ => {}
    }
}

fn artifact_map(envelope: &Value) -> BTreeMap<String, String> {
    envelope
        .get("evidence_integrity")
        .and_then(Value::as_object)
        .and_then(|value| value.get("artifacts"))
        .and_then(Value::as_array)
        .map_or_else(BTreeMap::new, |artifacts| {
            artifacts
                .iter()
                .filter_map(Value::as_object)
                .filter_map(|artifact| {
                    Some((
                        text(artifact, "artifact_id")?.to_owned(),
                        text(artifact, "digest")?.to_owned(),
                    ))
                })
                .collect()
        })
}

fn check_artifact_reference(
    path: &str,
    raw: Option<&Value>,
    committed: &BTreeMap<String, String>,
    findings: &mut Vec<Finding>,
    seen: &mut BTreeSet<(String, String)>,
) {
    let reference = raw.and_then(Value::as_object);
    let artifact_id = reference.and_then(|value| text(value, "artifact_id"));
    let digest = reference.and_then(|value| text(value, "digest"));
    if let (Some(artifact_id), Some(digest)) = (artifact_id, digest) {
        if committed.get(artifact_id).map(String::as_str) != Some(digest) {
            add_finding(
                findings,
                seen,
                "ARTIFACT_DIGEST_MISMATCH",
                PociDecision::Challenge,
                path,
                "artifact commitment is missing or different",
            );
        }
    }
}

fn text<'a>(object: &'a Map<String, Value>, field: &str) -> Option<&'a str> {
    object.get(field).and_then(Value::as_str)
}

fn string_set(value: Option<&Value>) -> BTreeSet<String> {
    value
        .and_then(Value::as_array)
        .map_or_else(BTreeSet::new, |values| {
            values
                .iter()
                .filter_map(Value::as_str)
                .map(ToOwned::to_owned)
                .collect()
        })
}

fn valid_timestamp(value: Option<&str>) -> bool {
    let Some(value) = value else {
        return false;
    };
    let bytes = value.as_bytes();
    bytes.len() == 20
        && bytes[4] == b'-'
        && bytes[7] == b'-'
        && bytes[10] == b'T'
        && bytes[13] == b':'
        && bytes[16] == b':'
        && bytes[19] == b'Z'
        && bytes.iter().enumerate().all(|(index, byte)| {
            matches!(index, 4 | 7 | 10 | 13 | 16 | 19) || byte.is_ascii_digit()
        })
}

fn valid_digest(value: &str) -> bool {
    value.len() == 71
        && value.starts_with("sha256:")
        && value[7..]
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn add_finding(
    findings: &mut Vec<Finding>,
    seen: &mut BTreeSet<(String, String)>,
    code: &str,
    decision: PociDecision,
    path: &str,
    message: &str,
) {
    let identity = (code.to_owned(), path.to_owned());
    if seen.insert(identity) {
        findings.push(Finding {
            code: code.to_owned(),
            decision,
            path: path.to_owned(),
            message: message.to_owned(),
        });
    }
}

fn reason_priority(code: &str) -> u16 {
    match code {
        "POCI_PROFILE_UNSUPPORTED" => 10,
        "AUTHORITY_MISSING" => 20,
        "POCI_REQUIRED_EVIDENCE_MISSING" => 30,
        "POCI_SCHEMA_INVALID" => 40,
        "INTENT_EXPIRED" => 100,
        "INTENT_REPLAYED" => 110,
        "AUTHORITY_SCOPE_VIOLATION" => 130,
        "IRREVERSIBLE_APPROVAL_MISSING" => 150,
        "CAUSAL_PARENT_MISMATCH" => 200,
        "CAUSAL_PARENT_MISSING" => 210,
        "PROPOSAL_EXECUTION_MISMATCH" => 300,
        "EXECUTION_RECEIPT_MISSING" => 310,
        "EXECUTION_RECEIPT_DIGEST_MISMATCH" => 320,
        "OBSERVED_RESULT_MISSING" => 330,
        "RESULT_DIGEST_MISMATCH" => 340,
        "WITNESS_CONFLICT" => 400,
        "WITNESS_EQUIVOCATION" => 410,
        "WITNESS_QUORUM_UNMET" => 420,
        "ENVELOPE_ROOT_MISMATCH" => 430,
        "ARTIFACT_DIGEST_MISMATCH" => 440,
        "VERIFIER_INTERNAL_FAIL_CLOSED" => 999,
        _ => 500,
    }
}

fn finding_order(left: &Finding, right: &Finding) -> std::cmp::Ordering {
    right
        .decision
        .rank()
        .cmp(&left.decision.rank())
        .then_with(|| reason_priority(&left.code).cmp(&reason_priority(&right.code)))
        .then_with(|| left.code.cmp(&right.code))
        .then_with(|| left.path.cmp(&right.path))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture_root() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../examples/poci-witness/fixtures")
    }

    #[test]
    fn poci_manifest_matches_all_committed_cases() {
        let report =
            verify_manifest(&fixture_root().join("manifest.json")).expect("manifest should verify");
        assert!(report.passed);
        assert_eq!(report.case_count, 12);
    }

    #[test]
    fn poci_valid_fixture_is_deterministic() {
        let envelope = read_strict_json(&fixture_root().join("valid-action.accept.json"))
            .expect("valid fixture should parse");
        let first = verify_envelope(&envelope);
        let second = verify_envelope(&envelope);
        assert_eq!(first, second);
        assert_eq!(first.decision, PociDecision::Accept);
        assert!(first.computed_envelope_root.is_some());
    }

    #[test]
    fn poci_rejects_duplicate_json_keys() {
        let error =
            parse_strict_json(r#"{"a":1,"a":2}"#).expect_err("duplicate keys must fail closed");
        assert!(error.contains("duplicate JSON key"));
    }

    #[test]
    fn poci_ignores_embedded_verdict_as_authority() {
        let mut envelope = read_strict_json(&fixture_root().join("valid-action.accept.json"))
            .expect("valid fixture should parse");
        envelope["verification"]["decision"] = Value::String("BLOCK".to_owned());
        envelope["verification"]["primary_reason_code"] =
            Value::String("AUTHORITY_MISSING".to_owned());
        let result = verify_envelope(&envelope);
        assert_eq!(result.decision, PociDecision::Accept);
    }
}

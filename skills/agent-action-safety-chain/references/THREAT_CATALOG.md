# Threat Catalog

## Authority failures

- Missing declared intent.
- Missing or forged causal parent.
- Scope escalation.
- Irreversible action without approval.
- Model-generated rationale treated as authorization.
- Expired or revoked authority.

## Replay and concurrency

- Missing nonce.
- Reused nonce.
- Race between evaluation and nonce consumption.
- Retry after partial side effect.
- Replay overwriting the original evidence bundle.

## Data movement

- Secret access followed by network egress.
- Unknown or unapproved destination.
- Network action hidden behind an unusual action name.
- Sensitive content inferred from metadata but not marked.
- Allow-list matching that ignores canonical host normalization.

## Evidence integrity

- Path traversal through trace or span identifiers.
- Symlink or unlisted-file injection.
- Manifest missing an evidence role.
- Modified evidence after manifest generation.
- Hash chain discontinuity.
- Authorization and observation collapsed into one status.
- Missing evidence after executor failure.

## Claim risks

- Calling a guard a sandbox.
- Calling synthetic tests a security audit.
- Claiming vendor endorsement.
- Reporting detection metrics without fixtures and commands.
- Treating a provider correlation ID as causal authorization.

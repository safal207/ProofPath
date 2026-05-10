use proofpath_verifier::{verify, RequestContext};
use std::{env, error::Error, fs};

fn main() -> Result<(), Box<dyn Error>> {
    let Some(path) = env::args().nth(1) else {
        eprintln!("usage: proofpath-verify <request.http>");
        std::process::exit(2);
    };

    let raw = fs::read_to_string(path)?;
    let ctx = parse_http_headers(&raw);
    let result = verify(&ctx);

    println!("{}", serde_json::to_string_pretty(&result)?);

    Ok(())
}

fn parse_http_headers(raw: &str) -> RequestContext {
    let mut ctx = RequestContext::new();

    for line in raw.lines().skip(1) {
        let trimmed = line.trim_end();

        if trimmed.is_empty() {
            break;
        }

        if let Some((name, value)) = trimmed.split_once(':') {
            ctx = ctx.with_header(name.trim(), value.trim());
        }
    }

    ctx
}

#[cfg(test)]
mod tests {
    use super::parse_http_headers;
    use proofpath_verifier::{verify, Decision, HEADER_INTENT_ID};

    #[test]
    fn parses_basic_http_headers() {
        let raw = "POST /x HTTP/1.1\nHost: example.test\nx-proofpath-intent-id: intent_1\n\n{}";
        let ctx = parse_http_headers(raw);

        assert_eq!(ctx.header(HEADER_INTENT_ID), Some("intent_1"));
    }

    #[test]
    fn cli_parser_output_can_be_verified() {
        let raw = "POST /x HTTP/1.1\n\
x-proofpath-intent-id: intent_1\n\
x-proofpath-causal-parent: decision_1\n\
x-proofpath-scope: profile.update\n\
x-proofpath-reversibility: reversible\n\
\n{}";
        let ctx = parse_http_headers(raw);
        let result = verify(&ctx);

        assert_eq!(result.decision, Decision::Accept);
    }
}

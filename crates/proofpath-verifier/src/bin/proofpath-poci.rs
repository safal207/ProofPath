#[path = "../poci.rs"]
mod poci;

use poci::{read_strict_json, verify_envelope, verify_manifest, PociDecision};
use serde::Serialize;
use std::env;
use std::error::Error;
use std::path::PathBuf;

#[derive(Debug)]
struct Arguments {
    path: PathBuf,
    manifest: bool,
    pretty: bool,
    allow_non_accept: bool,
}

fn parse_arguments() -> Result<Arguments, String> {
    let mut values = env::args().skip(1);
    let path = values.next().ok_or_else(|| {
        "usage: proofpath-poci <path.json> [--manifest] [--pretty] [--allow-non-accept]"
            .to_owned()
    })?;
    let mut arguments = Arguments {
        path: PathBuf::from(path),
        manifest: false,
        pretty: false,
        allow_non_accept: false,
    };

    for value in values {
        match value.as_str() {
            "--manifest" => arguments.manifest = true,
            "--pretty" => arguments.pretty = true,
            "--allow-non-accept" => arguments.allow_non_accept = true,
            _ => return Err(format!("unknown argument: {value}")),
        }
    }

    Ok(arguments)
}

fn print_json<T: Serialize>(value: &T, pretty: bool) -> Result<(), serde_json::Error> {
    if pretty {
        println!("{}", serde_json::to_string_pretty(value)?);
    } else {
        println!("{}", serde_json::to_string(value)?);
    }
    Ok(())
}

fn main() -> Result<(), Box<dyn Error>> {
    let arguments = parse_arguments().map_err(|error| {
        eprintln!("{error}");
        error
    })?;

    if arguments.manifest {
        let report = verify_manifest(&arguments.path)?;
        print_json(&report, arguments.pretty)?;
        if !report.passed {
            std::process::exit(1);
        }
        return Ok(());
    }

    let envelope = read_strict_json(&arguments.path)?;
    let output = verify_envelope(&envelope);
    let decision = output.decision;
    print_json(&output, arguments.pretty)?;

    if !arguments.allow_non_accept && decision != PociDecision::Accept {
        std::process::exit(decision.exit_code());
    }

    Ok(())
}

"""Verify recovery control on freshly emitted production and mutated models."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tools"))
from formal import concrete_witnesses, validate_job

DEPTH = 90  # Includes the locked warm reboot and subsequent upload attempts at edges 77/79.
LIMIT = 120
SCOPES = {
    "safety": "Unbounded control safety at 2048-byte program and 1024-byte working capacity, arbitrary frame and memory inputs",
    "accounting": "Bounded 90 service edges, one four-byte image, two possible data words, four delayed completion choices",
}


def execute(argv, log, timeout):
    start = time.monotonic()
    with log.open("w") as stream:
        result = subprocess.run(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
    return {"command": list(map(str, argv)), "returncode": result.returncode,
            "seconds": time.monotonic() - start, "log": log.relative_to(ROOT).as_posix()}


def job(role, variant, output):
    directory = output / role
    sources = sorted((directory / "emit" / variant).glob("*.sv"))
    if not sources:
        raise RuntimeError(f"No emitted sources for {role}/{variant}")
    cover = variant == "cover"
    negative = variant == "corrupt"
    unbounded = role == "safety" and variant == "correct"
    mode = "cover" if cover else "prove" if unbounded else "bmc"
    engine = "smtbmc yices" if unbounded else "btor btormc"
    cells = (3 if role == "safety" else 2) if cover else (2 if unbounded else 1)
    depth = 36 if unbounded else DEPTH  # Includes 32 CRC edges from admission to request.
    names = " ".join(source.name for source in sources)
    script = directory / f"{variant}.sby"
    script.write_text("\n".join([
        "[options]", f"mode {mode}", f"depth {depth}", f"timeout {LIMIT}",
        "", "[engines]", engine, "", "[script]",
        f"read_slang --top RecoveryFormal {names}", "prep -top RecoveryFormal -flatten",
        "fminit -seq por_n 0,'z", "async2sync", "chformal -lower",
        f"select -assert-count {cells} t:$" + ("cover" if cover else "assert"),
        "", "[files]", *map(str, sources), "",
    ]))
    destination = directory / variant
    row = execute(["sby", "-d", str(destination), str(script)], directory / f"{variant}.log", LIMIT + 60)
    row.update(id=f"T18-{role.upper()}-{variant.upper()}", mode=mode, engine=engine, depth=depth,
               source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    status = destination / "status"
    row["solver_status"] = status.read_text().split()[0] if status.is_file() else "ERROR"
    try:
        validate_job(destination, "cover" if cover else "negative" if negative else "proof",
                     row["returncode"], row["solver_status"])
    except RuntimeError as error:
        row.update(status="failed", error=str(error))
    else:
        row["status"] = "covered" if cover else "fault_rejected" if negative else "proved" if unbounded else "bounded"
        row["witnesses"] = [p.relative_to(ROOT).as_posix() for p in concrete_witnesses(destination)]
    return row


def run(output):
    output = Path(output).resolve()
    output.relative_to(ROOT / "build")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a fresh output directory")
    output.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    receipt = dict(task="T18", status="running", cases={}, deferred=[], timeout_seconds=LIMIT,
                   qualification_limits=list(SCOPES.values()),
                   assumptions=["POR initially asserted, then arbitrary; one qualified digital clock",
                                "Completed frames presented at control boundary; pin and CDC behavior tested separately",
                                "Cover/fault witnesses and bounded accounting use one scripted four-byte image, no fairness assumption"])
    try:
        emission = execute([sys.executable, "tools/sbt.py",
                            f"hw/runMain deadhorse.i2c_recovery_loader.EmitRecoveryFormal {output}"],
                           output / "emit.log", 600)
        receipt["emission"] = emission
        if emission["returncode"]:
            raise RuntimeError("Formal emission failed")
        for role, scope in SCOPES.items():
            case = dict(scope=scope, jobs=[])
            receipt["cases"][role] = case
            for variant in ("cover", "corrupt", "correct"):
                row = job(role, variant, output)
                case["jobs"].append(row)
                print(f"{row['id']}: {row['status']}", flush=True)
                if row["status"] == "failed":
                    raise RuntimeError(f"{row['id']}: {row['solver_status']} (exit {row['returncode']})")
            case["status"] = "pass"
        receipt["status"] = "pass"
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        receipt.update(status="failed", error=str(error))
    receipt["seconds"] = time.monotonic() - start
    (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    result = run(ROOT / parser.parse_args().output)
    print(result["status"].upper() + " T18 recovery formal")
    sys.exit(0 if result["status"] == "pass" else 1)

"""Run T18 adoption, wire-to-memory simulation, production timing and formal acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

from provenance import validate as validate_provenance

BLOCK = Path(__file__).resolve().parent
ROOT = BLOCK.parents[2]
SUITES = {"RecoveryWireSpec", "RecoveryLoaderSpec"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs():
    paths = [
        ROOT / "build.sbt", ROOT / "docs/spec/i2c-recovery-loader.md", ROOT / "tools/env/lock.json",
        ROOT / "tools/sbt.py", ROOT / "tools/formal.py", BLOCK / "LICENSE",
    ]
    for directory in (BLOCK, ROOT / "hw/lib/src/main/scala", ROOT / "tools/timing"):
        paths.extend(p for p in directory.rglob("*") if p.suffix in {".py", ".scala", ".json", ".md", ".tcl"})
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in sorted(set(paths))}


def simulation_result(log):
    """Require successful cases in each expected suite from this invocation's own log."""
    observed = {}
    suite = None
    for line in log.splitlines():
        header = re.fullmatch(r"\[info\] (\w+Spec):", line)
        if header:
            suite = header.group(1)
            observed[suite] = 0
        elif line.startswith("[info] - ") and suite:
            observed[suite] += 1
    count = sum(observed.values())
    summary = f"Tests: succeeded {count}, failed 0, canceled 0, ignored 0, pending 0"
    if (not SUITES.issubset(observed) or not all(observed.values()) or
            summary not in log or "[info] All tests passed." not in log):
        raise ValueError(f"Incomplete T18 wire/integration simulation: {observed}")
    return observed


def validate_formal(detail, directory):
    if detail.get("task") != "T18" or set(detail["cases"]) != {"safety", "accounting"}:
        raise ValueError("Incomplete formal receipt")
    for role, case in detail["cases"].items():
        correct = "proved" if role == "safety" else "bounded"
        expected = {"cover": ("covered", "PASS", 0), "corrupt": ("fault_rejected", "FAIL", 2),
                    "correct": (correct, "PASS", 0)}
        jobs = case["jobs"]
        if case.get("status") != "pass" or len(jobs) != len(expected):
            raise ValueError(f"Incomplete formal obligations for {role}")
        for job in jobs:
            variant = job["id"].split("-")[-1].lower()
            if (job["id"] != f"T18-{role.upper()}-{variant.upper()}" or
                    expected.pop(variant, None) != (job["status"], job["solver_status"], job["returncode"])):
                raise ValueError(f"Unexpected formal outcome: {job['id']}")
            sources = {p.name: digest(p) for p in (directory / role / "emit" / variant).glob("*.sv")}
            if not sources or sources != job["source_sha256"]:
                raise ValueError(f"Formal emission mismatch: {job['id']}")


def run(output):
    output = Path(output).resolve()
    output.relative_to(ROOT / "build")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a fresh output directory; preserve prior T18 evidence")
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    receipt = dict(task="T18", status="running", deferred=[], commands=[], source_sha256=inputs(),
                   commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                   qualification_limits=[
                       "Standalone lite recovery path through the program-memory port. SRAM, boot ROM, QSPI, CPU and board pads are external.",
                       "Digital wake uses a qualified active clock. Oscillator startup, clock distribution and physical pin timing require integration.",
                   ])

    def command(name, args, child=None):
        argv = list(map(str, args))
        log = output / (name + ".log")
        row = dict(name=name, command=argv, log=log.relative_to(ROOT).as_posix())
        receipt["commands"].append(row)
        before = time.monotonic()
        try:
            with log.open("w") as stream:
                process = subprocess.run(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=1800)
            row["returncode"] = process.returncode
        finally:
            row["seconds"] = time.monotonic() - before
        if process.returncode:
            raise RuntimeError(f"{name} exited {process.returncode}, see {row['log']}")
        if child:
            detail = json.loads(child.read_text())
            row.update(child_status=detail.get("status"), receipt=dict(
                path=child.relative_to(ROOT).as_posix(), sha256=digest(child)))
            if detail.get("status") != "pass" or detail.get("deferred"):
                raise ValueError(f"{name} did not pass all required checks")
            return detail

    python = sys.executable
    try:
        # Normal acceptance works from the distributed source tree. When available,
        # additionally authenticate the mapping against the original Git tree.
        reference = ROOT / "build/riscay-mcu"
        receipt["provenance"] = validate_provenance(upstream=reference if (reference / ".git").exists() else None)
        command("simulation", [python, "tools/sbt.py", "hw/testOnly deadhorse.i2c_recovery_loader.*"])
        receipt["simulation"] = simulation_result((output / "simulation.log").read_text())
        emitted = output / "emit"
        command("emit", [python, "tools/sbt.py", f"hw/runMain deadhorse.i2c_recovery_loader.EmitRecoveryLoader {emitted}"])
        sources = sorted(emitted.glob("*.sv"))
        if not (emitted / "RecoveryLoader.sv").is_file():
            raise ValueError("Production RecoveryLoader emission missing")
        timing_dir = output / "timing"
        timing_args = [python, "tools/timing/check.py", "--top", "RecoveryLoader", "--clock", "clk",
                       "--output", timing_dir]
        for source in sources:
            timing_args.extend(["--source", source])
        timing = command("timing", timing_args, timing_dir / "result.json")
        measured_sources = {p.relative_to(ROOT).as_posix(): digest(p) for p in sources}
        if (timing["source_sha256"] != measured_sources or timing["top"] != "RecoveryLoader" or
                timing["role"] != "production" or timing["operating_point"] != "default"):
            raise ValueError("Timing receipt does not match production emission and default T09 conditions")
        receipt["timing"] = timing
        formal_dir = output / "formal"
        formal = command("formal", [python, BLOCK / "formal/check.py", "--output", formal_dir],
                         formal_dir / "result.json")
        validate_formal(formal, formal_dir)
        receipt["formal"] = formal
        receipt["qualification_limits"].extend(formal["qualification_limits"])
        if inputs() != receipt["source_sha256"]:
            raise RuntimeError("Sources changed during T18 acceptance")
        receipt["status"] = "pass"
    except Exception as error:
        receipt.update(status="failed", error=str(error))
        print(str(error), file=sys.stderr)
    receipt["seconds"] = time.monotonic() - started
    (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(f'{receipt["status"].upper()} T18 recovery loader, {receipt["seconds"]:.3f}s', flush=True)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    sys.exit(0 if run(ROOT / args.output)["status"] == "pass" else 1)

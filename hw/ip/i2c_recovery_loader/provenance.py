"""Validate the T18 adoption manifest; an existing local T06 clone allows a full Git audit."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

BLOCK = Path(__file__).resolve().parent
PIN = "4671317186003740ceb61360ba08c59bbdf10136"


def validate(block=BLOCK, upstream=None):
    manifest = json.loads((block / "provenance.json").read_text())
    if (manifest["commit"], manifest["license"]) != (PIN, "Apache-2.0"):
        raise ValueError("Unexpected upstream revision or licence")
    seen = set()
    destinations = set()
    for row in manifest["files"]:
        source, blob = row["source"], row["blob"]
        if source in seen or not re.fullmatch("[0-9a-f]{40}", blob) or not row["changes"].strip():
            raise ValueError(f"Invalid upstream entry: {source}")
        seen.add(source)
        if upstream is not None:
            actual = subprocess.check_output(
                ["git", "-C", str(upstream), "rev-parse", "--verify", f"{PIN}:{source}"],
                text=True,
            ).strip()
            if actual != blob:
                raise ValueError(f"Wrong pinned Git blob for {source}")
        for name in row["destinations"]:
            dest = (block / name).resolve()
            dest.relative_to(block.resolve())
            content = dest.read_bytes().replace(b"\r\n", b"\n")
            if source == "LICENSE":
                header = f"blob {len(content)}\0".encode()
                if name != "LICENSE" or hashlib.sha1(header + content).hexdigest() != blob:
                    raise ValueError("Copied licence differs from the pinned Git blob")
            elif b"SPDX-License-Identifier: Apache-2.0" not in content.splitlines()[0]:
                raise ValueError(f"Missing upstream licence identifier on {name}")
            destinations.add(name)
    expected = {"ClockedI2cTarget.scala", "LoaderControl.scala", "RecoveryLoader.scala", "LICENSE"}
    if {Path(name).name for name in destinations} != expected:
        raise ValueError("Incomplete adapted-file destination inventory")
    return dict(upstream_commit=PIN, upstream_blobs_checked=upstream is not None,
                files=len(seen), destinations=sorted(destinations))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, help="Optional local Git clone for verifying source blobs")
    args = parser.parse_args()
    print(json.dumps(validate(upstream=args.upstream), indent=2))

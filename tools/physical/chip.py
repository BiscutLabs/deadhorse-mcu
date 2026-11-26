"""Run one explicit T38 physical stage in the pinned wafer.space environment.

This runner records raw tool status; a completed flow is not timing/signoff
acceptance. Use chip_prepare/chip_constraints first. Never run aggregate CI.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True)
    p.add_argument('--state', required=True)
    p.add_argument('--from-step', required=True)
    p.add_argument('--to-step', required=True)
    p.add_argument('--tag', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--preserve-graph', action='store_true',
                   help='Use authenticated T38 wrappers for CTS and timing repair')
    a = p.parse_args()
    out = (ROOT / a.output).resolve()
    out.relative_to(ROOT / 'build')
    out.mkdir(parents=True, exist_ok=False)
    cfg, state = [(ROOT / v).resolve() for v in (a.config, a.state)]
    command = ['librelane', '--manual-pdk', '--pdk', 'gf180mcuD', '--scl',
               'gf180mcu_fd_sc_mcu7t5v0', '--pdk-root', str(ROOT / 'build/t43/pdk-candidate'),
               '--run-tag', a.tag, '--with-initial-state', str(state),
               '--from', a.from_step, '--to', a.to_step, str(cfg)]
    if a.preserve_graph:
        command = [sys.executable, str(ROOT / 'tools/physical/chip_flow.py'),
                   '--flow', 'T38Chip', *command[1:]]
    hashes = {str(q.relative_to(ROOT)): hashlib.sha256(q.read_bytes()).hexdigest()
              for q in [Path(__file__), cfg, state]}
    if a.preserve_graph:
        wrapper = ROOT / 'tools/physical/chip_flow.py'
        hashes[str(wrapper.relative_to(ROOT))] = hashlib.sha256(wrapper.read_bytes()).hexdigest()
    started = time.monotonic()
    with (out / 'flow.log').open('w') as stream:
        run = subprocess.run(command, cwd=cfg.parent, stdout=stream, stderr=subprocess.STDOUT)
    result = dict(status='flow_completed_unqualified' if run.returncode == 0 else 'failed',
        command=command, seconds=time.monotonic() - started, returncode=run.returncode,
        input_sha256=hashes, scope='Pre-scan physical measurement; independent timing/coverage and signoff checks remain separate')
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    raise SystemExit(run.returncode)


if __name__ == '__main__':
    main()

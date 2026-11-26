"""Four-edge LF readiness: digital proof, cover and an early-ready fault.

This does not establish the analog initializer's reset premise.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from tools.formal import assertion_names, validate_job


def main(output):
    out = (ROOT / output).resolve()
    out.relative_to(ROOT / 'build')
    out.mkdir(parents=True, exist_ok=False)
    paths = [ROOT / name for name in (
        'hw/ip/osc_ctrl/formal/lf_ready_check.py',
        'hw/ip/osc_ctrl/formal/LfReadyFormal.scala',
        'hw/ip/osc_ctrl/src/main/scala/deadhorse/osc_ctrl/AnalogPhysical.scala',
        'hw/lib/src/main/scala/deadhorse/lib/Cdc.scala',
        'tools/formal.py', 'tools/env/lock.json')]
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    hashes = lambda: {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}
    receipt = dict(status='running', source_sha256=hashes(), jobs=[],
        commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        assumptions=['power_n is low initially; thereafter power_n and enable are arbitrary'],
        scope='Digital readiness only; analog initialization and cell timing remain physical obligations')

    def run(command, name, cap=180):
        start = time.monotonic()
        with (out / (name + '.log')).open('w') as log:
            try:
                code = subprocess.run(command, cwd=ROOT, stdout=log,
                    stderr=subprocess.STDOUT, timeout=cap).returncode
            except subprocess.TimeoutExpired:
                code = 124
        return dict(command=command, returncode=code, seconds=time.monotonic()-start)

    try:
        receipt['emission'] = run([sys.executable, 'tools/sbt.py',
            'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/osc_ctrl/formal")',
            f'hw/runMain deadhorse.osc_ctrl.EmitLfReadyFormal {out}/emit'], 'emit')
        if receipt['emission']['returncode']:
            raise RuntimeError('Emission failed')
        for name, mode, variant in [('correct', 'prove', 'correct'),
                                     ('reachable', 'cover', 'correct'),
                                     ('early', 'bmc', 'early')]:
            sources = sorted((out / 'emit' / variant).glob('*.sv'))
            if not sources:
                raise RuntimeError('Missing emitted model')
            engine = 'abc pdr' if mode == 'prove' else 'btor btormc'
            job = out / (name + '.sby')
            job.write_text('\n'.join(['[options]', f'mode {mode}', 'depth 12', 'timeout 120',
                '[engines]', engine, '[script]',
                'read_slang --top LfReadyFormal ' + ' '.join(p.name for p in sources),
                'prep -top LfReadyFormal -flatten', "fminit -seq power_n 0,'z",
                'async2sync', 'chformal -lower', 'select -assert-count 2 t:$assert',
                'select -assert-count 1 t:$assume', 'select -assert-count 1 t:$cover',
                '[files]', *map(str, sources), '']))
            row = run(['sby', '-d', str(out / name), str(job)], name)
            status_path = out / name / 'status'
            status = status_path.read_text().split()[0] if status_path.exists() else 'ERROR'
            row.update(name=name, mode=mode, engine=engine, solver_status=status,
                model_sha256={p.name: sha(p) for p in sources})
            receipt['jobs'].append(row)
            row['failed_properties'] = validate_job(out / name,
                'negative' if mode == 'bmc' else 'proof' if mode == 'prove' else 'cover',
                row['returncode'], status, {assertion_names(2)[0]} if mode == 'bmc' else None)
            row['status'] = 'proved' if mode == 'prove' else 'covered' if mode == 'cover' else 'fault_rejected'
            print(name, row['status'], flush=True)
        if hashes() != receipt['source_sha256']:
            raise RuntimeError('Sources changed during checks')
        receipt['status'] = 'pass'
    except Exception as error:
        receipt.update(status='failed', error=str(error))
    receipt['artifact_sha256'] = {p.relative_to(out).as_posix(): sha(p)
        for p in out.rglob('*') if p.is_file() and p != out / 'result.json'}
    (out / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(receipt['status'].upper(), receipt.get('error', ''), flush=True)
    return 0 if receipt['status'] == 'pass' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    sys.exit(main(parser.parse_args().output))

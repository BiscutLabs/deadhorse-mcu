"""PLAN04 AON policy proofs; source-clock/reset composition remains separate."""
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
    paths = [p for parent in ('hw/lib', 'hw/ip/osc_ctrl') for p in (ROOT / parent).rglob('*')
             if p.is_file() and p.suffix in ('.scala', '.py', '.yaml')]
    paths += [ROOT / p for p in ('build.sbt', 'tools/sbt.py', 'tools/formal.py', 'tools/env/lock.json')]
    def hashes():
        return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    receipt = dict(status='running', source_sha256=hashes(), jobs=[],
                   assumptions=['Initial reset asserted; thereafter reset and all policy inputs arbitrary; one AON clock'],
                   scope='AON sequencer safety only; not source-clock, reset, straps or analog qualification',
                   commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip())
    def run(argv, log, cap=180):
        start = time.monotonic()
        with log.open('w') as f:
            try:
                code = subprocess.run(argv, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, timeout=cap).returncode
            except subprocess.TimeoutExpired:
                code = 124
        return dict(command=argv, returncode=code, seconds=time.monotonic()-start,
                    log=log.relative_to(out).as_posix())
    try:
        emission = run([sys.executable, 'tools/sbt.py',
                        'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/osc_ctrl/formal")',
                        f'hw/runMain deadhorse.osc_ctrl.EmitOscFormal {out}/emit'], out / 'emit.log')
        receipt['emission'] = emission
        if emission['returncode']:
            raise RuntimeError('Emission failed')
        for variant in ('correct', 'wake', 'gate', 'early_gate', 'reset', 'hold', 'cover'):
            mode = 'prove' if variant == 'correct' else 'cover' if variant == 'cover' else 'bmc'
            engine = 'abc pdr' if mode == 'prove' else 'btor btormc'
            sources = sorted((out / 'emit' / variant).glob('*.sv'))
            if not sources:
                raise RuntimeError('Missing emitted model')
            job = out / (variant + '.sby')
            job.write_text('\n'.join(['[options]', f'mode {mode}', 'depth 24', 'timeout 120',
                '[engines]', engine, '[script]',
                'read_slang --top OscFormal ' + ' '.join(p.name for p in sources),
                'prep -top OscFormal -flatten', "fminit -seq reset_n 0,'z", 'async2sync', 'chformal -lower',
                f'select -assert-count {4 if mode == "cover" else 6} t:$' + ('cover' if mode == 'cover' else 'assert'),
                'select -assert-count 1 t:$assume', '[files]', *map(str, sources), '']))
            row = run(['sby', '-d', str(out / variant), str(job)], out / (variant + '.log'))
            status_path = out / variant / 'status'
            status = status_path.read_text().split()[0] if status_path.exists() else 'ERROR'
            row.update(variant=variant, mode=mode, engine=engine, solver_status=status,
                       model_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
            receipt['jobs'].append(row)
            if status == 'TIMEOUT':
                row['status'] = 'unresolved'
            else:
                fault = {'wake': {assertion_names(6)[2]}, 'gate': {assertion_names(6)[4]},
                         'early_gate': {assertion_names(6)[1],assertion_names(6)[5]},
                         'reset': {assertion_names(6)[5]}, 'hold': {assertion_names(6)[0]}}.get(variant)
                row['failed_properties'] = validate_job(out / variant,
                    'proof' if mode == 'prove' else 'cover' if mode == 'cover' else 'negative',
                    row['returncode'], status, fault)
                row['status'] = 'proved' if mode == 'prove' else 'covered' if mode == 'cover' else 'fault_rejected'
            print(variant, row['status'], flush=True)
        if hashes() != receipt['source_sha256']:
            raise RuntimeError('Proof sources changed during run')
        receipt['status'] = 'unresolved' if any(r['status'] == 'unresolved' for r in receipt['jobs']) else 'pass'
    except Exception as error:
        receipt.update(status='failed', error=str(error))
    receipt['artifact_sha256'] = {p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob('*') if p.is_file() and p != out / 'result.json'}
    (out / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(receipt['status'].upper(), receipt.get('error', ''))
    return 0 if receipt['status'] == 'pass' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--policy-only', action='store_true',
                        help='Run only AON policy safety, not PLAN04 formal acceptance')
    args = parser.parse_args()
    if not args.policy_only:
        parser.error('Full PLAN04 composition is not implemented; --policy-only is a partial diagnostic')
    sys.exit(main(args.output))

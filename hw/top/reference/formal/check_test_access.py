"""Scoped T37 entry proof, reachability and actual short/wrong-key RTL faults."""
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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    out = (ROOT / a.output).resolve(); out.relative_to(ROOT / 'build')
    out.mkdir(parents=True, exist_ok=False)
    inputs = [Path(__file__), Path(__file__).with_name('SocTestAccessFormal.scala')]
    inputs += [ROOT / s for s in ('hw/top/reference/src/main/scala/deadhorse/top/SocTestAccess.scala',
        'hw/lib/src/main/scala/deadhorse/lib/Cdc.scala', 'tools/formal.py', 'tools/sbt.py',
        'tools/env/lock.json', 'build.sbt')]
    def hashes():
        return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    receipt = dict(status='running', sources=hashes(), jobs=[],
        commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        assumptions=['External reset asserted initially only; thereafter arbitrary reset, clock and inputs.'],
        scope='Public testMode at positive TCK vs full-word key oracle; no SoC isolation, clock-switch timing or scan-coverage claim.',
        bound_basis='80 symbolic samples exceeds 2*(2 release edges + 32 key edges + 1 observation edge)+2 initial samples; only covers/negative BMC use this bound.')
    def run(command, label, cap=180):
        start = time.monotonic()
        with (out / (label + '.log')).open('w') as log:
            try:
                code = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=cap).returncode
            except subprocess.TimeoutExpired:
                code = 124
        return dict(command=command, seconds=time.monotonic()-start, returncode=code)
    try:
        receipt['emission'] = run([sys.executable, 'tools/sbt.py',
            f'set hw / Compile / unmanagedSourceDirectories += file("{ROOT}/hw/top/reference/formal")',
            f'hw/runMain deadhorse.top.EmitSocTestAccessFormal {out}/emit'], 'emit')
        if receipt['emission']['returncode']:
            raise RuntimeError('Emission failed')
        for label, variant, mode, engine in (
            ('correct', 'correct', 'prove', 'abc pdr'),
            ('cover', 'correct', 'cover', 'smtbmc yices'),
            ('early', 'early', 'bmc', 'smtbmc yices'),
            ('wrong-key', 'wrong-key', 'bmc', 'smtbmc yices')):
            files = sorted((out / 'emit' / variant).glob('*.sv'))
            if not files:
                raise RuntimeError('No emitted model')
            config = out / (label + '.sby')
            config.write_text('\n'.join(['[options]', f'mode {mode}', 'multiclock on',
                'depth 80', 'timeout 120', '[engines]', engine, '[script]',
                'read_slang --top SocTestAccessFormal ' + ' '.join(p.name for p in files),
                'prep -top SocTestAccessFormal -flatten', "fminit -seq reset_n 0,'z",
                'clk2fflogic', 'chformal -lower', 'select -assert-count 1 t:$assert',
                'select -assert-count 1 t:$assume', 'select -assert-count 2 t:$cover',
                '[files]', *map(str, files), '']))
            row = run(['sby', '-d', str(out / label), str(config)], label)
            statusfile = out / label / 'status'
            status = statusfile.read_text().split()[0] if statusfile.exists() else 'ERROR'
            row.update(name=label, solver_status=status, engine=engine,
                       model_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
            receipt['jobs'].append(row)
            if status == 'TIMEOUT' or row['returncode'] == 124:
                row['status'] = 'unresolved'
            else:
                kind = 'negative' if mode == 'bmc' else mode
                row['failed_properties'] = validate_job(out / label, kind, row['returncode'], status,
                    set(assertion_names(1)) if kind == 'negative' else None)
                row['status'] = {'negative': 'fault_rejected', 'prove': 'proved', 'cover': 'covered'}[kind]
            print(label, row['status'], flush=True)
        if hashes() != receipt['sources']:
            raise RuntimeError('Source changed during run')
        receipt['status'] = 'unresolved' if any(r['status'] == 'unresolved' for r in receipt['jobs']) else 'pass'
    except Exception as error:
        receipt.update(status='failed', error=str(error))
    receipt['artifacts'] = {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in out.rglob('*') if p.is_file() and p != out / 'result.json'}
    (out / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(receipt['status'].upper(), receipt.get('error', ''))
    return 0 if receipt['status'] == 'pass' else 1


if __name__ == '__main__':
    sys.exit(main())

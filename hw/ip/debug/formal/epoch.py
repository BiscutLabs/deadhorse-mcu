"""Actual SBA/fabric/CDC reset composition, with production watchdog values."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from tools.formal import validate_job


def main(output):
    out = (ROOT / output).resolve()
    out.relative_to(ROOT / 'build')
    out.mkdir(parents=True, exist_ok=False)
    paths = [p for base in ('hw/lib', 'hw/ip/debug', 'hw/ip/bus', 'hw/ip/bus_bridge', 'hw/top/reference')
             for p in (ROOT / base).rglob('*') if p.is_file() and p.suffix in ('.scala', '.py')]
    paths += [ROOT / p for p in ('tools/env/lock.json', 'build.sbt', 'tools/formal.py', 'tools/sbt.py')]
    hashes = lambda: {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    receipt = dict(status='running', source_sha256=hashes(), jobs=[], timeout_seconds=120,
                   commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                   assumptions=['POR initially asserted, subsequently arbitrary',
                                'one outstanding DM request; legal delayed/error endpoint, structurally modeled',
                                'independent unconstrained clocks; digital sampling, no metastability model'],
                   scope='One retained path with actual single-master fabrics, production timeout values, actual shared CDC; not whole-SoC arbitration',
                   limits={'main_fabric': 131080, 'bridge': 131072, 'aon_fabric': 128})

    def run(command, name, timeout=180):
        start = time.monotonic()
        with (out / (name + '.log')).open('w') as log:
            try:
                code = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=timeout).returncode
            except subprocess.TimeoutExpired:
                code = 124
        return dict(command=command, returncode=code, seconds=time.monotonic()-start, log=name+'.log')

    try:
        receipt['emission'] = run([sys.executable, 'tools/sbt.py',
            'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/debug/formal")',
            f'hw/runMain deadhorse.debug.EmitDebugEpochFormal {out}/emit'], 'emit', 600)
        if receipt['emission']['returncode']:
            raise RuntimeError('Emission failed')
        for variant in ('correct', 'corrupt', 'stale', 'lost_credit', 'cover'):
            cover = variant == 'cover'
            fault = variant in ('corrupt', 'stale', 'lost_credit')
            mode = 'cover' if cover else 'bmc' if fault else 'prove'
            engine = 'smtbmc z3' if cover or fault else 'abc pdr'
            sources = sorted((out / 'emit' / variant).glob('*.sv'))
            if not sources:
                raise RuntimeError('No emitted sources')
            config = out / (variant + '.sby')
            config.write_text('\n'.join(['[options]', f'mode {mode}', 'multiclock on', 'depth 96',
                'timeout 120', '[engines]', engine, '[script]',
                'read_slang --top DebugEpochFormal ' + ' '.join(p.name for p in sources),
                'prep -top DebugEpochFormal -flatten', "fminit -seq por_n 0,'z", 'clk2fflogic',
                'chformal -lower', 'select -assert-count 1 t:$assume',
                f'select -assert-count {8 if cover else 16} t:$'+('cover' if cover else 'assert'),
                '[files]', *map(str, sources), '']))
            row = run(['sby', '-d', str(out / variant), str(config)], variant)
            row.update(variant=variant, mode=mode, engine=engine,
                       model_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
            receipt['jobs'].append(row)
            status = out / variant / 'status'
            row['solver_status'] = status.read_text().split()[0] if status.exists() else 'ERROR'
            if row['solver_status'] == 'TIMEOUT':
                row['status'] = 'unresolved'
            else:
                expected = {'assert__chisel3_builtin_0'} if variant in ('corrupt','lost_credit') else {
                    'assert__chisel3_builtin_0', 'assert__chisel3_builtin_5'} if variant=='stale' else None
                row['failed_properties'] = validate_job(out / variant, 'cover' if cover else 'negative' if fault else 'proof',
                             row['returncode'], row['solver_status'], expected)
                if variant=='stale' and 'assert__chisel3_builtin_5' not in row['failed_properties']:
                    raise RuntimeError('Stale fault did not exercise error propagation')
                if variant=='lost_credit' and 'credit.assert__chisel3_builtin_0' not in (out/variant/'logfile.txt').read_text():
                    raise RuntimeError('Lost-credit fault did not exercise drain accounting')
                row['status'] = 'covered' if cover else 'fault_rejected' if fault else 'proved'
            print(variant, row['status'], flush=True)
        if hashes() != receipt['source_sha256']:
            raise RuntimeError('Proof sources changed')
        receipt['status'] = 'unresolved' if any(j['status']=='unresolved' for j in receipt['jobs']) else 'pass'
    except Exception as exc:
        receipt.update(status='failed', error=str(exc))
    receipt['artifact_sha256'] = {p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in out.rglob('*') if p.is_file()}
    (out / 'result.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(receipt['status'], receipt.get('error', ''), flush=True)
    return 0 if receipt['status']=='pass' else 1


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', required=True)
    sys.exit(main(ap.parse_args().output))

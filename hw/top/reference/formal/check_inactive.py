"""Focused safe tie-off proof, cover and real output-enable fault. No CI."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'tools'))
from formal import validate_job


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    output.relative_to(ROOT / 'build')
    output.mkdir(parents=True, exist_ok=False)
    sources = [Path(__file__), Path(__file__).with_name('SocInactiveFormal.scala'),
               ROOT / 'hw/top/stubs/src/main/scala/deadhorse/top/SocInactivePads.scala',
               ROOT / 'tools/formal.py', ROOT / 'tools/sbt.py', ROOT / 'build.sbt', ROOT / 'tools/env/lock.json']
    def snapshot():
        return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    receipt = dict(status='running', source_sha256=snapshot(), assumptions=[],
                   commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                   scope='Static inactive pads only, not whole-SoC functional or physical qualification', runs=[])
    def run(command, name, timeout=180):
        start = time.monotonic()
        with (output / (name+'.log')).open('w') as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
        receipt['runs'].append(dict(command=command, log=name+'.log', seconds=time.monotonic()-start,
                                    returncode=result.returncode))
        return result.returncode
    try:
        if run([sys.executable, 'tools/sbt.py',
                f'set hw / Compile / unmanagedSourceDirectories += file("{ROOT}/hw/top/reference/formal")',
                f'hw/runMain deadhorse.top.EmitSocInactiveFormal {output}/emit'], 'emit', 600):
            raise RuntimeError('Emission failed')
        fault_ids = {'corrupt': 'assert__chisel3_builtin_0', 'gpio_fault': 'assert__chisel3_builtin_2',
                     'timer_fault': 'assert__chisel3_builtin_3', 'adc_fault': 'assert__chisel3_builtin_4'}
        jobs = [('cover', 'cover', 'smtbmc z3')]+[(n, 'bmc', 'smtbmc z3') for n in fault_ids]+[('correct', 'prove', 'abc pdr')]
        for variant, mode, engine in jobs:
            files = sorted((output / 'emit' / variant).glob('*.sv'))
            inventory = {p.name: re.findall(r'(assert__\w+):', p.read_text()) for p in files}
            if sum(map(len, inventory.values())) != 6:
                raise RuntimeError(f'Expected six safety assertions: {inventory}')
            covers = sum(p.read_text().count('cover property') for p in files)
            if covers != (1 if variant == 'cover' else 0):
                raise RuntimeError('Cover inventory mismatch')
            config = output / (variant+'.sby')
            config.write_text('\n'.join(['[options]', f'mode {mode}', 'depth 4', 'timeout 120', '',
                '[engines]', engine, '', '[script]',
                'read_slang --top SocInactiveFormal '+' '.join(p.name for p in files),
                'prep -top SocInactiveFormal -flatten', 'async2sync', 'chformal -lower',
                'select -assert-count 6 t:$assert', 'select -assert-count 0 t:$assume',
                f'select -assert-count {covers} t:$cover', '', '[files]', *map(str, files), '']))
            code = run(['sby', '-d', str(output / variant), str(config)], variant)
            status = (output / variant / 'status').read_text().split()[0]
            failures = validate_job(output / variant, 'negative' if variant in fault_ids else mode, code, status)
            if variant in fault_ids:
                faults = re.findall(r'Assert failed in [\w.]+: ([\w.]+)', (output / variant / 'logfile.txt').read_text())
                if faults != [fault_ids[variant]]:
                    raise RuntimeError(f'Wrong fault identity: {faults}')
                failures = faults
            receipt['runs'][-1].update(status=status, inventory=inventory, failed_properties=failures)
            print(f'PASS inactive {variant}: {status}', flush=True)
        if snapshot() != receipt['source_sha256']:
            raise RuntimeError('Source changed during proof')
        receipt['status'] = 'pass'
    except Exception as error:
        receipt.update(status='failed', error=str(error))
        raise
    finally:
        receipt['artifact_sha256'] = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in sorted(output.rglob('*')) if p.is_file() and p != output / 'result.json'}
        (output / 'result.json').write_text(json.dumps(receipt, indent=2)+'\n')


if __name__ == '__main__':
    main()

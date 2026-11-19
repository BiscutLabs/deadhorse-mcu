"""T19 focused safety properties, concrete covers and planted fault controls."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'tools'))
from formal import validate_job

CASES = {
    'cadence': ('UsbCadenceFormal', 2, 2, 16),
    'resume': ('UsbResumeFormal', 2, 2, 48),
    'denied': ('UsbDeniedFormal', 8, 2, 32),
    'in': ('UsbInFormal', 6, 4, 48),
    'out': ('UsbOutFormal', 6, 3, 48),
    'pads': ('UsbPadsFormal', 4, 2, 8),
    'control': ('UsbControlFormal', 2, 3, 128),
}
DEFAULT_CASES=tuple(CASES)
for lane in range(8):
    CASES[f'in_bit{lane}']=CASES['in']
    CASES[f'out_bit{lane}']=CASES['out']


def run(output, regmap, roles=None, portfolio=False):
    output = Path(output).resolve(); output.relative_to(ROOT / 'build')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use fresh output; preserve evidence')
    output.mkdir(parents=True)
    receipt = dict(status='running', cases={}, assumptions=[
        'reset_n initially low, subsequently arbitrary; single digital sample clock',
        'Denied harness fixes owner0 and maps tag0 to1, covering all non-owner origins',
        'Resume proof uses threshold17; production threshold144000 is separately simulated',
        'IN harness issues byte consumes only when valid and ACK only after consumed data; request/retry choices and application data/push are arbitrary',
        'OUT harness generates packets at most64 bytes, with arbitrary bytes, finish/error, stalls and application ready',
        'Digital synchronizers exclude analog metastability and electrical USB qualification'],
        limitations=['Packet properties apply to the stated packet-interface harness; they are not a proof of the full wire protocol',
                     'A bit-lane result covers only that named bit; all eight lanes are required to establish byte integrity'])
    started = time.monotonic()
    for role, (top, assertions, covers, depth) in CASES.items():
        if role not in (roles or DEFAULT_CASES): continue
        directory = output / role; directory.mkdir()
        entry = dict(status='running', jobs=[]); receipt['cases'][role] = entry
        try:
            with (directory / 'emit.log').open('w') as log:
                subprocess.run([sys.executable, 'tools/sbt.py',
                    f'runMain deadhorse.usb.EmitUsbFormal {regmap} {role} {directory}/emit'],
                    cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=600, check=True)
            for variant in (('cover','corrupt','withheld','correct') if role=='in' or role.startswith('in_bit') else ('cover','corrupt','correct')):
                sources = sorted((directory / 'emit' / variant).glob('*.sv'))
                if not sources: raise ValueError('Missing formal sources')
                mode = 'cover' if variant == 'cover' else 'prove' if variant == 'correct' else 'bmc'
                engine = ('abc pdr\nsmtbmc z3' if portfolio else 'abc pdr') if mode == 'prove' else 'btor btormc'
                # Constant-invalid fault makes four valid-conditioned assertions
                # tautologies during elaboration. Capacity and the service
                # obligation remain, and the latter must yield a counterexample.
                expected_assertions=2 if variant=='withheld' else assertions
                job = directory / (variant + '.sby')
                job.write_text('\n'.join(['[options]', f'mode {mode}', f'depth {depth}', 'timeout 120',
                    '', '[engines]', engine, '', '[script]',
                    f'read_slang --top {top} ' + ' '.join(p.name for p in sources),
                    f'prep -top {top} -flatten', "fminit -seq reset_n 0,'z", 'async2sync', 'chformal -lower',
                    f'select -assert-count {covers if mode == "cover" else expected_assertions} t:$' + ('cover' if mode == 'cover' else 'assert'),
                    '', '[files]', *map(str, sources), '']))
                before = time.monotonic()
                with (directory / (variant + '.log')).open('w') as log:
                    process = subprocess.run(['sby', '-d', str(directory / variant), str(job)],
                        cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=180)
                status_path = directory / variant / 'status'
                status = status_path.read_text().split()[0] if status_path.exists() else 'ERROR'
                row = dict(variant=variant, mode=mode, engine=engine, depth=depth, solver_status=status,
                    seconds=time.monotonic()-before, returncode=process.returncode,
                    source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
                entry['jobs'].append(row)
                validate_job(directory / variant, 'cover' if mode == 'cover' else 'proof' if variant == 'correct' else 'negative',
                    process.returncode, status)
                row['result'] = 'covered' if mode == 'cover' else 'proved' if variant == 'correct' else 'fault_rejected'
                print(f'PASS USB {role}/{variant}: {row["result"]}', flush=True)
            entry['status'] = 'pass'
        except Exception as error:
            entry.update(status='unresolved' if any(j.get('solver_status')=='TIMEOUT' for j in entry['jobs']) else 'failed', error=str(error))
    states={c['status'] for c in receipt['cases'].values()}
    receipt['status']='failed' if 'failed' in states else 'unresolved' if 'unresolved' in states else 'pass'
    receipt['seconds'] = time.monotonic()-started
    (output / 'result.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', required=True); parser.add_argument('--output', required=True)
    parser.add_argument('--case', action='append', choices=CASES)
    parser.add_argument('--portfolio', action='store_true', help='Run ABC PDR and Z3 induction together; same assertions and timeout')
    args = parser.parse_args()
    result = run(ROOT / args.output, ROOT / args.json, args.case, args.portfolio)
    print(result['status'].upper()+' USB focused formal')
    sys.exit(0 if result['status'] == 'pass' else 1)

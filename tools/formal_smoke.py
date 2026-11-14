"""Prove Hello with native BTOR2 and SymbiYosys; require fault and cover witnesses."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
DEPTH = 8
TIMEOUT = 180


def constrained_btor(source: Path, target: Path, properties: int):
    """Add only startup input constraints; preserve the native transition system."""
    data = source.read_text()
    rows = [line.split() for line in data.splitlines() if line and not line.startswith(';')]
    if sum(row[1] == 'bad' for row in rows) != properties:
        raise RuntimeError(f'{source}: missing/unexpected properties')
    one = next(row[0] for row in rows if row[1:] == ['sort', 'bitvec', '1'])
    inputs = {row[3]: row[0] for row in rows if row[1] == 'input' and len(row) == 4}
    reset, checking = inputs['reset_n'], inputs['checking']
    index = max(int(row[0]) for row in rows)
    extra = []

    def add(body):
        nonlocal index
        index += 1
        extra.append(f'{index} {body}')
        return str(index)

    zero = add(f'zero {one}')
    true = add(f'one {one}')
    started = add(f'state {one} t07_started')
    add(f'init {one} {started} {zero}')
    add(f'next {one} {started} {true}')
    reset_low = add(f'not {one} {reset}')
    startup = add(f'or {one} {started} {reset_low}')
    add(f'constraint {startup}')
    valid = add(f'eq {one} {checking} {started}')
    add(f'constraint {valid}')
    target.write_text(data + '\n; T07 documented startup input constraints\n' + '\n'.join(extra) + '\n')


def btor_outcome(text, induction, properties=2):
    outcomes = re.findall(r'^(sat|unsat|unknown)$', text, re.MULTILINE)
    proved_ids = re.findall(r'^unsat\nb(\d+)$', text, re.MULTILINE)
    if (outcomes == ['unsat'] * properties and induction
            and sorted(map(int, proved_ids)) == list(range(properties))
            and f'found 0 reachable and {properties} unreachable bad state properties' in text):
        return 'proved'
    if (outcomes == ['sat'] and re.search(r'^b\d+$', text, re.MULTILINE)
            and re.search(r'^#0$', text, re.MULTILINE) and re.search(r'^\.$', text, re.MULTILINE)):
        return 'witness'
    raise RuntimeError(f'BTOR2 did not produce a conclusive expected result: {outcomes}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    base = (ROOT / args.output).resolve()
    if not base.is_relative_to(ROOT / 'build'):
        parser.error('output must be under build/')
    base.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix='run-', dir=base))
    receipt = {'status': 'running', 'depth_limit': DEPTH, 'runs': [], 'versions': {},
               'assumptions': ['initial reset_n=0, then unconstrained',
                               'checking=0 at step zero, then 1; harness history validity'],
               'scope': 'sampled reset and registered byte successor; not analog reset timing'}
    path = run / 'receipt.json'

    def command(argv, log, allowed=(0,), timeout=TIMEOUT):
        started = time.monotonic()
        with (run / log).open('w') as stream:
            result = subprocess.run(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
        text = (run / log).read_text()
        record = {'command': argv, 'returncode': result.returncode,
                  'seconds': time.monotonic() - started, 'log': log}
        receipt['runs'].append(record)
        if result.returncode not in allowed:
            raise RuntimeError(f'{argv[0]} exit {result.returncode}: {run / log}\n{text[-2500:]}')
        return text, record

    try:
        # Guard direct calls as well as calls through the local gate.
        command([sys.executable, 'tools/env/check.py'], 'environment.log')
        for name, argv in {'btormc': ['btormc', '--version'], 'sby': ['sby', '--version'],
                           'yosys': ['yosys', '-V'], 'z3': ['z3', '--version'],
                           'firtool': ['firtool', '--version']}.items():
            receipt['versions'][name] = command(argv, name + '-version.log')[0].strip()
        emitted = run / 'emitted'
        command([sys.executable, 'tools/sbt.py',
                 f'hw/runMain deadhorse.lib.EmitHelloFormal {emitted.relative_to(ROOT).as_posix()}'],
                'emit.log', timeout=600)
        for variant in ('correct', 'wrong_increment', 'wrong_reset', 'cover_query'):
            model = run / (variant + '.btor2')
            constrained_btor(emitted / variant / 'HelloFormal.btor2', model,
                             1 if variant == 'cover_query' else 2)
            induction = variant == 'correct'
            argv = ['btormc', '--trace-gen', '1', '-v', '-kmax', str(DEPTH)]
            if induction:
                argv.append('--kind')
            text, record = command(argv + [str(model)], 'btor-' + variant + '.log', allowed=(0, 10, 20))
            outcome = btor_outcome(text, induction)
            expected = 'proved' if induction else 'witness'
            if outcome != expected:
                raise RuntimeError(f'BTOR2 {variant}: {outcome}, expected {expected}')
            record.update(route='native-btor2', variant=variant, outcome=outcome,
                          kind='unbounded induction' if induction else 'bounded witness')
            print(f'PASS BTOR2 {variant}: {record["kind"]}', flush=True)

        for variant in ('correct', 'wrong_increment', 'wrong_reset', 'cover'):
            mode = 'cover' if variant == 'cover' else 'prove'
            directory = emitted / variant
            sources = sorted(directory.glob('*.sv'))
            if not sources:
                raise RuntimeError('missing emitted SystemVerilog')
            config = run / (variant + '.sby')
            config.write_text((ROOT / 'hw/lib/formal/hello.sby.in').read_text().format(
                mode=mode, depth=DEPTH, timeout=TIMEOUT,
                sources=' '.join(p.name for p in sources), files='\n'.join(map(str, sources)),
                property_count=1 if mode == 'cover' else 2,
                property_type='cover' if mode == 'cover' else 'assert'))
            work = run / ('sby-' + variant)
            _, record = command(['sby', '-d', str(work), str(config)],
                                'sby-' + variant + '.log', allowed=(0, 2))
            status = (work / 'status').read_text().strip().split()[0]
            expected = 'FAIL' if variant.startswith('wrong_') else 'PASS'
            if status != expected or record['returncode'] != (2 if expected == 'FAIL' else 0):
                raise RuntimeError(f'SymbiYosys {variant}: {status}, expected {expected}')
            if variant != 'correct' and not list(work.glob('engine_*/trace*.vcd')):
                raise RuntimeError('missing counterexample/cover witness')
            record.update(route='symbiyosys', variant=variant, outcome=status,
                          kind='unbounded induction' if variant == 'correct' else 'bounded witness')
            print(f'PASS SymbiYosys {variant}: {record["kind"]}', flush=True)
        receipt['status'] = 'pass'
    except Exception as exc:
        receipt.update(status='fail', error=str(exc))
        raise
    finally:
        receipt['git_commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        inputs = [ROOT / 'build.sbt', ROOT / 'tools/sbt.py', Path(__file__), ROOT / 'tools/env/lock.json']
        inputs += sorted((ROOT / 'hw/lib').rglob('*.scala'))
        inputs.append(ROOT / 'hw/lib/formal/hello.sby.in')
        receipt['inputs'] = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
        path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(f'PASS formal smoke: {path.relative_to(ROOT)}')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        sys.exit(f'FORMAL_SMOKE: {exc}')

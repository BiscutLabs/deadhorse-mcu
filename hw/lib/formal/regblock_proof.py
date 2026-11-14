"""Require induction, deliberate-fault failures and cover witnesses for RegBlock."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from formal_smoke import btor_outcome


def startup_btor(source, target):
    """Initialize startup history and add a first-failure safety observer.

    This encodes the same startup contract as SBY. No DUT state is initialized
    here; in particular all reset checks remain capable of finding reset bugs.
    pastGood starts true and falls permanently on the first original failure.
    Querying pastGood && bad preserves existence of every counterexample and
    supplies the prefix hypothesis absent from BtorMC's init-free recheck.
    """
    rows = [line.split() for line in source.read_text().splitlines() if line and not line.startswith(';')]
    if sum(row[1] == 'bad' for row in rows) != 1:
        raise RuntimeError('missing/unexpected RegBlock safety property')
    one = next(row[0] for row in rows if row[1:] == ['sort', 'bitvec', '1'])
    reset = next(row[0] for row in rows if row[1:] == ['input', one, 'reset_n'])
    history = next(row[0] for row in rows if row[1:] == ['state', one, 'historyValid'])
    # BTOR2 requires a state's initialization constant to precede the state.
    # Insert zero immediately after its sort, renumbering references only.
    fresh = max(int(row[0]) for row in rows) + 1
    zero_id, true_id, past_id = map(str, range(fresh, fresh + 3))
    original_bad = next(row[2] for row in rows if row[1] == 'bad')
    for row in rows:
        if row[1] == 'bad':
            row[1:] = ['output', row[2], 'originalBad']
    position = next(i for i, row in enumerate(rows) if row[0] == one) + 1
    rows[position:position] = [[zero_id, 'zero', one], [true_id, 'one', one],
                               [past_id, 'state', one, 'pastGood']]
    ids = {row[0]: str(i + 1) for i, row in enumerate(rows)}
    converted = []
    for row in rows:
        op = row[1]
        if op == 'sort':
            refs = []
        elif op in ('state', 'input', 'const', 'constd', 'consth', 'zero', 'one', 'ones'):
            refs = [2]
        elif op in ('output', 'bad', 'constraint'):
            refs = [2]
        elif op in ('slice', 'uext', 'sext', 'not', 'neg', 'redand', 'redor', 'redxor'):
            refs = [2, 3]
        elif op in ('next', 'init', 'and', 'or', 'xor', 'eq', 'neq', 'concat', 'add', 'sub',
                    'sll', 'srl', 'sra', 'ult', 'ulte', 'ugt', 'ugte'):
            refs = [2, 3, 4]
        elif op == 'ite':
            refs = [2, 3, 4, 5]
        else:
            raise RuntimeError(f'unsupported native BTOR2 operation: {op}')
        changed = list(row)
        changed[0] = ids[row[0]]
        for ref in refs:
            changed[ref] = ids[row[ref]]
        converted.append(' '.join(changed))
    one, reset, history, zero = (ids[node] for node in (one, reset, history, zero_id))
    data = '\n'.join(converted) + '\n'
    index = len(rows)
    extra = []
    def add(body):
        nonlocal index
        index += 1
        extra.append(f'{index} {body}')
        return str(index)
    add(f'init {one} {history} {zero}')
    reset_low = add(f'not {one} {reset}')
    startup = add(f'or {one} {history} {reset_low}')
    add(f'constraint {startup}')
    past, true, bad = (ids[node] for node in (past_id, true_id, original_bad))
    add(f'init {one} {past} {true}')
    good = add(f'not {one} {bad}')
    prefix = add(f'and {one} {past} {good}')
    add(f'next {one} {past} {prefix}')
    first_failure = add(f'and {one} {past} {bad}')
    add(f'bad {first_failure}')
    target.write_text(data + '\n; Documented initial reset/history only\n' + '\n'.join(extra) + '\n')


def main():
    base = ROOT / 'build/t05/formal'
    base.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix='run-', dir=base))
    receipt = dict(status='running', runs=[], induction_search_limit=12,
                   assumptions=['initial reset_n=0, then unconstrained',
                                'checking=0 at step zero, then 1'], versions={})

    def command(args, log, allowed=(0,), timeout=180):
        start = time.monotonic()
        with (run / log).open('w') as stream:
            result = subprocess.run(args, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
        text = (run / log).read_text()
        record = dict(command=args, log=log, returncode=result.returncode, seconds=time.monotonic() - start)
        receipt['runs'].append(record)
        if result.returncode not in allowed:
            raise RuntimeError(f'{args[0]} exit {result.returncode}: {run / log}\n{text[-3000:]}')
        return text, record

    try:
        command([sys.executable, 'tools/env/check.py'], 'environment.log')
        for tool, flag in [('btormc', '--version'), ('sby', '--version'), ('yosys', '-V'), ('z3', '--version')]:
            receipt['versions'][tool] = command([tool, flag], tool + '-version.log')[0].strip()
        for block in ('coverage', 'mixed'):
            directory = ROOT / 'build/regmap' / block
            command([sys.executable, 'hw/regmap/regmap.py', f'hw/regmap/fixtures/{block}/{block}.regmap.yaml',
                     '--out', str(directory)], block + '-generate.log')
            emitted = run / block
            command([sys.executable, 'tools/sbt.py',
                     f'hw/runMain deadhorse.lib.EmitRegBlockFormal {directory}/{block}_regs.json {emitted}'],
                    block + '-emit.log', timeout=600)
            for variant in ('correct', 'wrong_strobes', 'wrong_reset', 'wrong_read'):
                label = block + '-' + variant
                model = run / (label + '.btor2')
                startup_btor(emitted / variant / 'RegBlockFormal.btor2', model)
                induction = variant == 'correct'
                args = ['btormc', '--trace-gen', '1', '-v', '-kmax', '12']
                if induction:
                    args.append('--kind')
                text, record = command(args + [str(model)], label + '-btor.log', allowed=(0, 10, 20))
                outcome = btor_outcome(text, induction, properties=1)
                if outcome != ('proved' if induction else 'witness'):
                    raise RuntimeError(f'{label}: unexpected {outcome}')
                record.update(route='native-btor2', fixture=block, variant=variant, outcome=outcome,
                              kind='unbounded induction' if induction else 'bounded counterexample')
                print(f'PASS BTOR2 {label}: {record["kind"]}', flush=True)
            for variant in ('correct', 'wrong_strobes', 'wrong_reset', 'wrong_read', 'cover'):
                label = block + '-' + variant
                source = emitted / variant
                sources = sorted(source.glob('*.sv'))
                if not sources:
                    raise RuntimeError(f'{label}: no emitted sources')
                config = run / (label + '.sby')
                config.write_text((ROOT / 'hw/lib/formal/regblock.sby.in').read_text().format(
                    mode='cover' if variant == 'cover' else 'prove',
                    engine='smtbmc z3' if variant == 'cover' else 'abc pdr',
                    sources=' '.join(p.name for p in sources),
                    files='\n'.join(map(str, sources)), property_count=7 if variant == 'cover' else 1,
                    property_type='cover' if variant == 'cover' else 'assert'))
                work = run / (label + '-sby')
                _, record = command(['sby', '-d', str(work), str(config)], label + '-sby.log', allowed=(0, 2))
                status = (work / 'status').read_text().strip().split()[0]
                negative = variant.startswith('wrong_')
                if status != ('FAIL' if negative else 'PASS') or record['returncode'] != (2 if negative else 0):
                    raise RuntimeError(f'{label}: unexpected SymbiYosys {status}')
                if variant != 'correct' and not list(work.glob('engine_*/trace*.vcd')):
                    raise RuntimeError(f'{label}: missing witness')
                record.update(route='symbiyosys', fixture=block, variant=variant, outcome=status,
                              kind='unbounded PDR' if variant == 'correct' else 'bounded witness')
                print(f'PASS SymbiYosys {label}: {record["kind"]}', flush=True)
        receipt['status'] = 'pass'
    except Exception as exc:
        receipt.update(status='fail', error=str(exc))
        raise
    finally:
        receipt['git_commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        inputs = list((ROOT / 'hw/regmap').rglob('*.py')) + list((ROOT / 'hw/regmap/fixtures').rglob('*.yaml'))
        inputs += [ROOT / p for p in ('hw/lib/src/main/scala/deadhorse/lib/RegBlock.scala',
                   'hw/lib/src/main/scala/deadhorse/lib/RegBus.scala', 'hw/lib/formal/RegBlockFormal.scala',
                   'hw/lib/formal/regblock.sby.in', 'tools/formal_smoke.py', 'tools/env/lock.json', 'build.sbt')]
        inputs.append(Path(__file__))
        receipt['inputs'] = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
        (run / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(f'PASS RegBlock formal: {run.relative_to(ROOT)}/receipt.json', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        sys.exit(f'REGBLOCK_FORMAL: {exc}')

"""PLAN03's single focused triage attempt; unchanged assertions and solver caps.

Freshly emits each concrete model, binds every variant to the historical model,
then tries DMA's remaining range assertion with Z3 and exact assertion partitions
for ADDI/watchdog. Sibling assertions are removed, never assumed. This does not
replace the block acceptance runners or claim complete ISA qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.formal import assertion_names, validate_job

CASES = {
    'dma': ('build/t23/formal-first/safety', 'DmaSafetyFormal', 10, 36,
            'hw/ip/dma/formal', 'deadhorse.dma.EmitDmaFormal safety', [3]),
    'lite': ('build/t25/rvfi-first/addi', 'LiteInstructionFormal', 14, 32,
             'hw/ip/lite_core/formal/LiteInstruction.scala',
             'deadhorse.lite_core.EmitLiteInstruction addi', list(range(14))),
    'watchdog': ('build/t26/formal02/channel', 'WatchdogFormal', 12, 20,
                 'hw/ip/watchdog/formal', 'deadhorse.watchdog.EmitWatchdogFormal', list(range(12))),
}


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=CASES, required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    out = (ROOT / args.output).resolve()
    out.relative_to(ROOT / 'build')
    out.mkdir(parents=True, exist_ok=False)
    old_path, top, count, depth, source, emitter, indices = CASES[args.case]
    old = ROOT / old_path
    inputs = [p for parent in ('hw/lib', 'hw/ip', 'project') for p in (ROOT / parent).rglob('*')
              if p.is_file() and p.suffix in ('.scala', '.py', '.json', '.yaml', '.sbt')]
    inputs += [ROOT / 'build.sbt', ROOT / 'tools/formal.py', ROOT / 'tools/sbt.py',
               ROOT / 'tools/env/lock.json', Path(__file__)]
    if args.case == 'lite':
        inputs.append(ROOT / 'hw/vendor/ibex_ref/riscv-formal/insns/insn_addi.v')
    hashes = lambda: {str(p.relative_to(ROOT)): digest(p) for p in inputs}
    receipt = dict(status='running', source_sha256=hashes(), jobs=[],
                   commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                   cap_seconds=120, depth=depth, original_assertions=count,
                   partition=indices, assumed_siblings=[], cutpoints=[],
                   assumptions='Original initial reset only; all later reset and inputs arbitrary',
                   scope='One new triage rung; historical timeouts remain; no full ISA or task closure')

    def save():
        (out / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')

    def run(argv, log, timeout=180):
        start = time.monotonic()
        with log.open('w') as stream:
            code = subprocess.run(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                  timeout=timeout).returncode
        return code, time.monotonic() - start

    try:
        setting = 'unmanagedSources' if source.endswith('.scala') else 'unmanagedSourceDirectories'
        argv = [sys.executable, 'tools/sbt.py',
                f'set hw / Compile / {setting} += file("{ROOT/source}")',
                f'hw/runMain {emitter} {out}/emit']
        code, seconds = run(argv, out / 'emit.log', 600)
        receipt['emission'] = dict(command=argv, returncode=code, seconds=seconds)
        assert code == 0, 'emission failed'
        identity = {}
        for variant in sorted(p.name for p in (old / 'emit').iterdir() if p.is_dir()):
            before = {p.name: digest(p) for p in (old / 'emit' / variant).glob('*.sv')}
            after = {p.name: digest(p) for p in (out / 'emit' / variant).glob('*.sv')}
            assert before and before == after, f'{variant}: emitted model differs from historical job'
            identity[variant] = after
        receipt['model_sha256'] = identity
        receipt['historical_evidence'] = {}
        # Reuse exact concrete witnesses, with model identity checked above. No
        # unchanged timed-out positive job is run as part of authentication.
        for variant in identity:
            if variant == 'correct':
                continue
            status = (old / variant / 'status').read_text().split()[0]
            assert status == ('PASS' if variant == 'cover' else 'FAIL'), (variant, status)
            files = [p for p in (old / variant).rglob('*') if p.is_file()]
            receipt['historical_evidence'][variant] = {str(p.relative_to(ROOT)): digest(p) for p in files}
        template = (old / 'correct.sby').read_text()
        assert f'depth {depth}' in template and 'timeout 120' in template
        template = template.replace(str(old / 'emit'), str(out / 'emit'))
        before_engine = template.split('[engines]\n', 1)[1].split('[script]', 1)[0]
        engine = 'smtbmc z3' if args.case == 'dma' else 'abc pdr'
        template = template.replace('[engines]\n' + before_engine, '[engines]\n' + engine + '\n')
        for index in indices:
            prop = ('d.' if args.case == 'dma' else '') + assertion_names(count)[index]
            marker = f'select -assert-count {count} t:$assert'
            assert template.count(marker) == 1
            script = template.replace(marker, marker + '\n' + '\n'.join([
                f'select -assert-count 1 c:{prop}', f'delete t:$assert c:{prop} %d',
                'select -assert-count 1 t:$assert', 'select *', 'opt_clean']))
            name = f'property-{index}'
            config = out / (name + '.sby')
            config.write_text(script)
            code, seconds = run(['sby', '-d', str(out / name), str(config)], out / (name + '.log'))
            status = (out / name / 'status').read_text().split()[0]
            row = dict(index=index, property=prop, engine=engine, status=status,
                       seconds=seconds, returncode=code, config_sha256=digest(config))
            receipt['jobs'].append(row)
            save()
            assert status in ('PASS', 'TIMEOUT'), f'{name}: {status}; inspect before continuing'
            if status == 'PASS':
                validate_job(out / name, 'proof', code, status)
            print(args.case, name, status, round(seconds, 3), flush=True)
        assert hashes() == receipt['source_sha256'], 'Sources changed during proof run'
        receipt['status'] = 'proved_partition' if all(j['status'] == 'PASS' for j in receipt['jobs']) else 'unresolved'
    except Exception as exc:
        receipt.update(status='failed', error=str(exc))
    receipt['artifact_sha256'] = {str(p.relative_to(out)): digest(p) for p in out.rglob('*')
                                  if p.is_file() and p != out / 'result.json'}
    save()
    print(receipt['status'].upper(), receipt.get('error', ''), flush=True)
    return 0 if receipt['status'] == 'proved_partition' else 1


if __name__ == '__main__':
    sys.exit(main())

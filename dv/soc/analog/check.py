"""T34 frozen scoped acceptance under D87; never aggregate CI or analog signoff."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.ci_tiers import snapshot
from dv.soc.analog.binding import interfaces, audit, fault_controls


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def formal_disposition(formal, code):
    expected = [('por-initial', 'prove')]
    for case in ('normal', 'bypass'):
        expected += [(case+'-'+v, 'prove' if v == 'correct' else 'bmc')
                     for v in ('correct', 'cold', 'strap', 'early')]
        expected.append((case+'-cover', 'cover'))
    jobs = formal.get('jobs', [])
    if (formal.get('emission', {}).get('returncode') != 0 or not jobs or
            [(j['name'], j['mode']) for j in jobs] != expected[:len(jobs)]):
        raise ValueError('Malformed/incomplete reset proof receipt')
    for index, row in enumerate(jobs):
        mode = row['mode']
        target = {'prove': ('PASS', 0, 'proved'), 'cover': ('PASS', 0, 'covered'),
                  'bmc': ('FAIL', 2, 'fault_rejected')}[mode]
        if (row['solver_status'], row['returncode'], row.get('status')) == target: continue
        if (index == len(jobs)-1 and mode == 'prove' and row['solver_status'] == 'TIMEOUT'
                and row['returncode'] != 0 and 'status' not in row and code != 0
                and formal.get('status') == 'failed' and formal.get('error') == row['name']+': TIMEOUT'):
            return 'deferred_timeout'
        raise ValueError('Reset proof failure is not an approved timeout deferral')
    if len(jobs) != len(expected) or code != 0 or formal.get('status') != 'pass':
        raise ValueError('Incomplete or unsuccessful reset proof aggregate')
    return 'proved_scoped_digital_reset'


def main(output):
    out = (ROOT / output).resolve(); out.relative_to(ROOT / 'build')
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    receipt = dict(status='running', decision='D87', source_sha256=snapshot(), commands=[],
                   commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                   scope='Digital analog models and production socket/reset binding only; no analog or physical signoff',
                   ci={'fast': 'not run per D87', 'full': 'not run per D87'},
                   assumptions=['Ideal voltage stimulus, zero-delay undervoltage assertion, simulation reference clock',
                                'LF source edges supplied externally; trim codes use uncharacterized startup setting',
                                'Two-state simulation does not qualify X/Z or analog accuracy'],
                   deferrals=['T33 count/shutdown/epoch/CDC/RDC composition unchanged under D86/D87',
                              'Physical PVT/mismatch/noise/latency and four-state qualification',
                              'Production trim loading and physical test access: later approved T37/T38/layout work'])
    def save():
        receipt['seconds'] = time.monotonic() - start
        (out / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    def run(label, command):
        before = time.monotonic(); save()
        with (out / (label + '.log')).open('w') as log:
            code = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT).returncode
        receipt['commands'].append(dict(label=label, command=command, returncode=code,
                                        seconds=time.monotonic()-before, log=label+'.log'))
        save()
        if code: raise RuntimeError(label + ' failed')
        print('PASS', label, flush=True)
    def simulations(label, command, expected):
        reports = ROOT / 'build/sbt/hw/test-reports'
        for suite in expected:
            path = reports / ('TEST-' + suite + '.xml')
            if path.exists():
                shutil.copy2(path, out / (label + '-prior-' + path.name)); path.unlink()
        run(label, [sys.executable, 'tools/sbt.py', command])
        rows = {}
        for suite, count in expected.items():
            path = reports / ('TEST-' + suite + '.xml'); doc = ET.parse(path).getroot()
            cases = doc.findall('testcase')
            if (doc.attrib['name'] != suite or len(cases) != count or
                    any(doc.attrib[k] != '0' for k in ('failures', 'errors', 'skipped')) or
                    any(list(c) for c in cases)):
                raise RuntimeError('Incomplete/unexpected simulation suite ' + suite)
            archived = out / (label + '-' + path.name); shutil.copy2(path, archived)
            rows[suite] = dict(cases=[c.attrib['name'] for c in cases], sha256=digest(archived))
        receipt[label] = rows; save()
    try:
        env = ROOT/'build/env/image.json'
        receipt['environment'] = dict(identity=json.loads(env.read_text()), receipt_sha256=digest(env),
            executables={name: dict(path=shutil.which(name), sha256=digest(Path(shutil.which(name))))
                         for name in ('python', 'java', 'yosys', 'sby', 'verilator')})
        run('receipt-faults', [sys.executable, '-m', 'unittest', 'dv.soc.analog.test_check', '-v'])
        run('prepare-boot', [sys.executable, 'dv/soc/prepare_i0.py'])
        run('prepare-maps', [sys.executable, 'dv/soc/prepare_xip.py'])
        run('map', [sys.executable, 'hw/top/reference/check_soc_map.py'])
        prepared_dirs = ('build/t20/map', 'build/t20/i0-firmware', 'build/t20/i1',
                         'build/t21/gpio', 'build/t21/timers', 'build/t21/aon_timer',
                         'build/t22/pwm', 'build/t23/dma', 'build/t24/pinmux', 'build/t26/watchdog',
                         'build/t28/boot_control', 'build/t30/qspi')
        inputs = [p for d in prepared_dirs for p in (ROOT/d).rglob('*')
                  if p.is_file() and p.suffix in ('.json', '.hex')]
        receipt['prepared_sha256'] = {p.relative_to(ROOT).as_posix(): digest(p) for p in inputs}
        provenance = ROOT/'build/riscay-mcu'
        if subprocess.check_output(['git', '-C', str(provenance), 'rev-parse', 'HEAD'], text=True).strip() != '4671317186003740ceb61360ba08c59bbdf10136':
            raise RuntimeError('Wrong RISCay provenance revision')
        names = ('analog/gf180-lf-osc/sources.json', 'analog/gf180-lf-osc/NOTICE.md',
                 'analog/gf180-lf-osc/README.md', 'analog/gf180-lf-osc/characterization.md',
                 'analog/gf180-clock-reset/README.md', 'analog/gf180-clock-reset/circuits.py',
                 'analog/gf180-clock-reset/riscay_supply_monitor_gf180.spice',
                 'physical/gf180/pdk-lock.json', 'soc/sram-lock.json')
        receipt['provenance_sha256'] = {}
        for name in names:
            path = provenance/name
            original = subprocess.check_output(['git', '-C', str(provenance), 'show', 'HEAD:'+name])
            if hashlib.sha256(original).hexdigest() != digest(path): raise RuntimeError('Modified provenance '+name)
            receipt['provenance_sha256'][path.relative_to(ROOT).as_posix()] = digest(path)
        simulations('models', 'hw/testOnly deadhorse.osc_ctrl.AnalogModelSpec deadhorse.osc_ctrl.AnalogContractSpec',
                    {'deadhorse.osc_ctrl.AnalogModelSpec': 5, 'deadhorse.osc_ctrl.AnalogContractSpec': 7})
        cases = [f'production POR boot AON external={str(e).lower()} bypass={str(b).lower()}'
                 for e in (False, True) for b in (False, True)]
        simulations('production-boot', 'hw/testOnly deadhorse.top.SocClockResetSpec -- ' +
                    ' '.join('-t "'+case+'"' for case in cases), {'deadhorse.top.SocClockResetSpec': 4})
        if receipt['production-boot']['deadhorse.top.SocClockResetSpec']['cases'] != cases:
            raise RuntimeError('Unexpected production test selection')
        # Relevant digital reset proofs are retained unchanged. An unresolved job
        # remains a failure of that entrypoint, explicitly deferred here by D87.
        before = time.monotonic()
        with (out/'reset-formal.log').open('w') as log:
            code = subprocess.run([sys.executable, 'hw/ip/osc_ctrl/formal/reset_check.py',
                                   '--output', str(out/'reset-formal')], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT).returncode
        formal = json.loads((out/'reset-formal/result.json').read_text())
        receipt['reset_formal'] = formal
        receipt['commands'].append(dict(label='reset-formal', command=[sys.executable,
            'hw/ip/osc_ctrl/formal/reset_check.py', '--output', str(out/'reset-formal')], returncode=code,
            seconds=time.monotonic()-before, log='reset-formal.log'))
        disposition = formal_disposition(formal, code)
        receipt['reset_formal_disposition'] = disposition
        if disposition == 'deferred_timeout':
            receipt['deferrals'].append('Fresh reset proof timeout; original failed receipt retained, no retry')
        run('emit', [sys.executable, 'tools/sbt.py', f'hw/runMain deadhorse.top.EmitSoc {output}/emit production 8'])
        emit = out/'emit'
        files = [(emit/n.strip()).resolve() for n in (emit/'filelist.f').read_text().splitlines() if n.strip()]
        for path in files: path.relative_to(emit)
        if len(files) != len(set(files)): raise RuntimeError('Duplicate emitted source')
        baseline_path = ROOT/'build/t33/production-timing03/map/result.json'
        if not baseline_path.exists():
            raise RuntimeError('Required T33 emission baseline missing; no no-change qualification')
        else:
            baseline = json.loads(baseline_path.read_text())
            old = baseline['emitted_sha256']
            for name, sha in old.items():
                if digest(ROOT/name) != sha: raise RuntimeError('Changed T33 emission reference '+name)
            current = {p.relative_to(emit).as_posix(): digest(p) for p in files}
            old_emit = baseline_path.parent.parent/'emit'
            prior = {(ROOT/p).relative_to(old_emit).as_posix(): sha for p, sha in old.items()}
            receipt['production_emission_comparison'] = dict(reference=str(baseline_path.relative_to(ROOT)),
                receipt_sha256=digest(baseline_path), identical=current == prior,
                changed=[p for p in set(current)|set(prior) if current.get(p) != prior.get(p)])
            if current != prior: raise RuntimeError('Production HDL changed; review timing/behavior before accepting')
        (out/'interfaces.json').write_text(json.dumps(interfaces()))
        config = json.loads((ROOT/'phys/gf180-ws-1x1/block-timing.json').read_text())
        lib = ROOT/f'build/riscay-mcu/.tools/physical/pdk/{config["library"]}__{config["corner"]}.lib'
        if digest(lib) != config['sha256']: raise RuntimeError('Wrong pinned library')
        receipt['liberty_sha256'] = digest(lib)
        script = out/'binding.ys'
        script.write_text('\n'.join([f'read_liberty -lib {lib}', f'read_json {out}/interfaces.json',
            'read_slang --keep-hierarchy -DSYNTHESIS --top DeadhorseSoc '+' '.join(map(str,files)),
            'hierarchy -check -top DeadhorseSoc', 'proc', 'chformal -remove', 'memory_collect',
            f'write_json {out}/hier.json'])+'\n')
        run('binding-import', ['yosys', '-Q', '-T', '-s', str(script)])
        design = json.loads((out/'hier.json').read_text())
        receipt['binding'] = audit(design); receipt['binding_faults'] = fault_controls(design)
        run('structure', [sys.executable, 'tools/check_structure.py', '--include-untracked'])
        if snapshot() != receipt['source_sha256']: raise RuntimeError('Sources changed during frozen checks')
        if digest(env) != receipt['environment']['receipt_sha256']: raise RuntimeError('Environment identity changed')
        if any(digest(ROOT/p) != h for p,h in receipt['prepared_sha256'].items()):
            raise RuntimeError('Prepared inputs changed during checks')
        receipt['status'] = 'pass_with_deferrals'
    except Exception as error:
        receipt.update(status='failed', error=str(error))
    receipt['artifact_sha256'] = {p.relative_to(out).as_posix(): digest(p)
                                  for p in out.rglob('*') if p.is_file() and p != out/'result.json'}
    save(); print(receipt['status'].upper(), receipt.get('error', ''), flush=True)
    return 0 if receipt['status'] == 'pass_with_deferrals' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    sys.exit(main(parser.parse_args().output))

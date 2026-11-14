"""Pinned, single-clock GF180 pre-layout block timing. No exception/waiver flags."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'phys/gf180-ws-1x1/block-timing.json'


def local(value):
    path = (ROOT / value).resolve()
    path.relative_to(ROOT)
    if any(c in str(path) for c in '{}"\n\r;$ \t'):
        raise ValueError('Unsupported character in path')
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, output, name, allowed=(0,)):
    result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    (output / f'{name}.log').write_text(result.stdout)
    with (output / 'commands.jsonl').open('a') as stream:
        stream.write(json.dumps({'command': command, 'returncode': result.returncode}) + '\n')
    if result.returncode not in allowed:
        raise RuntimeError(f'{name} failed ({result.returncode}); see {output}/{name}.log')
    return result.stdout


def validate_boundary(module, clock, library_cells):
    ports = module['ports']
    if clock not in ports or ports[clock]['direction'] != 'input' or len(ports[clock]['bits']) != 1:
        raise ValueError('Missing scalar clock input')
    if any(p['direction'] == 'inout' for p in ports.values()):
        raise ValueError('Unsupported bidirectional timing boundary')
    for cell in module['cells'].values():
        if cell['type'] not in library_cells:
            raise ValueError(f'Unsupported macro/cell timing view: {cell["type"]}')
        # This first flow supports a direct, single clock only. Propagating a
        # clock through arbitrary logic is not a substitute for generated-clock
        # constraints. The timer independently checks every sequential clock pin.
        if 'CLK' in cell['connections'] and cell['connections']['CLK'] != ports[clock]['bits']:
            raise ValueError('Unsupported or missing clock constraint: non-root CLK net')


def measure(top, sources, clock, output, liberty=None):
    cfg = json.loads(CONFIG.read_text())
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', top + ''):
        raise ValueError('Top must be a simple identifier')
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', clock):
        raise ValueError('Clock must be a simple identifier')
    output = local(output)
    output.relative_to(ROOT / 'build')
    output.mkdir(parents=True, exist_ok=True)
    # Invalidate old success before any operation that might fail.
    (output / 'result.json').write_text(json.dumps({'status': 'blocked'}))
    (output / 'commands.jsonl').write_text('')
    liberty = local(liberty or f'build/riscay-mcu/.tools/physical/pdk/{cfg["library"]}__{cfg["corner"]}.lib')
    if digest(liberty) != cfg['sha256']:
        raise ValueError('Required slow-corner Liberty hash mismatch')
    sources = [local(source) for source in sources]
    if not sources:
        raise ValueError('At least one emitted source is required')
    versions = {name: run(cmd, output, name).strip() for name, cmd in
                [('yosys-version', ['yosys', '-V']), ('sta-version', ['sta', '-version'])]}
    # Environment check authenticates the executables against the tool lock.
    run([sys.executable, 'tools/env/check.py'], output, 'environment')
    synth = output / 'synth.ys'
    frontend = [
        f'read_liberty -lib "{liberty}"',
        f'read_slang --keep-hierarchy --top {top} -DSYNTHESIS ' + ' '.join(str(p) for p in sources),
        f'hierarchy -check -top {top}']
    elaborate = output / 'elaborate.ys'
    elaborate.write_text('\n'.join(frontend + [f'write_json "{output / "elaborated.json"}"', '']))
    run(['yosys', '-Q', '-T', '-s', str(elaborate)], output, 'elaboration')
    library_cells = set(re.findall(r'\bcell\s*\(\s*"?([^\s"()]+)"?\s*\)', liberty.read_text()))
    elaborated = json.loads((output / 'elaborated.json').read_text())
    # Detect uncharacterized macros before flattening/optimization can erase an
    # empty synthesis stub (notably the T06 SRAM model's SYNTHESIS branch).
    for name, mod in elaborated['modules'].items():
        if name not in library_cells and (
                name.startswith('gf180') or int(mod.get('attributes', {}).get('blackbox', '0'), 2)):
            raise ValueError(f'Unsupported macro/cell timing view: {name}')
    synth.write_text('\n'.join(frontend + [
        'check -assert', f'synth -top {top} -flatten -noabc',
        f'dfflibmap -liberty "{liberty}"', f'abc -liberty "{liberty}"',
        'clean -purge', 'check -assert', f'stat -liberty "{liberty}"',
        f'write_json "{output / "mapped.json"}"',
        f'write_verilog -noattr -noexpr "{output / "mapped.v"}"', '']))
    synthesis = run(['yosys', '-Q', '-T', '-s', str(synth)], output, 'synthesis')
    design = json.loads((output / 'mapped.json').read_text())
    module = design['modules'][top]
    validate_boundary(module, clock, library_cells)
    areas = re.findall(r'Chip area for (?:top )?module.*?:\s*([0-9.]+)', synthesis)
    if not areas:
        raise ValueError('Missing mapped area')
    tcl = output / 'timing.tcl'
    tcl.write_text('\n'.join([
        f'set liberty {{{liberty}}}', f'set netlist {{{output / "mapped.v"}}}',
        f'set top {top}', f'set clock_port {clock}', f'set period {cfg["period_ns"]}',
        f'set input_transition {cfg["input_transition_ns"]}',
        f'set output_load {cfg["output_load_pf"]}',
        f'set path_report {{{output / "paths.tsv"}}}',
        f'source {{{ROOT / "tools/timing/analyze.tcl"}}}', '']))
    timing = run(['sta', '-no_init', '-exit', str(tcl)], output, 'sta')
    if 'TIMING_COMPLETE' not in timing or re.search(r'(?im)^Error:', timing):
        raise ValueError('Incomplete STA analysis; see sta.log')
    with (output / 'paths.tsv').open() as stream:
        paths = list(csv.DictReader(stream, delimiter='\t'))
    if not paths:
        raise ValueError('No timed data paths')
    for path in paths:
        path['delay_ns'] = float(path['delay_ns'])
        path['cell_depth'] = int(path['cell_depth'])
        path['logic_depth'] = int(path['logic_depth'])
        if not math.isfinite(path['delay_ns']) or path['delay_ns'] < 0:
            raise ValueError('Invalid path delay')
    worst = max(paths, key=lambda p: p['delay_ns'])
    budget = cfg['period_ns'] * cfg['budget_fraction']
    report = dict(status='pass' if worst['delay_ns'] <= budget else 'fail', top=top,
                  budget_ns=budget, worst=worst,
                  classes={kind: max((p for p in paths if p['class'] == kind),
                                    key=lambda p: p['delay_ns'], default=None)
                           for kind in ('RR', 'IR', 'RO', 'IO')},
                  area_um2=float(areas[-1]), assumptions=cfg, tools=versions,
                  flow_sha256={str(p.relative_to(ROOT)): digest(p) for p in
                               [CONFIG, *sorted((ROOT / 'tools/timing').glob('*.py')),
                                ROOT / 'tools/timing/analyze.tcl', ROOT / 'tools/timing/EmitRegTiming.scala']},
                  source_sha256={str(p.relative_to(ROOT)): digest(p) for p in sources},
                  commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)))
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    (output / 'ledger-row.md').write_text(
        f'| {top} | {worst["delay_ns"]:.6f} ns | {worst["start"]} | {worst["end"]} | '
        f'{worst["logic_depth"]} | {report["area_um2"]:.4f} um2 | {report["status"]} |\n')
    print(f'{report["status"].upper()} {top}: {worst["delay_ns"]:.6f} ns, budget {budget:.6f} ns', flush=True)
    return report


def self_test(output):
    output = local(output)
    output.relative_to(ROOT / 'build')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'self-test.json').write_text(json.dumps({'status': 'blocked'}))
    (output / 'commands.jsonl').write_text('')
    run([sys.executable, 'tools/sbt.py', f'hw/runMain deadhorse.top.EmitHello {output.relative_to(ROOT)}/emit'], output, 'emit')
    good = measure('Hello', [str(output / 'emit/Hello.sv')], 'clock', output / 'hello')
    # The production CLI must exit 1 for a real timing failure, not merely label
    # it in JSON while returning success to the local gate.
    run([sys.executable, 'tools/timing/check.py', '--top', 'ClockedElapsedTicks',
         '--source', 'build/riscay-mcu/build/export/clocked/ClockedElapsedTicks.sv',
         '--clock', 'clock', '--output', str(output / 'elapsed')],
        output, 'over-budget', allowed=(1,))
    bad = json.loads((output / 'elapsed/result.json').read_text())
    print(f'EXPECTED FAIL ClockedElapsedTicks: {bad["worst"]["delay_ns"]:.6f} ns; CLI exit 1', flush=True)
    if good['status'] != 'pass' or bad['status'] != 'fail':
        raise ValueError('Positive/negative timing controls did not separate')
    if not good['classes']['RO'] or good['classes']['RO']['delay_ns'] <= 0:
        raise ValueError('Direct register output lost clock-to-Q delay')
    # Exercise the actual timer with the clock deliberately attached to reset.
    clock_fault = output / 'hello/missing-clock.tcl'
    clock_fault.write_text((output / 'hello/timing.tcl').read_text().replace(
        'set clock_port clock\n', 'set clock_port reset_n\n'))
    log = run(['sta', '-no_init', '-exit', str(clock_fault)], output, 'missing-clock', allowed=(1,))
    if 'Missing clock:' not in log or 'TIMING_COMPLETE' in log:
        raise ValueError('Missing-clock negative control escaped')
    try:
        measure('ClockedSram', ['build/riscay-mcu/build/export/clocked/ClockedSram.sv',
                'build/riscay-mcu/build/export/clocked/gf180mcu_ocd_ip_sram__sram1024x8m8wm1.sv'],
                'clock', output / 'unsupported-sram')
    except ValueError as exc:
        if 'Unsupported macro/cell timing view:' not in str(exc):
            raise
        (output / 'unsupported-sram/expected-rejection.txt').write_text(str(exc) + '\n')
    else:
        raise ValueError('Missing SRAM view negative control escaped')
    for block in ('mixed', 'coverage'):
        directory = output / block
        directory.mkdir(exist_ok=True)
        run([sys.executable, 'hw/regmap/regmap.py', f'hw/regmap/fixtures/{block}/{block}.regmap.yaml',
             '--out', str(directory)], output, block + '-generate')
        run([sys.executable, 'tools/sbt.py',
             f'set hw / Compile / unmanagedSources += file("{ROOT}/tools/timing/EmitRegTiming.scala")',
             f'hw/runMain deadhorse.timing.EmitRegTiming {directory}/{block}_regs.json {directory}/emit'],
            output, block + '-emit')
        result = measure('RegBlock', [str(directory / 'emit/RegBlock.sv')], 'clk', directory / 'timing')
        if result['status'] != 'pass':
            raise ValueError(f'Production RegBlock/{block} exceeds timing budget')
    (output / 'self-test.json').write_text(json.dumps({
        'status': 'pass', 'controls': {'over_budget_cli': 'exit 1',
        'clock_to_q': 'positive direct-register output delay',
        'missing_clock': 'OpenSTA error', 'unsupported_sram': 'blocked before mapping'},
        'production': ['Hello', 'RegBlock/mixed', 'RegBlock/coverage']}, indent=2) + '\n')
    print('PASS timing self-test: valid path accepted; real over-budget path rejected', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--output', required=True)
    parser.add_argument('--top')
    parser.add_argument('--source', action='append', default=[])
    parser.add_argument('--clock')
    parser.add_argument('--liberty')
    args = parser.parse_args()
    try:
        if args.self_test:
            self_test(args.output)
            return 0
        if not args.top or not args.clock:
            parser.error('--top and --clock are required')
        return int(measure(args.top, args.source, args.clock, args.output, args.liberty)['status'] != 'pass')
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f'BLOCKED timing: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())

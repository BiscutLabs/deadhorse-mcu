"""Pinned single-clock or stateless GF180 timing. No exception/waiver flags."""
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
sys.path.insert(0, str(ROOT))
CONFIG = ROOT / 'phys/gf180-ws-1x1/block-timing.json'
OPERATING_POINTS = ('default', 'main-12mhz', 'main-9p6mhz', 'main-9mhz', 'usb-48mhz')

# Reference adapters and primitives are verification-only.
sys.path.insert(0, str(ROOT / 'dv/core'))
from isolation import reject_sources


def local(value):
    path = (ROOT / value).resolve()
    path.relative_to(ROOT)
    if any(c in str(path) for c in '{}"\n\r;$ \t'):
        raise ValueError('Unsupported character in path')
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def output_aliases(module):
    groups = {}
    for name, port in module['ports'].items():
        if port['direction'] == 'output':
            for index, bit in enumerate(port['bits']):
                if isinstance(bit, int):
                    groups.setdefault(bit, []).append(f'{name}[{index}]')
    aliases = [names for names in groups.values() if len(names)>1]
    return max((len(names) for names in groups.values()),default=1), aliases


def electrical_checks(log):
    """Require the actual STA electrical report, not absence of warning text."""
    sections = re.findall(r'ELECTRICAL_BEGIN\n(.*?)ELECTRICAL_END', log, re.S)
    if len(sections) != 1:
        raise ValueError('Missing or ambiguous STA electrical report')
    return {'max_capacitance_and_slew_violations': sections[0].count('(VIOLATED)')}


def result_status(delay, budget, electrical):
    return 'pass' if delay <= budget and electrical['max_capacitance_and_slew_violations'] == 0 else 'fail'


def run(command, output, name, allowed=(0,)):
    result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    (output / f'{name}.log').write_text(result.stdout)
    with (output / 'commands.jsonl').open('a') as stream:
        stream.write(json.dumps({'command': command, 'returncode': result.returncode}) + '\n')
    if result.returncode not in allowed:
        raise RuntimeError(f'{name} failed ({result.returncode}); see {output}/{name}.log')
    return result.stdout


def validate_boundary(module, clock, library_cells, combinational=False):
    ports = module['ports']
    if not combinational and (clock not in ports or ports[clock]['direction'] != 'input' or len(ports[clock]['bits']) != 1):
        raise ValueError('Missing scalar clock input')
    if any(p['direction'] == 'inout' for p in ports.values()):
        raise ValueError('Unsupported bidirectional timing boundary')
    # A characterized, non-inverting integrated gate preserves the root clock.
    # Only this qualified cell driven directly by the root is supported; no
    # arbitrary logic, cascaded gates, dividers, or extra clock domains.
    gate_type='gf180mcu_fd_sc_mcu7t5v0__icgtp_1'
    clock_nets=[] if combinational else [ports[clock]['bits']]
    for cell in module['cells'].values():
        if cell['type']==gate_type:
            pins=cell['connections']
            if combinational or pins.get('CLK')!=ports[clock]['bits'] or set(pins)!={'CLK','E','TE','Q'} or any(len(v)!=1 for v in pins.values()):
                raise ValueError('Unsupported integrated clock-gate binding')
            clock_nets.append(pins['Q'])
    for cell in module['cells'].values():
        if cell['type'] not in library_cells:
            raise ValueError(f'Unsupported macro/cell timing view: {cell["type"]}')
        # STA independently checks every sequential clock pin. Ideal pre-CTS
        # launch constraints remain unchanged for the root and its gated branch.
        if 'CLK' in cell['connections']:
            if combinational:
                raise ValueError('Sequential cell in combinational timing mode')
            if cell['connections']['CLK'] not in clock_nets:
                raise ValueError('Unsupported or missing clock constraint: non-root CLK net')


def timing_config(operating_point='default'):
    if operating_point not in OPERATING_POINTS:
        raise ValueError('Unsupported timing operating point')
    cfg = json.loads(CONFIG.read_text())
    if operating_point != 'default':
        frequency_mhz = {'main-12mhz': 12.0, 'main-9p6mhz': 9.6, 'main-9mhz': 9.0, 'usb-48mhz': 48.0}[operating_point]
        cfg['period_ns'] = 1000.0 / frequency_mhz
        cfg['provenance'] = (f'User-authorized T13 {frequency_mhz:g} MHz trial: only the period changes; '
                             'the budget fraction and other constraints are unchanged. '
                             'Default configuration provenance: ' + cfg['provenance'])
        if operating_point == 'usb-48mhz':
            cfg['provenance'] = cfg['provenance'].replace('User-authorized T13 48 MHz trial',
                'T19 required USB 48 MHz sample-clock operating point')
        if operating_point == 'main-9mhz':
            cfg['provenance'] = cfg['provenance'].replace(
                'only the period changes;',
                'the STA period changes; ABC retains the tighter 62500 ps mapping target;')
    return cfg


def mapping_target_ps(cfg, operating_point):
    # Optimization target only, not the STA acceptance limit. The 9 MHz trial
    # retains the measured 9.6 MHz mapping recipe; a looser target regressed it.
    budget_ps = cfg['period_ns'] * cfg['budget_fraction'] * 1000
    return min(budget_ps, 62500.0) if operating_point == 'main-9mhz' else budget_ps


def measure(top, sources, clock, output, liberty=None, combinational=False, *, operating_point='default'):
    return _measure(top,sources,clock,output,liberty,combinational,operating_point=operating_point)


def _measure(top, sources, clock, output, liberty=None, combinational=False,
             reference_options=None, *, operating_point='default'):
    # Shared numerical flow. The production entry above always checks isolation.
    # Only dv/core/reference_timing.py supplies authenticated reference options;
    # such receipts are explicitly benchmarks, never production acceptance.
    if reference_options is None:
        reject_sources(sources)
    if reference_options is not None and operating_point != 'default':
        raise ValueError('Reference benchmark requires the default operating point')
    cfg = timing_config(operating_point)
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', top + ''):
        raise ValueError('Top must be a simple identifier')
    if combinational and clock is not None:
        raise ValueError('Combinational mode has a virtual clock, not a clock port')
    if not combinational and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', clock or ''):
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
        f'read_slang --keep-hierarchy --top {top} -DSYNTHESIS ' +
        ' '.join(reference_options or [])+' '+' '.join(str(p) for p in sources),
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
    # ABC constraints guide combinational mapping only. Final STA continues to
    # use the pinned input slew/output load, independently of this driver model.
    # An explicit script avoids the retime command inserted by ABC's -D default.
    budget = cfg['period_ns'] * cfg['budget_fraction']
    target_ps = mapping_target_ps(cfg, operating_point)
    driver = cfg['library'] + '__buf_1'
    if driver not in library_cells:
        raise ValueError('Missing ABC mapping driver in pinned library')
    # ABC sees one PO per net, while STA loads each top-level output port.
    # Determine aliases after logic optimization, and conservatively apply the
    # maximum aggregate load to every mapper PO. STA constraints do not change.
    premap = output / 'premap.ys'
    premap.write_text('\n'.join(frontend + [
        'check -assert', f'synth -top {top} -flatten -noabc',
        f'dfflibmap -liberty "{liberty}"', f'write_json "{output / "premapped.json"}"', '']))
    run(['yosys','-Q','-T','-s',str(premap)],output,'premap')
    predesign = json.loads((output/'premapped.json').read_text())
    multiplicity, aliases = output_aliases(predesign['modules'][top])
    mapping = dict(flow='buffered-sized-alias-load-v3', target_ps=target_ps,
                   driver_cell_heuristic=driver, output_load_ff=cfg['output_load_pf'] * 1000 * multiplicity,
                   output_alias_multiplier=multiplicity, output_alias_groups=aliases,
                   retiming=False)
    if operating_point == 'main-9mhz':
        mapping['target_provenance'] = ('Retain the 9.6 MHz trial mapping target; '
                                        'STA acceptance remains period * budget_fraction.')
    abc_constraints = output / 'mapping.constr'
    abc_constraints.write_text(f'set_driving_cell {driver}\nset_load {mapping["output_load_ff"]:g}\n')
    abc_script = output / 'mapping.abc'
    abc_script.write_text('strash; &get -n; &fraig -x; &put; scorr; dc2; strash; '
                         f'&get -n; &dch -f; &nf -D {target_ps:g}; &put; buffer; '
                         f'upsize -D {target_ps:g}; dnsize -D {target_ps:g}; stime -p\n')
    mapping['script_sha256'] = digest(abc_script)
    mapping['constraints_sha256'] = digest(abc_constraints)
    # Reproduce the same frontend/synthesis sequence for mapping instead of
    # reimporting JSON: serialization changes ABC's traversal order and would
    # gratuitously perturb the qualified mapping even for non-aliased blocks.
    synth.write_text('\n'.join(frontend + [
        'check -assert', f'synth -top {top} -flatten -noabc',
        f'dfflibmap -liberty "{liberty}"',
        f'abc -liberty "{liberty}" -constr "{abc_constraints}" -script "{abc_script}"',
        'clean -purge', 'check -assert', f'stat -liberty "{liberty}"',
        f'write_json "{output / "mapped.json"}"',
        f'write_verilog -noattr -noexpr "{output / "mapped.v"}"', '']))
    synthesis = run(['yosys', '-Q', '-T', '-s', str(synth)], output, 'synthesis')
    design = json.loads((output / 'mapped.json').read_text())
    if operating_point == 'usb-48mhz':
        from tools.timing.fanout import BUFFER, buffer_module
        if BUFFER not in library_cells:
            raise ValueError('USB fanout buffer absent from pinned library')
        (output / 'unbuffered.json').write_text(json.dumps(design))
        design['modules'][top], inserted = buffer_module(design['modules'][top], clock)
        mapping['fanout_tree'] = dict(cell=BUFFER,limit=8,inserted=len(inserted),
                                    verification='all original pins resolve identically; clocks unchanged')
        (output / 'buffered.json').write_text(json.dumps(design))
        buffer_script = output / 'buffer.ys'
        buffer_script.write_text('\n'.join([
            f'read_json "{output / "buffered.json"}"', 'check -assert',
            f'stat -liberty "{liberty}"', f'write_json "{output / "mapped.json"}"',
            f'write_verilog -noattr -noexpr "{output / "mapped.v"}"', '']))
        synthesis = run(['yosys','-Q','-T','-s',str(buffer_script)],output,'buffer')
        design = json.loads((output / 'mapped.json').read_text())
    module = design['modules'][top]
    post_multiplicity, post_aliases = output_aliases(module)
    if post_multiplicity > multiplicity:
        raise ValueError('ABC introduced additional output aliases; mapping load must be revised')
    mapping['mapped_output_alias_multiplier'] = post_multiplicity
    mapping['mapped_output_alias_groups'] = post_aliases
    validate_boundary(module, clock, library_cells, combinational)
    areas = re.findall(r'Chip area for (?:top )?module.*?:\s*([0-9.]+)', synthesis)
    if not areas:
        raise ValueError('Missing mapped area')
    tcl = output / 'timing.tcl'
    gate_pins=[name+'/'+pin for name,cell in module['cells'].items()
               if cell['type']=='gf180mcu_fd_sc_mcu7t5v0__icgtp_1' for pin in ('E','TE')]
    if any(re.search(r'[{}\s]',pin) for pin in gate_pins):
        raise ValueError('Unsupported clock-gate instance name')
    tcl.write_text('\n'.join([
        f'set liberty {{{liberty}}}', f'set netlist {{{output / "mapped.v"}}}',
        f'set top {top}', f'set clock_port {{{clock or ""}}}', f'set period {cfg["period_ns"]}',
        f'set combinational {int(combinational)}',
        'set clock_gate_pins {'+' '.join(gate_pins)+'}',
        f'set input_transition {cfg["input_transition_ns"]}',
        f'set output_load {cfg["output_load_pf"]}',
        f'set path_report {{{output / "paths.tsv"}}}',
        f'set gate_path_report {{{output / "gate_checks.tsv"}}}',
        f'source {{{ROOT / "tools/timing/analyze.tcl"}}}', '']))
    timing = run(['sta', '-no_init', '-exit', str(tcl)], output, 'sta')
    if 'TIMING_COMPLETE' not in timing or re.search(r'(?im)^Error:', timing):
        raise ValueError('Incomplete STA analysis; see sta.log')
    electrical = electrical_checks(timing)
    gate_checks=[]
    if gate_pins:
        with (output/'gate_checks.tsv').open() as stream:
            gate_checks=list(csv.DictReader(stream,delimiter='\t'))
        if {(r['pin'],r['check']) for r in gate_checks}!={(p,c) for p in gate_pins for c in ('max_rise','max_fall','min_rise','min_fall')} or len(gate_checks)!=len(gate_pins)*4:
            raise ValueError('Incomplete clock-gate setup/hold report')
        for row in gate_checks:
            row['slack_ns']=float(row['slack_ns'])
            if not math.isfinite(row['slack_ns']) or row['slack_ns']<0:
                raise ValueError('Invalid/violating clock-gate setup/hold slack')
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
    report = dict(status=result_status(worst['delay_ns'], budget, electrical), top=top,
                  role=('reference-benchmark-only' if reference_options is not None else
                        'operating-point-trial' if operating_point not in ('default','usb-48mhz') else 'production'),
                  operating_point=operating_point,
                  mapping=mapping, electrical=electrical,
                  boundary='combinational' if combinational else 'root-clock-with-icg' if gate_pins else 'single-clock',
                  clock_gate_checks=gate_checks,
                  budget_ns=budget, worst=worst,
                  classes={kind: max((p for p in paths if p['class'] == kind),
                                    key=lambda p: p['delay_ns'], default=None)
                           for kind in ('RR', 'IR', 'RO', 'IO', 'RG', 'IG')},
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
    print(f'{report["status"].upper()} {top}: {worst["delay_ns"]:.6f} ns, budget {budget:.6f} ns; '
          f'electrical violations {electrical["max_capacitance_and_slew_violations"]}', flush=True)
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
        'set clock_port {clock}\n', 'set clock_port {reset_n}\n'))
    log = run(['sta', '-no_init', '-exit', str(clock_fault)], output, 'missing-clock', allowed=(1,))
    if 'Missing clock:' not in log or 'TIMING_COMPLETE' in log:
        raise ValueError('Missing-clock negative control escaped')
    # Overload a real mapped output, without remapping it. This checks the STA
    # report and parser can distinguish electrical failure from a timing pass.
    load_fault = output / 'hello/excess-load.tcl'
    load_fault.write_text((output / 'hello/timing.tcl').read_text().replace(
        f'set output_load {good["assumptions"]["output_load_pf"]}\n',
        'set output_load 0.5\n').replace('hello/paths.tsv', 'hello/excess-load-paths.tsv'))
    log = run(['sta', '-no_init', '-exit', str(load_fault)], output, 'excess-load')
    electrical_fault = electrical_checks(log)
    with (output / 'hello/excess-load-paths.tsv').open() as stream:
        fault_delay = max(float(p['delay_ns']) for p in csv.DictReader(stream, delimiter='\t'))
    if ('TIMING_COMPLETE' not in log or fault_delay > good['budget_ns'] or
            result_status(fault_delay, good['budget_ns'], electrical_fault) != 'fail'):
        raise ValueError('Electrical overload negative control escaped')
    (output / 'electrical-negative.json').write_text(json.dumps(dict(
        status='rejected', injected_output_load_pf=0.5, delay_ns=fault_delay,
        budget_ns=good['budget_ns'], electrical=electrical_fault), indent=2) + '\n')
    # Stateless timing is an additional boundary contract, not a route for
    # bypassing the clock checks on a sequential block.
    try:
        measure('Hello', [str(output / 'emit/Hello.sv')], None,
                output / 'wrong-combinational', combinational=True)
    except ValueError as exc:
        if 'Sequential cell in combinational timing mode' not in str(exc):
            raise
    else:
        raise ValueError('Sequential design escaped stateless boundary check')
    mode_fault = output / 'hello/wrong-mode.tcl'
    mode_fault.write_text((output / 'hello/timing.tcl').read_text().replace(
        'set combinational 0\n', 'set combinational 1\n'))
    log = run(['sta', '-no_init', '-exit', str(mode_fault)], output, 'wrong-mode', allowed=(0, 1))
    if 'Sequential cell in combinational timing mode' not in log or 'TIMING_COMPLETE' in log:
        raise ValueError('STA stateless boundary negative control escaped')
    run([sys.executable, 'tools/sbt.py',
         f'set hw / Compile / unmanagedSources += file("{ROOT}/tools/timing/EmitCombTiming.scala")',
         f'hw/runMain deadhorse.timing.EmitCombTiming {output}/comb_emit'], output, 'comb-emit')
    comb = measure('CombTiming', [str(output/'comb_emit/CombTiming.sv')], None,
                   output/'combinational', combinational=True)
    if comb['status'] != 'pass' or not comb['classes']['IO'] or comb['worst']['delay_ns'] <= 0:
        raise ValueError('Stateless positive control lacks a timed IO path')
    if any(comb['classes'][kind] is not None for kind in ('RR', 'IR', 'RO')):
        raise ValueError('Stateless fixture unexpectedly contains register paths')
    alias = measure('AliasTiming',[str(output/'comb_emit/AliasTiming.sv')],None,
                    output/'alias',combinational=True)
    if (alias['status'] != 'pass' or alias['mapping']['output_alias_multiplier'] != 2 or
            alias['mapping']['output_load_ff'] != 100 or alias['assumptions']['output_load_pf'] != 0.05):
        raise ValueError('Aliased output aggregate mapping load or unchanged STA load lost')
    gated_self_test(output/'gated')
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
        'missing_clock': 'OpenSTA error', 'unsupported_sram': 'blocked before mapping',
        'electrical_overload': 'STA max-capacitance/slew violations detected',
        'output_aliases': 'two ports give 100fF mapper load; each retains 50fF STA load',
        'clock_gate': 'root/gated paths, enable setup/hold; alien clock and setup/hold faults rejected',
        'stateless': 'positive IO path; sequential inputs rejected by Python and STA'},
        'production': ['Hello', 'RegBlock/mixed', 'RegBlock/coverage']}, indent=2) + '\n')
    print('PASS timing self-test: valid path accepted; real over-budget path rejected', flush=True)


def gated_self_test(output):
    output=local(output); output.mkdir(parents=True,exist_ok=True)
    (output/'result.json').write_text('{"status":"blocked"}\n')
    run([sys.executable,'tools/sbt.py',
         f'set hw / Compile / unmanagedSources += file("{ROOT}/tools/timing/EmitGatedTiming.scala")',
         f'hw/runMain deadhorse.timing.EmitGatedTiming {output}/emit'],output,'emit')
    result=measure('GatedTiming',[str(p) for p in sorted((output/'emit').glob('*.sv'))],
                   'clk',output/'normal')
    if result['status']!='pass' or len(result['clock_gate_checks'])!=8 or not result['classes']['RG'] or not result['classes']['IG']:
        raise ValueError('Gated positive control lost data/enable paths')
    design=json.loads((output/'normal/mapped.json').read_text())['modules']['GatedTiming']
    gate=next(name for name,cell in design['cells'].items() if cell['type']=='gf180mcu_fd_sc_mcu7t5v0__icgtp_1')
    original=(ROOT/'tools/timing/analyze.tcl').read_text()
    faults={
        'alien-clock':(f'create_clock -name alien -period $period [get_pins {gate}/Q]\n','Unexpected clock:'),
        'enable-setup':('set_input_delay 50 -max -clock block_clock [get_ports test_enable]\n','Clock-gate enable setup/hold violation'),
        'enable-hold':('set_input_delay -5 -min -clock block_clock [get_ports test_enable]\n','Clock-gate enable setup/hold violation')}
    for name,(injection,expected) in faults.items():
        analysis=output/(name+'-analysis.tcl')
        analysis.write_text(original.replace('set regs [all_registers]',injection+'set regs [all_registers]',1))
        driver=output/(name+'.tcl')
        driver.write_text((output/'normal/timing.tcl').read_text().replace(
            str(ROOT/'tools/timing/analyze.tcl'),str(analysis)).replace(
            str(output/'normal/gate_checks.tsv'),str(output/(name+'-gate_checks.tsv'))))
        log=run(['sta','-no_init','-exit',str(driver)],output,name,allowed=(0,1))
        if expected not in log or 'TIMING_COMPLETE' in log:
            raise ValueError('Gated timing negative control escaped: '+name)
    (output/'result.json').write_text(json.dumps(dict(status='pass',negative_controls=list(faults)),indent=2)+'\n')
    print('PASS gated timing: root clock, enable setup/hold and three rejected faults',flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--output', required=True)
    parser.add_argument('--top')
    parser.add_argument('--source', action='append', default=[])
    parser.add_argument('--clock')
    parser.add_argument('--combinational', action='store_true')
    parser.add_argument('--liberty')
    parser.add_argument('--operating-point', choices=OPERATING_POINTS, default='default',
                        help='Named trial; default production acceptance remains unchanged')
    args = parser.parse_args()
    try:
        if args.self_test:
            if args.operating_point != 'default':
                parser.error('--self-test validates the default flow; use explicit trial measurements')
            self_test(args.output)
            return 0
        if not args.top or (not args.clock and not args.combinational):
            parser.error('--top and either --clock or --combinational are required')
        return int(measure(args.top, args.source, args.clock, args.output,
                           args.liberty, args.combinational, operating_point=args.operating_point)['status'] != 'pass')
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f'BLOCKED timing: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())

"""Carry authenticated production clocks and USB exceptions into the pad top."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'i_chip_core.soc.'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--map', required=True)
    p.add_argument('--screen', default='build/t43/new02/ss125')
    p.add_argument('--template-config', default='build/t43/chip-fit05/config.json')
    p.add_argument('--output', required=True)
    a = p.parse_args()
    mapped, screen, template, out = [(ROOT / v).resolve() for v in
                                   (a.map, a.screen, a.template_config, a.output)]
    out.relative_to(ROOT / 'build')
    out.mkdir(parents=True, exist_ok=False)
    receipt = json.loads((mapped / 'result.json').read_text())
    assert receipt['status'] == 'pass'
    assert sha(mapped / 'mapped.json') == receipt['artifact_sha256']['mapped.json']
    chip = json.loads((mapped / 'mapped.json').read_text())['modules']['chip_top']
    prior = json.loads((screen / 'result.json').read_text())
    assert prior['mapped_sha256'] == receipt['input_sha256']['build/t43/new02/map/canonical.json']
    expected = json.loads((screen / 'expected-clocks.json').read_text())
    input_hashes = {str(q.relative_to(ROOT)): sha(q) for q in
                   [Path(__file__), mapped / 'result.json', mapped / 'mapped.json',
                    screen / 'result.json', screen / 'expected-clocks.json', template]}

    def pin(name):
        cell, port = name.rsplit('/', 1)
        assert cell in chip['cells'] and port in chip['cells'][cell]['connections'], name
        assert len(chip['cells'][cell]['connections'][port]) == 1, name
        return name

    divider = pin(PREFIX + prior['generated_clock_pin'])
    select = pin(PREFIX + prior['clock_mux_mode_pin'])
    for name in expected:
        pin(PREFIX + name)
    all_exceptions = None
    for mode, value in [('rc', 0), ('external', 1)]:
        sdc = screen / mode / 'applied.sdc'
        assert sha(sdc) == prior['constraint_sha256'][mode + '/applied.sdc']
        input_hashes[str(sdc.relative_to(ROOT))] = sha(sdc)
        lines = re.sub(r'\\\r?\n\s*', ' ', sdc.read_text()).splitlines()
        exceptions = []
        certified = set()
        for line in lines:
            if not line.startswith('set_multicycle_path '):
                continue
            def translate(match):
                names = [pin(PREFIX + n) for n in match.group(1).split()]
                certified.update(n.rsplit('/', 1)[0] for n in names)
                return '[chip_pins {' + ' '.join(names) + '}]'
            rewritten, count = re.subn(r'\[get_pins \{([^}]+)\}\]', translate, line)
            assert count >= 2 and '-through' not in rewritten
            assert line.count(' -from ') == 1 and line.count(' -to ') == 1
            exceptions.append(rewritten)
        assert exceptions and len(exceptions) % 2 == 0
        if all_exceptions is None:
            all_exceptions = exceptions
        else:
            assert exceptions == all_exceptions, 'Strap mode changed USB exceptions'
        clocks = f'''set_units -time ns -capacitance pF
proc chip_pins {{names}} {{
 set result [get_pins -quiet $names]
 if {{[llength $result] != [llength $names]}} {{error "Missing/ambiguous T38 pin: $names"}}
 return $result
}}
create_clock -name usb -period 20.833333333333333 [get_ports clk_PAD]
create_generated_clock -name main -source [get_ports clk_PAD] -divide_by 6 [chip_pins {{{divider}}}]
create_clock -name aon -period 31250 {'[chip_pins {i_chip_core.soc.lf/clock}]' if mode == 'rc' else '[get_ports {input_PAD[0]}]'}
create_clock -name tck -period 10000 [get_ports {{input_PAD[3]}}]
set_case_analysis {value} [chip_pins {{{select}}}]
# No asynchronous clock groups or false paths; retain raw CDC/RDC diagnostics.
# Physical buffering must reconnect load pins. OpenDB dont_touch also forbids
# that reconnection. Preserve identities/functions with post-stage graph audits
# instead; no remapping or gate cloning is enabled by this release.
if {{[llength [info commands unset_dont_touch]]}} {{
 unset_dont_touch [get_cells {{i_chip_core.soc.*}}]
}}
set_clock_uncertainty 0.25 [all_clocks]
set_clock_transition 0.15 [get_clocks {{usb main tck}}]
# Assumed 2.6ns LF edge covers the limited T43 measured SS 30-70% slew.
# It is not a characterized macro timing model or signoff envelope.
set_clock_transition 2.6 [get_clocks aon]
set_timing_derate -early 0.95
set_timing_derate -late 1.05
set_max_transition 3 [current_design]
set_max_fanout 10 [current_design]
# Inherited assumed template load: 72.91fF. Diagnostic external timing:
# inputs arrive 0..1ns from the reference edge; outputs assume a peer capture
# requirement of 1ns setup and 0ns hold, including board propagation.
# These assumptions are not peripheral/USB electrical qualification.
set_load 0.07291 [get_ports {{bidir_PAD[*]}}]
set_input_transition 0.5 [get_ports {{rst_n_PAD input_PAD[*] bidir_PAD[*]}}]
'''
        # Mixed/alternate pins get each relevant domain with -add_delay.
        # These arbitrary input phases preserve first-sampler diagnostics;
        # they do not assert source-synchronous protocols or CDC qualification.
        groups = {
            'main': ['input_PAD[6]', 'input_PAD[7]', 'input_PAD[8]', 'input_PAD[9]', 'input_PAD[10]'] +
                    [f'bidir_PAD[{i}]' for i in list(range(1, 8)) + list(range(9, 34))],
            'aon': ['rst_n_PAD', 'input_PAD[1]', 'input_PAD[2]'] +
                   [f'bidir_PAD[{i}]' for i in (0, 1, 2, 3, 37, 38, 39)],
            'usb': ['input_PAD[11]'] + [f'bidir_PAD[{i}]' for i in (34, 35, 36)],
            'tck': ['input_PAD[4]', 'input_PAD[5]', 'bidir_PAD[8]'],
        }
        for domain, ports in groups.items():
            collection = '[get_ports {' + ' '.join(ports) + '}]'
            for kind in ('input', 'output'):
                selected = ports if kind == 'input' else [n for n in ports if n.startswith('bidir_PAD')]
                if not selected:
                    continue
                collection = '[get_ports {' + ' '.join(selected) + '}]'
                for limit, delay in [('min', 0), ('max', 1)]:
                    clocks += f'set_{kind}_delay -{limit} {delay} -add_delay -clock {domain} {collection}\n'
        clocks += '\n'.join(exceptions) + '\n'
        clocks += '''if { [info exists ::env(OPENLANE_SDC_IDEAL_CLOCKS)] && $::env(OPENLANE_SDC_IDEAL_CLOCKS) } {
 unset_propagated_clock [all_clocks]
} else {
 set_propagated_clock [all_clocks]
}
'''
        (out / (mode + '.sdc')).write_text(clocks)
    cfg = json.loads(template.read_text())
    cfg.update(PNR_SDC_FILE=str(out / 'rc.sdc'), SIGNOFF_SDC_FILE=str(out / 'rc.sdc'),
               FALLBACK_SDC=str(out / 'rc.sdc'),
               RSZ_DONT_TOUCH_RX='^$',
               RSZ_DONT_TOUCH_LIST=None,
               DESIGN_REPAIR_REMOVE_BUFFERS=False,
               PL_RESIZER_SETUP_GATE_CLONING=False,
               PL_RESIZER_SETUP_BUFFER_REMOVAL=False,
               GRT_RESIZER_SETUP_GATE_CLONING=False,
               GRT_RESIZER_SETUP_BUFFER_REMOVAL=False)
    (out / 'config.json').write_text(json.dumps(cfg, indent=2) + '\n')
    # This is a new mapping, so do not carry old timing metrics/SDF/ODB.
    state = dict(nl=str(mapped / 'chip_top.v'),
                 json_h=str(mapped / 'mapped.json'),
                 metrics={})
    (out / 'initial-state.json').write_text(json.dumps(state, indent=2) + '\n')
    (out / 'expected-clocks.json').write_text(json.dumps({PREFIX + k: v for k, v in expected.items()}, indent=2))
    (out / 'result.json').write_text(json.dumps(dict(status='prepared_not_measured',
        input_sha256=input_hashes, exception_statements=len(all_exceptions),
        exception_registers=len(certified), clock_pins=len(expected),
        artifact_sha256={q.name: sha(q) for q in out.iterdir() if q.is_file()},
        scope='Pre-scan production clocks and exact imported USB exceptions; board/load/LF slew assumptions, complete CDC/RDC and analog qualification deferred'), indent=2) + '\n')
    print('PASS production clock and exception preparation; execution/coverage audit pending')


if __name__ == '__main__':
    main()

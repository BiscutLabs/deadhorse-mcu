"""Bind functional clocks and existing USB exceptions to the T37 scan mapping.

Preparation only. Physical graph preservation and executed clock coverage are
separate premises; this never applies functional exceptions in scan mode.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from hw.top.reference.measurements.plan04_screen import clock_manifest
from tools.physical.scan_manifest import sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    base=ROOT/'build/t37/production02/map'
    ref=ROOT/'build/t33/pre-fast03/fast/usb/timing/usb'
    mapping=json.loads((base/'result.json').read_text())
    assert mapping['status']=='mapped' and sha(base/'canonical.json')==mapping['mapped_sha256']
    mod=json.loads((base/'canonical.json').read_text())['modules']['DeadhorseSoc']
    original=json.loads((ref/'certificate/result.json').read_text())
    assert original['status']=='pass' and sha(ref/'mapped.json')==original['mapped_sha256']
    inputs=[Path(__file__),ROOT/'hw/top/reference/measurements/plan04_screen.py',
            base/'result.json',base/'canonical.json',base/'island-preservation.json',ref/'certificate/result.json',ref/'mapped.json']
    for name,digest in mapping['input_sha256'].items():
        path=ROOT/name.removeprefix('/work/');assert sha(path)==digest,name;inputs.append(path)
    for name,digest in original['proof_source_sha256'].items():
        path=ROOT/name.removeprefix('/work/');assert sha(path)==digest,name;inputs.append(path)
    island=json.loads((base/'island-preservation.json').read_text())
    assert island['status']=='pass' and island['reference_sha256']==sha(ref/'mapped.json')
    assert island['certificate_sha256']==sha(ref/'certificate/result.json')
    prefix='i_chip_core.soc.'
    def rename(n):
        key=mapping['replica_renames'].get('digital.subsystem.usb.'+n,'digital.subsystem.usb.'+n)
        assert key in mod['cells'];return prefix+key
    groups={g:[rename(n) for n in ns] for g,ns in original['reset_aware']['groups'].items()}
    pre={rename(n) for n in original['pre_enable']['capture_pins']}
    launches={n for g in original['pre_enable']['allowed_launch_groups'] for n in groups[g]}
    constraints=[]
    def pins(ns,suffix):return ' '.join(n+'/'+suffix for n in sorted(ns))
    def exception(first,last,setup,hold):
        for kind,v in (('setup',setup),('hold',hold)):
            constraints.append(f'set_multicycle_path {v} -{kind} -from [get_pins {{{pins(first,"CLK")}}}] -to [get_pins {{{pins(last,"D")}}}]')
    for first,last in original['reset_aware']['allowed_pairs']:exception(groups[first],groups[last],4,3)
    exception(launches,pre,3,2)
    def flop(net):
        bits=mod['netnames'][net]['bits']
        names=[prefix+n+'/Q' for n,c in mod['cells'].items() if c['connections'].get('Q')==bits and 'CLK' in c['connections']]
        assert len(names)==1;return names[0]
    divider=flop('_clocks_ungatedClock')
    analog=json.loads((base/'analog-sockets.json').read_text());inputs.append(base/'analog-sockets.json')
    rc=next(i['ports']['clock'] for i in analog if i['module']=='LfRcMacro')
    selects=[prefix+n+'/S' for n,c in mod['cells'].items() if c['type'].startswith('gf180mcu_fd_sc_mcu7t5v0__mux2_')
        and c['connections'].get('I0')==mod['ports'][rc]['bits'] and c['connections'].get('I1')==mod['ports']['aonClockIn']['bits']
        and c['connections'].get('S')==mod['netnames']['clocks.bootstrap.select']['bits']]
    assert len(selects)==1
    original_clocks=clock_manifest(mod)
    manifest_path=ROOT/'build/t37/scan-manifest02.json';inputs.append(manifest_path)
    manifest=json.loads(manifest_path.read_text())
    assert sha(base/'canonical.json') in manifest['input_sha256'].values()
    insertion_path=ROOT/'build/t37/insert05/result.json';inputs.append(insertion_path)
    insertion=json.loads(insertion_path.read_text())
    assert insertion['status']=='pass_unplaced_insertion'
    assert sha(base/'canonical.json') in insertion['input_sha256'].values()
    assert sha(manifest_path) in insertion['input_sha256'].values()
    excluded=manifest['excluded']
    expected={prefix+(n if prefix+n.rsplit('/',1)[0] in excluded else n.replace('/CLKN','/CLK')):v
              for n,v in original_clocks.items()}
    phases={prefix+(n if prefix+n.rsplit('/',1)[0] in excluded else n.replace('/CLKN','/CLK')):int(n.endswith('/CLKN'))
            for n,v in original_clocks.items() if v=='tck'}
    domains={}
    for pin,domain in original_clocks.items():
        name,port=pin.rsplit('/',1);bit=mod['cells'][name]['connections'][port][0]
        assert bit not in domains or domains[bit]==domain
        domains[bit]=domain
    # SRAM state is not in clock_manifest's D-flop set. Bind its actual clock
    # by the identical clock net of already classified registers.
    for n,c in mod['cells'].items():
        if 'ip_sram__' in c['type']:
            clock=c['connections']['CLK'];assert len(clock)==1 and clock[0] in domains
            expected[prefix+n+'/CLK']=domains[clock[0]]
    for mode,value in (('rc',0),('external',1)):
        lines=[f'create_clock -name usb -period 20.833333333333333 [get_ports clk_PAD]',
            f'create_generated_clock -name main -source [get_ports clk_PAD] -divide_by 6 [get_pins {{{divider}}}]',
            'create_clock -name aon -period 31250 '+('[get_pins {i_chip_core.soc.lf/clock}]' if mode=='rc' else '[get_ports {input_PAD[0]}]'),
            'create_clock -name tck -period 10000 [get_ports {input_PAD[3]}]',
            f'set_case_analysis {value} [get_pins {{{selects[0]}}}]',
            'set_clock_uncertainty 0.25 [all_clocks]',
            'set_clock_transition 0.15 [get_clocks {usb main tck}]',
            'set_clock_transition 2.6 [get_clocks aon]',
            'set_timing_derate -early 0.95','set_timing_derate -late 1.05',
            'set_max_transition 3 [current_design]','set_max_fanout 10 [current_design]',
            'set_input_transition 0.5 [get_ports {rst_n_PAD input_PAD[*] bidir_PAD[*]}]',
            'set_load 0.07291 [get_ports {bidir_PAD[*]}]',*constraints,'set_propagated_clock [all_clocks]']
        (a.output/(mode+'.sdc')).write_text('\n'.join(lines)+'\n')
    (a.output/'expected.json').write_text(json.dumps(expected,indent=2))
    (a.output/'phases.json').write_text(json.dumps(phases,indent=2))
    result=dict(status='prepared_functional_only',inputs={str(q.relative_to(ROOT)):sha(q) for q in inputs},
        artifacts={q.name:sha(q) for q in a.output.iterdir() if q.is_file()},
        scope='Existing clocks/USB certificates rebound to current mapping; IO/reset/CDC timing remains raw diagnostic, no acceptance waiver')
    (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Prepared functional clock/exception binding; execution audit required')


if __name__=='__main__':main()

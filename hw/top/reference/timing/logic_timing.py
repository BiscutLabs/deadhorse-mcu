"""Focused I0 logic STA at T20's two clocks; memory macros remain excluded."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from tools.timing.check import electrical_checks,result_status,validate_boundary


def checked_status(delay,budget,electrical,safety):
    if not math.isfinite(delay) or not safety or any(not math.isfinite(r['slack_ns']) or r['slack_ns']<0 for r in safety):return 'fail'
    return result_status(delay,budget,electrical)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mapped-dir',required=True)
    ap.add_argument('--output',required=True)
    ap.add_argument('--analysis',default='tools/timing/analyze.tcl')
    a=ap.parse_args()
    base=(ROOT/a.mapped_dir).resolve();base.relative_to(ROOT/'build')
    out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    analysis=(ROOT/a.analysis).resolve();analysis.relative_to(ROOT)
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    cfg=json.loads((ROOT/'phys/gf180-ws-1x1/block-timing.json').read_text())
    lib=ROOT/cfg['liberty']
    assert digest(lib)==cfg['sha256']
    module=json.loads((base/'mapped.json').read_text())['modules']['DeadhorseSoc']
    library=set(re.findall(r'\bcell\s*\(\s*"?([^\s"()]+)"?\s*\)',lib.read_text()))
    validate_boundary(module,'mainClock',library)
    gates=[(n,c) for n,c in module['cells'].items() if c['type']=='gf180mcu_fd_sc_mcu7t5v0__icgtp_1']
    assert len(gates)==1
    name,gate=gates[0]
    assert gate['connections']['TE']==['0'] and isinstance(gate['connections']['E'][0],int)
    reset_count=sum(1 for c in module['cells'].values() for p,b in c['connections'].items()
                    if p in ('RN','SETN') and isinstance(b[0],int))
    assert reset_count>0
    sources=[Path(__file__),ROOT/'tools/timing/check.py',analysis,lib,base/'mapped.json',base/'mapped.v',ROOT/'tools/env/lock.json',ROOT/'phys/gf180-ws-1x1/block-timing.json']
    snapshot={str(p.relative_to(ROOT)):digest(p) for p in sources}
    receipt=dict(status='running',scope='GF180 mapped pre-layout I0 logic, five synchronous memory interfaces cut; no macro timing/area, wires or physical signoff',
        sources=snapshot,results={},constant_gate_pins={name+'/TE':'0'},ci='not run')
    def read(p):
        with p.open() as f:return list(csv.DictReader(f,delimiter='\t'))
    try:
        for mhz in (8,9):
            directory=out/str(mhz);directory.mkdir()
            script=directory/'timing.tcl'
            script.write_text('\n'.join([
                f'set liberty {{{lib}}}',f'set netlist {{{base}/mapped.v}}','set top DeadhorseSoc',
                'set clock_port mainClock',f'set period {1000/mhz}','set combinational 0',
                f'set clock_gate_pins {{{name}/E}}',f'set input_transition {cfg["input_transition_ns"]}',
                f'set output_load {cfg["output_load_pf"]}',f'set path_report {{{directory}/paths.tsv}}',
                f'set gate_path_report {{{directory}/gate_checks.tsv}}',f'source {{{analysis}}}',
                f'set safety [open {{{directory}/short_reset.tsv}} w]',
                'puts $safety "check\\tstart\\tend\\tslack_ns"',
                'set resets [concat [get_pins -quiet */RN] [get_pins -quiet */SETN]]',
                'if {![llength $resets]} {error "Missing reset pins"}',
                'foreach {kind targets modes} [list hold [all_registers -data_pins] {min_rise min_fall} reset $resets {min_rise min_fall max_rise max_fall}] {',
                ' foreach mode $modes {',
                '  foreach path [find_timing_paths -to $targets -path_delay $mode -group_path_count [expr {2*[llength $targets]}] -endpoint_path_count 1] {',
                '   puts $safety "$kind/$mode\\t[get_full_name [get_property $path startpoint]]\\t[get_full_name [get_property $path endpoint]]\\t[get_property $path slack]"',
                '  }',' }','}','close $safety','puts T20_LOGIC_COMPLETE','']))
            run=subprocess.run(['sta','-no_init','-exit',str(script)],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            (directory/'sta.log').write_text(run.stdout)
            assert run.returncode==0 and 'T20_LOGIC_COMPLETE' in run.stdout and not re.search(r'(?m)^Error',run.stdout),run.stdout[-1000:]
            paths=read(directory/'paths.tsv');gchecks=read(directory/'gate_checks.tsv');safety=read(directory/'short_reset.tsv')
            for p in paths:p['delay_ns']=float(p['delay_ns'])
            assert paths and all(math.isfinite(p['delay_ns']) and p['delay_ns']>=0 for p in paths)
            assert {'RR','IR','RO','RG'}<={p['class'] for p in paths}
            assert len(gchecks)==4 and all(math.isfinite(float(r['slack_ns'])) and float(r['slack_ns'])>=0 for r in gchecks)
            assert {r['check'] for r in gchecks}=={'max_rise','max_fall','min_rise','min_fall'}
            assert safety
            for row in safety:row['slack_ns']=float(row['slack_ns'])
            assert all(math.isfinite(r['slack_ns']) for r in safety)
            # Both active-low asynchronous control pins release on rising edges.
            # Their falling edges assert reset and have no library recovery arc.
            for mode in ('reset/max_rise','reset/min_rise'):
                actual=[r['end'] for r in safety if r['check']==mode]
                assert len(actual)==len(set(actual))==reset_count,(mode,len(actual),reset_count)
            assert {'hold/min_rise','hold/min_fall'}<={r['check'] for r in safety}
            worst=max(paths,key=lambda p:p['delay_ns']);budget=.6*1000/mhz;electrical=electrical_checks(run.stdout)
            assert result_status(budget+1,budget,{'max_capacitance_and_slew_violations':0})=='fail'
            assert checked_status(0,budget,{'max_capacitance_and_slew_violations':0},[{'slack_ns':-0.001}])=='fail'
            receipt['results'][mhz]=dict(status=checked_status(worst['delay_ns'],budget,electrical,safety),budget_ns=budget,worst=worst,
                classes={k:max((r for r in paths if r['class']==k),key=lambda p:p['delay_ns']) for k in {p['class'] for p in paths}},
                electrical=electrical,gate_checks=gchecks,
                reset_endpoint_count=reset_count,short_reset_violations=[r for r in safety if r['slack_ns']<0],
                short_reset_worst={k:min((r for r in safety if r['check']==k),key=lambda r:r['slack_ns']) for k in {r['check'] for r in safety}})
            print(mhz,receipt['results'][mhz]['status'],worst['delay_ns'],electrical,flush=True)
        assert snapshot=={str(p.relative_to(ROOT)):digest(p) for p in sources},'Timing inputs changed'
        receipt['status']='logic_screening_pass' if all(r['status']=='pass' for r in receipt['results'].values()) else 'fail'
    except Exception as error:
        receipt.update(status='blocked',error=str(error));raise
    finally:
        receipt['artifacts']={str(p.relative_to(out)):digest(p) for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
        (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return 0 if receipt['status']=='logic_screening_pass' else 1


if __name__=='__main__':sys.exit(main())

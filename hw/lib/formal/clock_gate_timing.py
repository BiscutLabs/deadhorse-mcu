"""Characterize only the approved single GF180 ICG boundary; fail closed."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'dv/core'))
from common import local, output_dir, run
from isolation import reject_sources


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True); parser.add_argument('--output',required=True)
    parser.add_argument('--domain',choices=('main','aon','usb'),help='D78 production period; omitted preserves the existing fixture')
    args=parser.parse_args(); source=local(args.source); output=output_dir(args.output)
    receipt=output/'result.json'; receipt.write_text('{"status":"running"}\n')
    reject_sources([source])
    cfg=json.loads((ROOT/'phys/gf180-ws-1x1/block-timing.json').read_text())
    if args.domain:
        cfg=dict(cfg,period_ns={'main':125.0,'aon':31250.0,'usb':1000.0/48}[args.domain])
    library=ROOT/f'build/riscay-mcu/.tools/physical/pdk/{cfg["library"]}__{cfg["corner"]}.lib'
    if hashlib.sha256(library.read_bytes()).hexdigest()!=cfg['sha256']: raise ValueError('Library hash mismatch')
    cell='gf180mcu_fd_sc_mcu7t5v0__icgtp_1'
    script=output/'netlist.ys'
    script.write_text(f'read_liberty -lib {library}\nread_slang --top ClockGate {source}\n'
        f'hierarchy -check -top ClockGate\nwrite_json {output}/netlist.json\n')
    run(['yosys','-Q','-T','-s',script],output,'netlist')
    netlist=json.loads((output/'netlist.json').read_text())['modules']['ClockGate']
    if len(netlist['cells'])!=1: raise ValueError('Clock gate must contain exactly one ICG')
    instance=next(iter(netlist['cells'].values()))
    if instance['type']!=cell: raise ValueError('Unexpected clock-gate cell')
    for pin,port in {'CLK':'clk_i','E':'en_i','TE':'test_en_i','Q':'clk_o'}.items():
        if instance['connections'][pin]!=netlist['ports'][port]['bits']: raise ValueError('Clock-gate pin mismatch')
    tcl=output/'timing.tcl'
    tcl.write_text(f'set liberty {{{library}}}\nset source {{{source}}}\nset period {cfg["period_ns"]}\n'
        f'set transition {cfg["input_transition_ns"]}\nset load {cfg["output_load_pf"]}\n'
        f'set metrics {{{output}/metrics.tsv}}\nsource hw/lib/formal/clock_gate_timing.tcl\n')
    result=run(['sta','-exit',tcl],output,'timing')
    if 'CLOCK_GATE_TIMING_COMPLETE' not in result.stdout or re.search(r'(?m)^Error:',result.stdout):
        raise ValueError('Incomplete clock-gate STA')
    values={row['metric']:float(row['value_ns']) for row in csv.DictReader((output/'metrics.tsv').open(),delimiter='\t')}
    if len(values)!=10: raise ValueError('Missing clock/enable timing metrics')
    section=re.findall(r'ELECTRICAL_BEGIN\n(.*?)ELECTRICAL_END',result.stdout,re.S)
    if len(section)!=1: raise ValueError('Missing electrical report')
    violations=section[0].count('(VIOLATED)')
    delay=max(v for k,v in values.items() if k.startswith('clock_'))
    slack=min(v for k,v in values.items() if k.endswith('_slack'))
    budget=cfg['period_ns']*cfg['budget_fraction']
    area=float(re.search(r'cell\('+cell+r'\)\s*\{\s*area\s*:\s*([0-9.]+)',library.read_text())[1])
    status='pass' if delay<=budget and slack>=0 and violations==0 else 'fail'
    receipt.write_text(json.dumps(dict(status=status,kind='single-cell pre-layout screening',
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),library_sha256=cfg['sha256'],
        tool_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            (Path(__file__),ROOT/'hw/lib/formal/clock_gate_timing.tcl',ROOT/'phys/gf180-ws-1x1/block-timing.json')},
        clock_contract=args.domain or 'existing fixture',
        constraints=cfg,metrics_ns=values,clock_delay_ns=delay,minimum_enable_slack_ns=slack,
        electrical_violations=violations,cell_count=1,cell_area_um2=area,budget_ns=budget),indent=2)+'\n')
    if status!='pass': raise RuntimeError('Clock-gate timing/electrical checks failed')
    print(f'PASS ICG: clock delay {delay:.6f} ns; minimum enable slack {slack:.6f} ns; electrical violations {violations}')


if __name__=='__main__': main()

"""Unbounded gate-binding proof; independent PDK behavior is checked by Icarus."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'dv/core'))
from common import inputs, local, output_dir, run
from state_equiv import prepare


def prove(gold,candidate,out):
    a,b,evidence=prepare(gold,candidate,'ClockGate',out,{'en_latch':'ckg.en_latch'})
    script=out/'prove.ys'
    script.write_text(f'read_json {a}\nrename ClockGate gold\nread_json {b}\nrename ClockGate gate\n'
        'miter -equiv -flatten gold gate miter\nhierarchy -top miter\nopt_expr\nopt_clean\n'
        'sat -verify -prove trigger 0 -show-inputs -show-outputs\n')
    result=run(['yosys','-Q','-T','-s',script],out,'proof',allowed=(0,1))
    if result.returncode==0 and 'SUCCESS!' in result.stdout: return 'proved',evidence
    if result.returncode==1 and 'proof did fail' in result.stdout: return 'failed',evidence
    raise RuntimeError('Inconclusive clock-gate proof')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emitted',required=True); parser.add_argument('--output',required=True)
    args=parser.parse_args(); emitted=local(args.emitted); output=output_dir(args.output)
    inputs()
    reference=ROOT/'hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv'
    candidate=emitted/'model/ClockGate.sv'
    receipt=dict(status='running',assumptions=[],kind='unbounded named-state induction',
        scope='digital wrapper and verification binding; GF180 UDP model separately phase-tested',
        sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (reference,candidate)},faults={})
    path=output/'result.json'; path.write_text(json.dumps(receipt,indent=2)+'\n')
    for role in ('gold','candidate'):
        top='prim_generic_clock_gating' if role=='gold' else 'ClockGate'
        script=output/(role+'.ys')
        script.write_text(f'read_slang --top {top} {reference} '+(str(candidate) if role=='candidate' else '')+'\n'
            f'prep -top {top} -flatten\n'+('rename prim_generic_clock_gating ClockGate\n' if role=='gold' else '')+
            f'write_json {output}/{role}.json\n')
        run(['yosys','-Q','-T','-s',script],output,role)
    gold=output/'gold.json'; gate=output/'candidate.json'
    status,evidence=prove(gold,gate,output)
    if status!='proved': raise RuntimeError('Gate binding equivalence failed')
    receipt['correspondence']=evidence
    original=json.loads(gate.read_text())
    for name in ('lost_test_enable','inverted_capture'):
        variant=copy.deepcopy(original); module=variant['modules']['ClockGate']
        if name=='lost_test_enable':
            bit=module['ports']['test_en_i']['bits'][0]
            for cell in module['cells'].values():
                for port,bits in cell['connections'].items():
                    if cell['port_directions'][port]=='input': cell['connections'][port]=['0' if b==bit else b for b in bits]
        else:
            latch=next(c for c in module['cells'].values() if c['type']=='$dlatch')
            bit=max(b for net in module['netnames'].values() for b in net['bits'] if isinstance(b,int))+1
            module['cells']['fault_not']=dict(type='$not',parameters={'A_SIGNED':0,'A_WIDTH':1,'Y_WIDTH':1},
                attributes={},port_directions={'A':'input','Y':'output'},connections={'A':latch['connections']['D'],'Y':[bit]})
            latch['connections']['D']=[bit]
        directory=output_dir(output/name); variant_path=directory/'candidate.json'
        variant_path.write_text(json.dumps(variant))
        status,_=prove(gold,variant_path,directory)
        if status!='failed': raise RuntimeError('Clock-gate fault escaped: '+name)
        receipt['faults'][name]='rejected'
    receipt['covers']={}
    for name,enable,test,expected in [('closed',0,0,0),('functional',1,0,1),('test_only',0,1,1)]:
        directory=output_dir(output/('cover_'+name)); script=directory/'cover.ys'
        script.write_text(f'read_json {gate}\nclk2fflogic\nopt_clean\n'
            'sat -seq 3 -set-def-inputs '
            f'-set-at 1 clk_i 0 -set-at 1 en_i 0 -set-at 1 test_en_i 0 '
            f'-set-at 2 clk_i 0 -set-at 2 en_i {enable} -set-at 2 test_en_i {test} '
            f'-set-at 3 clk_i 1 -set-at 3 en_i 0 -set-at 3 test_en_i 0 -set-at 3 clk_o {expected} '
            f'-show-inputs -show-outputs -dump_vcd {directory}/trace.vcd\n')
        result=run(['yosys','-Q','-T','-s',script],directory,'cover')
        if 'SAT solving finished - model found:' not in result.stdout:
            raise RuntimeError('Unreachable clock-gate cover: '+name)
        receipt['covers'][name]=dict(status='covered',depth=3)
    # Actual implementation fault: capture only on falling edge. The phase
    # checker must reject this without corrupting any observed value.
    falling=copy.deepcopy(original); module=falling['modules']['ClockGate']
    latch=next(c for c in module['cells'].values() if c['type']=='$dlatch')
    latch['type']='$dff'; latch['parameters']={'WIDTH':1,'CLK_POLARITY':0}
    latch['connections']['CLK']=module['ports']['clk_i']['bits']; del latch['connections']['EN']
    latch['port_directions']['CLK']='input'; del latch['port_directions']['EN']
    directory=output_dir(output/'falling_edge_fault'); netlist=directory/'fault.json'
    netlist.write_text(json.dumps(falling))
    script=directory/'emit.ys'; script.write_text(f'read_json {netlist}\nwrite_verilog -noattr {directory}/ClockGate.sv\n')
    run(['yosys','-Q','-T','-s',script],directory,'emit')
    run([sys.executable,'hw/lib/formal/clock_gate_sim.py','--emitted',directory,
        '--output',directory/'simulation','--binding','model','--faulted'],directory,'simulation')
    receipt['faults']['falling_edge_only']='phase-model rejected'
    receipt['status']='proved'; path.write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS clock-gate binding induction and both negative controls')


if __name__=='__main__': main()

"""Prove retained SIE protocol-register enables imply clk_gate_i.

This certificate alone does NOT approve or apply a multicycle timing constraint.
All register values and PHY outputs are freed: a sound combinational
over-approximation for the clock-enable implication, with no reachability premise.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4]


def enable_port(cell):
    if cell['type']!='$adffe' or int(cell['parameters']['EN_POLARITY'],2)!=1:
        raise ValueError('Expected positive-enable asynchronous-reset flip-flop')
    return dict(direction='output',bits=cell['connections']['EN'])


def run(output,packet_bytes):
    output=Path(output).resolve();output.relative_to(ROOT/'build')
    if output.exists() and any(output.iterdir()):raise ValueError('Use fresh output')
    output.mkdir(parents=True)
    sources=[ROOT/'build/vendor/usb/rtl'/n for n in ('sie.v','phy_rx.v','phy_tx.v')]
    receipt=dict(status='running',source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        bulk_packet_bytes=packet_bytes,
        sizing_source_sha256=hashlib.sha256((ROOT/'hw/ip/usb/src/main/scala/deadhorse/usb/UsbPacketSizing.scala').read_bytes()).hexdigest(),
        scope='SIE protocol register CE implication only; not mapped pin membership, hold timing, reset recovery or multicycle authorization',
        abstraction='All SIE sequential Q values and PHY outputs are independent arbitrary inputs',registers=[])
    def command(name,script,expected=0):
        path=output/(name+'.ys');path.write_text(script+'\n')
        result=subprocess.run(['yosys','-Q','-T','-s',str(path)],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (output/(name+'.log')).write_text(result.stdout)
        if result.returncode!=expected:raise RuntimeError(name+' returned '+str(result.returncode))
        return result.stdout
    try:
        command('prepare','\n'.join([
            f'read_slang --keep-hierarchy --top sie -GIN_CTRL_MAXPACKETSIZE=8 -GIN_BULK_MAXPACKETSIZE={packet_bytes} -GBIT_SAMPLES=4 '+' '.join(map(str,sources)),
            'proc','opt',f'write_json {output}/prepared.json']))
        design=json.loads((output/'prepared.json').read_text());module=design['modules']['sie']
        model=copy.deepcopy(module);enables=[];cut=0;common_reset=None
        for name,cell in module['cells'].items():
            kind=cell['type'];pins=cell['connections']
            if kind=='$adffe':
                if common_reset is None:common_reset=pins['ARST']
                if (pins['CLK']!=module['ports']['clk_i']['bits'] or pins['ARST']!=common_reset or len(common_reset)!=1 or
                    int(cell['parameters']['EN_POLARITY'],2)!=1 or int(cell['parameters']['CLK_POLARITY'],2)!=1 or
                    int(cell['parameters']['ARST_POLARITY'],2)!=0):raise ValueError('Unsupported clock/enable/reset binding')
                port=f'eligible_{len(enables)}';enables.append(port)
                model['ports'][port]=enable_port(cell)
                aliases={n:v['bits'] for n,v in module['netnames'].items() if not n.startswith('$') and set(pins['Q'])&set(v['bits'])}
                receipt['registers'].append(dict(cell=name,q=pins['Q'],aliases=aliases,enable_port=port))
                model['ports'][f'free_q_{cut}']=dict(direction='input',bits=pins['Q']);cut+=1
                del model['cells'][name]
            elif kind.startswith(('phy_rx$', 'phy_tx$')):
                for port,direction in cell['port_directions'].items():
                    if direction=='output':model['ports'][f'free_phy_{cut}']=dict(direction='input',bits=pins[port]);cut+=1
                    elif direction!='input':raise ValueError('Unsupported PHY bidirectional port')
                del model['cells'][name]
            elif 'dff' in kind or 'latch' in kind or kind in design['modules']:
                raise ValueError('Unclassified sequential/hierarchical cell '+kind)
        if not enables:raise ValueError('No certified registers')
        receipt['common_async_reset_aliases']=[n for n,v in module['netnames'].items() if v['bits']==common_reset]
        for variant in ('correct','corrupt'):
            candidate=copy.deepcopy(model)
            if variant=='corrupt':
                # Mutate the real prepared register, then use the same enable
                # extraction as the positive certificate, rather than merely
                # overwriting an already extracted proof output.
                mutant=copy.deepcopy(design)
                broken=mutant['modules']['sie']['cells'][receipt['registers'][0]['cell']]
                broken['connections']['EN']=['1']
                (output/'corrupt-prepared.json').write_text(json.dumps(mutant))
                candidate['ports'][enables[0]]=enable_port(broken)
            path=output/(variant+'.json');path.write_text(json.dumps({'modules':{'sie':candidate}}))
            proof=' '.join(f'-prove {port} 0' for port in enables)
            log=command(variant,'\n'.join([f'read_json {path}','hierarchy -top sie','opt_clean','check -assert','techmap','opt',
                f'sat -set-def-inputs -set clk_gate_i 0 {proof} -dump_vcd {output}/{variant}.vcd -verify']),1 if variant=='corrupt' else 0)
            marker='proof did fail' if variant=='corrupt' else 'SUCCESS!'
            if marker not in log:raise ValueError('Missing proof result '+variant)
            if variant=='corrupt' and not (output/'corrupt.vcd').exists():raise ValueError('Missing counterexample')
        receipt['status']='pass';receipt['register_cells']=len(enables)
    except Exception as error:receipt.update(status='failed',error=str(error))
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper()+' SIE enable implication; no timing exception applied')
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    parser.add_argument('--packet-bytes',type=int,choices=(8,16,32,64),required=True)
    args=parser.parse_args();sys.exit(0 if run(ROOT/args.output,args.packet_bytes)['status']=='pass' else 1)

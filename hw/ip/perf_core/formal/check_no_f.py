"""Local no-F/FS-Off conditional equivalence, including new-state invariants."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'dv/core'))
from common import output_dir
from candidate import parameters
from equiv import elaborate,compare
from state_equiv import STATE

class Logic:
    def __init__(self,module):
        self.m=module
        self.fresh=1+max(b for n in module['netnames'].values() for b in n['bits'] if isinstance(b,int))
    def cell(self,kind,ports,width=1):
        result=list(range(self.fresh,self.fresh+width));self.fresh+=width
        params={'Y_WIDTH':format(width,'b')};directions={'Y':'output'};connections={'Y':result}
        for name,bits in ports.items():
            connections[name]=bits;directions[name]='input'
            if name!='S': params.update({name+'_WIDTH':format(len(bits),'b'),name+'_SIGNED':'0'})
        if kind=='$mux': params={'WIDTH':format(width,'b')}
        name='__t13_'+str(result[0]);self.m['cells'][name]=dict(type=kind,parameters=params,
            attributes={},port_directions=directions,connections=connections)
        self.m['netnames'][name+'_wire']=dict(hide_name=0,bits=result,attributes={})
        return result
    def eq(self,bits,value): return self.cell('$eq',dict(A=bits,B=list(reversed(format(value,f'0{len(bits)}b')))))
    def either(self,a,b): return self.cell('$logic_or',dict(A=a,B=b))
    def both(self,a,b): return self.cell('$logic_and',dict(A=a,B=b))
    def inv(self,a): return self.cell('$not',dict(A=a),len(a))
    def mux(self,s,a,b): return self.cell('$mux',dict(A=a,B=b,S=s),len(a))
    def output(self,name,bits):
        self.m['ports'][name]=dict(direction='output',bits=bits)
        self.m['netnames'][name]=dict(hide_name=0,bits=bits,attributes={})
    def input(self,name,width):
        bits=list(range(self.fresh,self.fresh+width));self.fresh+=width
        self.m['ports'][name]=dict(direction='input',bits=bits)
        self.m['netnames'][name]=dict(hide_name=0,bits=bits,attributes={})

def remap(module,replacements):
    def bits(values): return [replacements.get(b,b) for b in values]
    for c in module['cells'].values():
        c['connections']={name:bits(value) for name,value in c['connections'].items()}
    for category in ('ports','netnames'):
        for n in module[category].values(): n['bits']=bits(n['bits'])

def state(module,name):
    bits=module['netnames'][name]['bits']
    matches=[(n,c) for n,c in module['cells'].items() if c['type'] in STATE and c['connections']['Q']==bits]
    if len(matches)!=1: raise ValueError('Missing unique state: '+name)
    return matches[0]

def project(gold,gate,module):
    gold,gate=copy.deepcopy(gold),copy.deepcopy(gate)
    a,b=gold['modules'][module],gate['modules'][module]
    if module=='ibex_compressed_decoder':
        for m in (a,b):
            logic=Logic(m);instruction=m['ports']['instr_i']['bits']
            quadrant=logic.either(logic.eq(instruction[:2],0),logic.eq(instruction[:2],2))
            operation=logic.either(logic.eq(instruction[13:16],3),logic.eq(instruction[13:16],7))
            allowed=logic.inv(logic.both(quadrant,operation))
            for name,port in list(m['ports'].items()):
                if port['direction']=='output':
                    logic.output(name,logic.mux(allowed,['0']*len(port['bits']),port['bits']))
        return gold,gate
    if module!='ibex_cs_registers': raise ValueError(module)
    la,lb=Logic(a),Logic(b)
    # No committed F instruction; operand/flag observations remain unrestricted.
    commit=b['ports'].pop('fp_commit_i')['bits']
    remap(b,{bit:'0' for bit in commit})
    for name in ('fp_flags_i','fp_dirty_i'): la.input(name,len(b['ports'][name]['bits']))
    removed=[]; replacements={}
    for name in ('fpStatus','fcsr'):
        key,c=state(b,name);c=copy.deepcopy(c)
        if c['type'] not in ('$aldff','$adff') or c['connections']['CLK']!=b['ports']['clk_i']['bits'] or int(c['parameters']['CLK_POLARITY'],2)!=1:
            raise ValueError('Unexpected added-state clock/reset form')
        if c['type']=='$aldff':
            if set(c['connections']['AD'])!={'0'}: raise ValueError('Added state does not reset to zero')
            reset=c['connections']['ALOAD'];polarity=int(c['parameters']['ALOAD_POLARITY'],2)
        else:
            if int(c['parameters']['ARST_VALUE'],2): raise ValueError('Added state does not reset to zero')
            reset=c['connections']['ARST'];polarity=int(c['parameters']['ARST_POLARITY'],2)
        active=reset if polarity else lb.inv(reset)
        la.output('__reset_'+name,['1'])
        lb.output('__reset_'+name,lb.either(b['ports']['rst_ni']['bits'],active))
        replacements.update({bit:'0' for bit in c['connections']['Q']})
        removed.append((name,c));del b['cells'][key]
    remap(b,replacements)
    for name in ('fp_fs_o','fp_fcsr_o'): la.output(name,['0']*len(b['ports'][name]['bits']))
    ports=b['ports']
    write=lb.either(lb.eq(ports['csr_op_i']['bits'],1),lb.eq(ports['csr_op_i']['bits'],2))
    privilege=lb.either(lb.inv(ports['csr_access_i']['bits']),lb.eq(ports['priv_mode_id_o']['bits'],3))
    effective=lb.both(lb.both(lb.eq(ports['csr_addr_i']['bits'],0x300),ports['csr_op_en_i']['bits']),lb.both(write,privilege))
    allowed=lb.inv(lb.both(effective,lb.inv(lb.eq(ports['csr_wdata_i']['bits'][13:15],0))))
    for name,c in removed:
        data=[replacements.get(bit,bit) for bit in c['connections']['D']]
        la.output('__invariant_'+name,['0']*len(data))
        lb.output('__invariant_'+name,lb.mux(allowed,['0']*len(data),data))
    # Only the explicitly advertised misa.F difference is normalized.
    data=list(ports['csr_rdata_o']['bits'])
    data[5]=lb.mux(lb.eq(ports['csr_addr_i']['bits'],0x301),[data[5]],['0'])[0]
    lb.output('csr_rdata_o',data)
    return gold,gate

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',required=True);parser.add_argument('--candidate',required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args()
    parameters(args.baseline);parameters(args.candidate);out=output_dir(args.output)
    receipt=dict(status='running',modules={});path=out/'result.json';path.write_text(json.dumps(receipt))
    try:
        for module in ('ibex_compressed_decoder','ibex_cs_registers'):
            directory=output_dir(out/module)
            raw=[elaborate(module,p,directory,role) for p,role in ((args.baseline,'baseline'),(args.candidate,'candidate'))]
            originals=[json.loads(p.read_text()) for p in raw]
            variants=['normal','output-fault']+(['invariant-fault'] if module=='ibex_cs_registers' else [])
            checks={}
            for variant in variants:
                models=copy.deepcopy(originals);m=models[1]['modules'][module];logic=Logic(m)
                if variant=='output-fault':
                    name='instr_o' if module=='ibex_compressed_decoder' else 'csr_mstatus_mie_o'
                    old=list(m['ports'][name]['bits']);old[0]=logic.inv([old[0]])[0];logic.output(name,old)
                if variant=='invariant-fault':
                    _,cell=state(m,'fpStatus');cell['connections']['D'][0]=logic.inv([cell['connections']['D'][0]])[0]
                projected=project(*models,module);destination=output_dir(directory/variant)
                files=[destination/'baseline.json',destination/'candidate.json']
                for file,model in zip(files,projected): file.write_text(json.dumps(model))
                status=compare(module,*files,destination)
                if status!=('proved' if variant=='normal' else 'failed'): raise ValueError('Unexpected conditional result: '+module+'/'+variant)
                checks[variant]=status
            receipt['modules'][module]=dict(status='proved',checks=checks,
                production={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in raw},
                assumptions=['No C.FLW/C.FSW/C.FLWSP/C.FSWSP encodings; all other encodings and valid inputs unrestricted'] if module=='ibex_compressed_decoder' else
                ['Initial reset; equal legacy state; candidate FS/fcsr initially zero (reset and next-state invariants proved)',
                 'No F commit; effective mstatus WRITE/SET cannot set FS; CLEAR unrestricted'],
                projection=[] if module=='ibex_compressed_decoder' else ['misa read bit5 only'],
                scope='conditional local induction/combinational equivalence; not core latency refinement')
            path.write_text(json.dumps(receipt,indent=2)+'\n')
        receipt['status']='pass';print('PASS local no-F/FS-Off equivalence and state invariants; real faults rejected')
    except BaseException as exc: receipt.update(status='failed',error=str(exc));raise
    finally: path.write_text(json.dumps(receipt,indent=2)+'\n')

if __name__=='__main__': main()

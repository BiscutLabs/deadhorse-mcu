"""Focused all-retirement JALR link-value proof; never an aggregate ISA pass.

Uses an authenticated frozen production checker, with no new assumptions.
Original reset/clock assumptions survive. Only the independent lemma removes
instruction selection; the original target partition keeps every assumption.
"""
import argparse
import copy
import json
from pathlib import Path
import sys

from common import ROOT, local, output_dir, run
from assertion_partitions import TOP, assertions, partition
from jalr_invariant import PREFIX, digest, flavor, gate, next_bit, property_cell, independent
from jalr_receipts import snapshot_baseline_audit


def attach(original,monitor):
    result=copy.deepcopy(original);m=result['modules'][TOP]
    ports={'reset':'checker_inst.reset','valid':'checker_inst.rvfi_valid',
           'instruction':'checker_inst.rvfi_insn','retiredPc':'checker_inst.rvfi_pc_rdata',
           'reportedValue':'checker_inst.rvfi_rd_wdata'}
    mapping={};fresh=next_bit(m)
    for port,net in ports.items():
        old=monitor['ports'][port]['bits'];new=m['netnames'][net]['bits']
        if len(old)!=len(new): raise ValueError('Monitor input width mismatch')
        mapping.update(zip(old,new))
    all_bits={b for c in monitor['cells'].values() for values in c['connections'].values()
              for b in values if isinstance(b,int)}
    for bit in sorted(all_bits-set(mapping)):
        mapping[bit]=fresh;fresh+=1
    for name,cell in monitor['cells'].items():
        key='__jalr_link_monitor_'+name
        if key in m['cells']: raise ValueError('Monitor cell collision')
        c=copy.deepcopy(cell)
        c['connections']={p:[mapping.get(b,b) for b in bits] for p,bits in c['connections'].items()}
        m['cells'][key]=c
    outputs={p:[mapping.get(b,b) for b in monitor['ports'][p]['bits']] for p in ('active','holds','coverZero','coverLink')}
    # Explicitly verify the graft did not change even one original object.
    restored=copy.deepcopy(result)
    for n in set(m['cells'])-set(original['modules'][TOP]['cells']):
        del restored['modules'][TOP]['cells'][n]
    if restored!=original: raise ValueError('Monitor changed original design')
    return result,outputs


def cone(module,outputs):
    """Qualification ONLY: all checker inputs free, no CPU assumptions/state."""
    cuts={n:v['bits'] for n,v in module['netnames'].items()
          if n.startswith('checker_inst.rvfi_') or n in ('checker_inst.reset','checker_inst.check')}
    cutbits={b for bits in cuts.values() for b in bits if isinstance(b,int)}
    drivers={}
    for name,c in module['cells'].items():
        for p,d in c['port_directions'].items():
            if d=='output':
                for bit in c['connections'][p]:
                    if isinstance(bit,int): drivers.setdefault(bit,[]).append(name)
    selected={};seen=set();pending=[b for bits in outputs.values() for b in bits]
    while pending:
        bit=pending.pop()
        if not isinstance(bit,int) or bit in cutbits or bit in seen: continue
        seen.add(bit);names=drivers.get(bit,[])
        if len(names)!=1: raise ValueError('Qualification cone has ambiguous/free internal driver')
        n=names[0];c=module['cells'][n]
        if flavor(c) or c['type'] not in ('$and','$or','$not','$logic_not','$logic_and',
                '$logic_or','$add','$eq','$ne','$reduce_or','$reduce_bool','$mux','$pmux'):
            raise ValueError('Non-combinational/unexpected qualification cell: '+c['type'])
        selected[n]=copy.deepcopy(c)
        pending.extend(b for p,d in c['port_directions'].items() if d=='input' for b in c['connections'][p])
    # Aliased or constant RVFI inputs are omitted unless actually used.
    needed={b for c in selected.values() for p,d in c['port_directions'].items() if d=='input'
            for b in c['connections'][p] if b in cutbits}
    ports={f'input_{b}':dict(direction='input',bits=[b]) for b in sorted(needed)}
    ports.update({n:dict(direction='output',bits=bits) for n,bits in outputs.items()})
    nets={n:dict(hide_name=0,bits=p['bits'],attributes={}) for n,p in ports.items()}
    return dict(modules={TOP:dict(attributes={'top':'1'},ports=ports,cells=selected,netnames=nets)})



def link_witness(text,kind):
    """Read settled VCD frames, independently calculate the architectural value."""
    scope=[];names={};values={};time=0;found=[]
    wanted=['rvfi_testbench.checker_inst.reset','rvfi_testbench.rvfi_valid',
            'rvfi_testbench.rvfi_insn','rvfi_testbench.rvfi_pc_rdata','rvfi_testbench.rvfi_rd_wdata']
    def sample():
        if not all(n in names and names[n] in values for n in wanted): return
        bits=[values[names[n]] for n in wanted]
        if any(set(b)-set('01') for b in bits): return
        reset,valid,insn,pc,value=[int(b,2) for b in bits];rd=(insn>>7)&31
        if reset or not valid or insn&127!=0x67 or (insn>>12)&7: return
        expected=(pc+4)&0xffffffff if rd else 0
        if (kind=='cover-zero' and not rd and value==expected or
            kind=='cover-link' and rd and value==expected or
            kind=='fault' and rd and value!=expected):
            found.append(dict(time=time,instruction=hex(insn),encoded_rd=rd,
                              retired_pc=hex(pc),expected=hex(expected),reported=hex(value)))
    for line in text.splitlines():
        parts=line.split()
        if not parts: continue
        if parts[0]=='$scope': scope.append(parts[2])
        elif parts[0]=='$upscope': scope.pop()
        elif parts[0]=='$var': names['.'.join(scope+[parts[4]])]=parts[3]
        elif line.startswith('#'): sample();time=int(line[1:])
        elif line[0] in 'bB' and len(parts)==2: values[parts[1]]=parts[0][1:]
        elif line[0] in '01xXzZ': values[line[1:]]=line[0]
    sample()
    if not found: raise ValueError('No active JALR '+kind+' witness')
    return found[0]


def mutate_increment(model):
    targets=[]
    for name,c in model['modules'][TOP]['cells'].items():
        if not name.startswith('__jalr_link_monitor_') or c['type']!='$add': continue
        bits=c['connections'].get('B',[])
        if not bits or set(bits)-{'0','1'} or int(''.join(reversed(bits)),2)!=4: continue
        params=c['parameters']
        if (len(c['connections']['A'])!=32 or len(c['connections']['Y'])!=32 or
            int(params['A_WIDTH'],2)!=32 or int(params['Y_WIDTH'],2)!=32 or
            int(params['B_WIDTH'],2)!=len(bits) or int(params['A_SIGNED'],2) or int(params['B_SIGNED'],2)):
            raise ValueError('Unexpected link-adder width or signedness')
        targets.append((name,c))
    if len(targets)!=1: raise ValueError('Link increment fault target not unique')
    name,c=targets[0]
    c['connections']['B']=list(reversed(format(8,'032b')))
    c['parameters']['B_WIDTH']=format(32,'032b')
    return name


def qualify(attached,signals,target,out):
    q=copy.deepcopy(attached)['modules'][TOP]
    check=q['netnames']['checker_inst.check']['bits'];valid=q['netnames'][PREFIX+'spec_valid']['bits']
    upstream=gate(q,'$and',target['connections']['EN'],valid)
    helper=gate(q,'$and',signals['active'],check)
    active_equal=gate(q,'$eq',upstream,helper)
    bad_original=gate(q,'$and',upstream,gate(q,'$not',target['connections']['A']))
    bad_helper=gate(q,'$and',check,gate(q,'$not',signals['holds']))
    violation_equal=gate(q,'$eq',bad_original,bad_helper)
    forced=[c for n,c in q['cells'].items() if flavor(c)=='assume' and n.startswith('$flatten\\checker_inst.')]
    if len(forced)!=1 or forced[0]['type']!='$check' or int(forced[0]['parameters']['TRG_ENABLE'],2):
        raise ValueError('Expected one combinational instruction-selection assumption')
    enable=gate(q,'$and',gate(q,'$not',q['netnames']['checker_inst.reset']['bits']),check)
    assumption_enable_equal=gate(q,'$eq',forced[0]['connections']['EN'],enable)
    design=cone(q,dict(active_equal=active_equal,violation_equal=violation_equal,
                      assumption_enable_equal=assumption_enable_equal))
    files=[];results={}
    for role in ('positive','negative'):
        job=output_dir(out/('qualification-'+role));model=copy.deepcopy(design)
        if role=='negative':
            name=mutate_increment(model)
            results['mutation']=dict(cell=name,change='PC+4 -> PC+8')
        path=job/'model.json';path.write_text(json.dumps(model));ys=job/'check.ys'
        witness=job/'counterexample.json'
        ys.write_text(f'read_json {path}\ncheck -assert\nsat '+('-verify ' if role=='positive' else '')+
            '-prove active_equal 1 -prove violation_equal 1 -prove assumption_enable_equal 1 '
            f'-show-inputs -show-outputs -dump_json {witness}\n')
        before={p:digest(p) for p in (path,ys)}
        result=run(['yosys','-Q','-T','-s',ys],job,'check',timeout=120)
        expected='SAT proof finished - no model found: SUCCESS!' if role=='positive' else 'SAT proof finished - model found: FAIL!'
        if expected not in result.stdout: raise ValueError('Unsuccessful guard qualification '+role)
        if role=='negative' and (not witness.is_file() or not witness.stat().st_size):
            raise ValueError('Missing qualification counterexample')
        if any(digest(p)!=h for p,h in before.items()): raise ValueError('Qualification inputs changed')
        files.extend([path,ys]);results[role]=dict(status='PASS' if role=='positive' else 'rejected',seconds=result.elapsed_seconds)
        if role=='negative': results['counterexample_sha256']=digest(witness)
    return files,results


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();base=local(args.baseline);out=output_dir(args.output)
    record=out/'result.json';receipt=dict(status='running',scope='JALR link value only; aggregate ISA incomplete',results={})
    record.write_text(json.dumps(receipt));protected={}
    try:
        audit_snapshot=snapshot_baseline_audit(base,out)
        evidence=json.loads((base/'result.json').read_text())
        timeout=evidence['timeout_seconds'];depth=evidence['depth']
        if timeout>120: raise ValueError('Focused experiment cap is 120 seconds')
        protected=dict(evidence['input_sha256'])
        for p in (base/'result.json',audit_snapshot,Path(__file__),ROOT/'dv/core/jalr_receipts.py',
                  ROOT/'dv/core/audit_jalr_invariant.py',ROOT/'hw/ip/perf_core/formal/JalrLinkProperty.scala'):
            protected[str(p)]=digest(p)
        original=json.loads((base/'original.json').read_text())
        run([sys.executable,'tools/sbt.py',
            'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/perf_core/formal")',
            f'hw/runMain deadhorse.perf_core.formal.EmitJalrLinkProperty {out}'],out,'emit-property')
        ys=out/'monitor.ys';monitor_path=out/'monitor.json'
        ys.write_text(f'read_slang --top JalrLinkProperty {out}/JalrLinkProperty.sv\n'
                      f'prep -top JalrLinkProperty -flatten\nwrite_json {monitor_path}\n')
        run(['yosys','-Q','-T','-s',ys],out,'monitor')
        attached,signals=attach(original,json.loads(monitor_path.read_text())['modules']['JalrLinkProperty'])
        targets=[n for n in assertions(original) if 'rvfi_insn_check.sv:177$assert' in n]
        if len(targets)!=1: raise ValueError('Original JALR link-value assertion not unique')
        target=attached['modules'][TOP]['cells'][targets[0]]
        if target['type']!='$check' or int(target['parameters']['TRG_ENABLE'],2):
            raise ValueError('Expected original combinational assertion')
        files,qualification=qualify(attached,signals,target,out)
        model,removed=independent(original,attached,signals)
        m=model['modules'][TOP];m['cells']['__jalr_link_assert']=m['cells'].pop('__jalr_address_assert')
        receipt.update(qualification=qualification,removed_only_in_independent_lemma=removed,
            original_assertions=assertions(original),target_assertion=targets[0],depth=depth,timeout_seconds=timeout,
            assumptions=['original reset == initstate','original alternating-clock initialization sequence'])
        for p,h in protected.items():
            if digest(local(p))!=h: raise ValueError('Source changed during preparation: '+p)
        for p in [*files,ys,monitor_path,out/'JalrLinkProperty.sv']:
            protected[str(p)]=digest(p)
        receipt['input_sha256']=protected;record.write_text(json.dumps(receipt,indent=2)+'\n')
        for role in ('prove','cover-zero','cover-link','fault','original-link-value'):
            job=output_dir(out/role);design=copy.deepcopy(model);m=design['modules'][TOP]
            mode='prove';engine='abc pdr'
            if role.startswith('cover-'):
                m['cells']['__jalr_link_assert']=property_cell('cover',signals['coverZero' if role=='cover-zero' else 'coverLink'])
                mode='cover';engine='btor btormc'
            if role=='fault':
                bit=m['netnames']['checker_inst.rvfi_rd_wdata']['bits'][0]
                drivers=[(n,p,i) for n,c in m['cells'].items() for p,d in c['port_directions'].items()
                    if d=='output' for i,b in enumerate(c['connections'][p]) if b==bit]
                if len(drivers)!=1: raise ValueError('Reported value needs unique real driver')
                n,p,i=drivers[0];fresh=next_bit(m);m['cells'][n]['connections'][p][i]=fresh
                # Corrupt the real reported bit only for a nonzero destination.
                # This fault injection condition never restricts the environment.
                m['cells']['__jalr_link_output_fault']=dict(type='$xor',parameters={'A_WIDTH':'1','A_SIGNED':'0',
                    'B_WIDTH':'1','B_SIGNED':'0','Y_WIDTH':'1'},attributes={},
                    port_directions={'A':'input','B':'input','Y':'output'},
                    connections={'A':[fresh],'B':signals['coverLink'],'Y':[bit]})
                receipt['fault_driver']=[n,p,i];mode='bmc';engine='btor btormc'
            if role=='original-link-value':
                augmented=copy.deepcopy(attached)
                augmented['modules'][TOP]['cells']['__jalr_link_assert']=property_cell('assert',signals['holds'])
                design=partition(augmented,[targets[0],'__jalr_link_assert'])
                receipt['original_partition']=dict(helper='assert, never assume',
                    unverified_original_assertions=[n for n in assertions(original) if n!=targets[0]])
            path=job/'model.json';path.write_text(json.dumps(design))
            config=job/'check.sby';config.write_text(f'[options]\nmode {mode}\ndepth {depth}\n'
                f'multiclock on\ntimeout {timeout}\n[engines]\n{engine}\n[script]\nread_json {path}\nopt_clean\n')
            protected.update({str(p):digest(p) for p in (path,config)})
            result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=timeout+30)
            for p,h in protected.items():
                if digest(local(p))!=h: raise ValueError('Proof input changed: '+p)
            status=(job/'work/status').read_text().split()[0]
            receipt['results'][role]=dict(status=status,returncode=result.returncode,seconds=result.elapsed_seconds)
            record.write_text(json.dumps(receipt,indent=2)+'\n')
            expected=('FAIL',2) if role=='fault' else ('PASS',0)
            if (status,result.returncode)!=expected: raise RuntimeError(f'JALR link {role}: {status}')
            if role.startswith('cover-') or role=='fault':
                witnesses=[]
                for trace in (job/'work').glob('engine_*/trace*.vcd'):
                    try: witnesses.append(dict(path=str(trace),sha256=digest(trace),retirement=link_witness(trace.read_text(),role)))
                    except ValueError: continue
                if not witnesses: raise ValueError('Missing active '+role+' witness')
                receipt['results'][role]['witnesses']=witnesses
            print(f'JALR link {role}: {status}',flush=True)
        receipt['status']='pass (link lemma and original value assertion only)'
    except BaseException as exc:
        receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected;record.write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__': main()

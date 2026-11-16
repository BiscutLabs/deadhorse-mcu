"""Independent JALR address lemma on an unchanged freshly prepared ISA model.

This diagnostic never grants an ISA pass. The original checker is retained as
an artifact; only this separate lemma removes its forced-at-cycle-64 JALR
assumption. All reset/clock assumptions and production cells survive exactly.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys

from common import ROOT, output_dir, run
from assertion_partitions import TOP, assertions, partition, stabilize_generated_names

PREFIX='checker_inst.channel[0].'


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def flavor(cell):
    if cell['type']=='$check': return cell['parameters']['FLAVOR']
    return {'$assert':'assert','$assume':'assume','$cover':'cover'}.get(cell['type'])


def next_bit(module):
    return 1+max(b for c in module['cells'].values() for bits in c['connections'].values()
                 for b in bits if isinstance(b,int))


def gate(module,kind,a,b=None):
    result=[next_bit(module)]
    conn={'A':a,'Y':result};params={'A_WIDTH':format(len(a),'b'),'A_SIGNED':'0','Y_WIDTH':'1'}
    if b is not None:
        conn['B']=b;params.update(B_WIDTH=format(len(b),'b'),B_SIGNED='0')
    module['cells']['__jalr_gate_'+str(result[0])]=dict(type=kind,parameters=params,
        attributes={},port_directions={p:'output' if p=='Y' else 'input' for p in conn},connections=conn)
    return result


def attach(original,monitor):
    result=copy.deepcopy(original);m=result['modules'][TOP]
    ports={'reset':'checker_inst.reset','valid':'checker_inst.rvfi_valid',
           'instruction':'checker_inst.rvfi_insn','reportedAddress':'checker_inst.rvfi_rs1_addr'}
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
        key='__jalr_monitor_'+name
        if key in m['cells']: raise ValueError('Monitor cell collision')
        c=copy.deepcopy(cell)
        c['connections']={p:[mapping.get(b,b) for b in bits] for p,bits in c['connections'].items()}
        m['cells'][key]=c
    outputs={p:[mapping.get(b,b) for b in monitor['ports'][p]['bits']] for p in ('active','holds')}
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
                '$logic_or','$eq','$ne','$reduce_or','$reduce_bool','$mux','$pmux'):
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


def property_cell(kind,a,en=['1']):
    return dict(type='$'+kind,parameters={},attributes={},
        port_directions={'A':'input','EN':'input'},connections={'A':a,'EN':en})


def independent(original,attached,signals):
    result=copy.deepcopy(attached);m=result['modules'][TOP]
    removed={n:c for n,c in m['cells'].items() if flavor(c) in ('assert','cover')}
    if any(not n.startswith('$flatten\\checker_inst.') for n in removed):
        raise ValueError('Refusing to remove a production property')
    forced=[n for n,c in m['cells'].items() if flavor(c)=='assume' and n.startswith('$flatten\\checker_inst.')]
    if len(forced)!=1: raise ValueError('Expected exactly one instruction-selection assumption')
    name=forced[0];cell=m['cells'][name]
    if cell['connections']['A']!=m['netnames'][PREFIX+'spec_valid']['bits']:
        raise ValueError('Unexpected removed assumption')
    removed[name]=cell
    for n in removed: del m['cells'][n]
    m['cells']['__jalr_address_assert']=property_cell('assert',signals['holds'])
    # Every surviving original cell is byte-for-byte equal, all original ports
    # and netnames unchanged. Removed objects are inventoried in the receipt.
    for n,c in original['modules'][TOP]['cells'].items():
        if n not in removed and m['cells'].get(n)!=c: raise ValueError('Changed production/environment cell')
    for key in ('ports','netnames','attributes'):
        if m[key]!=original['modules'][TOP][key]: raise ValueError('Changed model interface')
    return result,removed


def check_invariant(out,source,sources,depth,timeout):
    receipt=dict(status='running',scope='independent all-retirement JALR rs1-address lemma and original address partition; no aggregate ISA acceptance',
        depth=depth,timeout_seconds=timeout,assumptions=['original reset == initstate',
        'original alternating-clock initialization sequence'],results={})
    record=out/'result.json';record.write_text(json.dumps(receipt))
    protected=[Path(p) for p in sources]+[ROOT/'dv/core/ReferenceFormal.scala',
        ROOT/'hw/ip/perf_core/formal/JalrAddressProperty.scala',Path(__file__),
        ROOT/'dv/core/riscv_formal.py',ROOT/'dv/core/assertion_partitions.py']
    hashes={str(p):digest(p) for p in protected}
    try:
        raw=out/'original-raw.json';prep=out/'prepare-invariant.ys'
        prep.write_text(source+f'write_json {raw}\n')
        run(['yosys','-Q','-T','-s',prep],out,'prepare-invariant',timeout=120)
        original,renames=stabilize_generated_names(json.loads(raw.read_text()))
        original_path=out/'original.json';original_path.write_text(json.dumps(original))
        run([sys.executable,'tools/sbt.py',
            'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/perf_core/formal")',
            f'hw/runMain deadhorse.perf_core.formal.EmitJalrAddressProperty {out}'],out,'emit-property')
        monitor_path=out/'monitor.json';ys=out/'monitor.ys'
        ys.write_text(f'read_slang --top JalrAddressProperty {out}/JalrAddressProperty.sv\n'
                      f'prep -top JalrAddressProperty -flatten\nwrite_json {monitor_path}\n')
        run(['yosys','-Q','-T','-s',ys],out,'monitor')
        monitor=json.loads(monitor_path.read_text())['modules']['JalrAddressProperty']
        attached,signals=attach(original,monitor);m=attached['modules'][TOP]
        targets=[n for n in assertions(original) if 'rvfi_insn_check.sv:171$assert' in n]
        if len(targets)!=1: raise ValueError('Pinned JALR source-address assertion not unique')
        target=m['cells'][targets[0]]
        if target['type']!='$check' or int(target['parameters']['TRG_ENABLE'],2):
            raise ValueError('Expected original combinational assertion')
        qualified=copy.deepcopy(attached);q=qualified['modules'][TOP]
        sv=q['netnames'][PREFIX+'spec_valid']['bits'];check=q['netnames']['checker_inst.check']['bits']
        upstream=gate(q,'$and',target['connections']['EN'],sv)
        helper=gate(q,'$and',signals['active'],check)
        active_equal=gate(q,'$eq',upstream,helper)
        bad_original=gate(q,'$and',upstream,gate(q,'$not',target['connections']['A']))
        bad_helper=gate(q,'$and',check,gate(q,'$not',signals['holds']))
        violation_equal=gate(q,'$eq',bad_original,bad_helper)
        forced=[c for n,c in q['cells'].items() if flavor(c)=='assume' and n.startswith('$flatten\\checker_inst.')]
        if len(forced)!=1 or forced[0]['type']!='$check' or int(forced[0]['parameters']['TRG_ENABLE'],2):
            raise ValueError('Expected one combinational instruction-selection assumption')
        assume_enable=gate(q,'$and',gate(q,'$not',q['netnames']['checker_inst.reset']['bits']),check)
        assumption_enable_equal=gate(q,'$eq',forced[0]['connections']['EN'],assume_enable)
        qual_path=out/'qualification.json'
        qual_path.write_text(json.dumps(cone(q,dict(active_equal=active_equal,violation_equal=violation_equal,
            assumption_enable_equal=assumption_enable_equal))))
        qual=out/'qualification.ys';qual.write_text(f'read_json {qual_path}\n'
            'check -assert\nsat -verify -prove active_equal 1 -prove violation_equal 1 -prove assumption_enable_equal 1 -show-inputs -show-outputs\n')
        run(['yosys','-Q','-T','-s',qual],out,'qualification')
        receipt['qualification']='PASS exact activation and violation equivalence, free checker inputs'
        model,removed=independent(original,attached,signals)
        receipt.update(original_assertions=assertions(original),removed_only_in_independent_lemma=removed,
            target_assertion=targets[0],generated_name_map=renames)
        # The unchanged original is still the acceptance model. No original
        # assertion is claimed proved by this diagnostic or assumed here.
        model_path=out/'lemma.json';model_path.write_text(json.dumps(model))
        protected.extend([raw,prep,original_path,monitor_path,qual_path,qual,model_path,ys,out/'JalrAddressProperty.sv'])
        if any(digest(Path(p))!=h for p,h in hashes.items()): raise ValueError('Sources changed during preparation')
        hashes.update({str(p):digest(p) for p in protected})
        receipt['input_sha256']=hashes
        record.write_text(json.dumps(receipt,indent=2)+'\n')
        for role in ('prove','cover','fault','original-source-address'):
            directory=output_dir(out/role);job=copy.deepcopy(model);j=job['modules'][TOP]
            mode='prove';engine='abc pdr'
            if role=='original-source-address':
                augmented=copy.deepcopy(attached)
                augmented['modules'][TOP]['cells']['__jalr_address_assert']=property_cell('assert',signals['holds'])
                job=partition(augmented,[targets[0],'__jalr_address_assert'])
                j=job['modules'][TOP]
                receipt['original_partition']={
                    'retained_original_assertion':targets[0],
                    'helper':'__jalr_address_assert (assert, never assume)',
                    'unverified_original_assertions':[n for n in assertions(original) if n!=targets[0]],
                    'semantics':'all original assumptions, clocks, state, covers and selected assertion unchanged'}
            if role=='cover':
                j['cells']['__jalr_address_assert']=property_cell('cover',signals['active'])
                mode='cover';engine='btor btormc'
            if role=='fault':
                # Change the actual reported RVFI bit's driver, not the monitor.
                bit=j['netnames']['checker_inst.rvfi_rs1_addr']['bits'][0]
                drivers=[(n,p,i) for n,c in j['cells'].items() for p,d in c['port_directions'].items()
                         if d=='output' for i,b in enumerate(c['connections'][p]) if b==bit]
                if len(drivers)!=1: raise ValueError('RVFI mutation requires unique real driver')
                n,p,i=drivers[0];fresh=next_bit(j)
                j['cells'][n]['connections'][p][i]=fresh
                j['cells']['__jalr_reported_address_fault']=dict(type='$not',parameters={
                    'A_WIDTH':'1','A_SIGNED':'0','Y_WIDTH':'1'},attributes={},
                    port_directions={'A':'input','Y':'output'},connections={'A':[fresh],'Y':[bit]})
                receipt['fault_driver']=[n,p,i]
                mode='bmc';engine='btor btormc'
            path=directory/'model.json';path.write_text(json.dumps(job))
            config=directory/'check.sby';config.write_text(f'[options]\nmode {mode}\ndepth {depth}\n'
                f'multiclock on\ntimeout {timeout}\n[engines]\n{engine}\n[script]\nread_json {path}\nopt_clean\n')
            hashes.update({str(p):digest(p) for p in (path,config)})
            result=run(['sby','-f','-d',directory/'work',config],directory,'check',allowed=(0,2,8,16),timeout=timeout+30)
            if any(digest(Path(p))!=h for p,h in hashes.items()): raise ValueError('Proof inputs changed during run')
            status=(directory/'work/status').read_text().split()[0]
            receipt['results'][role]=dict(status=status,returncode=result.returncode,seconds=result.elapsed_seconds)
            record.write_text(json.dumps(receipt,indent=2)+'\n')
            expected=('FAIL',2) if role=='fault' else ('PASS',0)
            if (status,result.returncode)!=expected:
                raise RuntimeError(f'JALR address {role}: {status}; no ISA acceptance granted')
            print(f'{role}: {status}',flush=True)
        receipt['status']='pass (lemma and original address partition only)'
        return 0
    except BaseException as exc:
        receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=hashes
        record.write_text(json.dumps(receipt,indent=2)+'\n')

"""Focused original JALR destination/trap lemmas with exact checker qualification."""
import argparse
import copy
import json
from pathlib import Path
import sys
from common import ROOT, local, output_dir, run
from jalr_invariant import TOP, PREFIX, digest, gate, next_bit, property_cell, independent, flavor
from jalr_receipts import verify_hashes
from check_jalr_link import cone
from qualify_owner_valid import inject

BINDINGS=dict(reset='checker_inst.reset',valid='checker_inst.rvfi_valid',instruction='checker_inst.rvfi_insn',
              reportedAddress='checker_inst.rvfi_rd_addr',reportedTrap='checker_inst.rvfi_trap')


def attach(original,monitor):
    design=copy.deepcopy(original);m=design['modules'][TOP];mapping={};fresh=next_bit(m)
    for port,net in BINDINGS.items():
        old=monitor['ports'][port]['bits'];new=m['netnames'][net]['bits']
        if len(old)!=len(new):raise ValueError('Metadata binding width changed')
        mapping.update(zip(old,new))
    bits={b for c in monitor['cells'].values() for bs in c['connections'].values() for b in bs if isinstance(b,int)}
    for bit in sorted(bits-set(mapping)):mapping[bit]=fresh;fresh+=1
    for name,c in monitor['cells'].items():
        c=copy.deepcopy(c);c['connections']={p:[mapping.get(b,b) for b in bs] for p,bs in c['connections'].items()}
        m['cells']['__metadata_'+name]=c
    signals={n:[mapping.get(b,b) for b in p['bits']] for n,p in monitor['ports'].items() if p['direction']=='output'}
    restored=copy.deepcopy(design)
    for n in set(m['cells'])-set(original['modules'][TOP]['cells']):del restored['modules'][TOP]['cells'][n]
    if restored!=original:raise ValueError('Metadata monitor changed production model')
    return design,signals


def qualify(attached,signals,target,out):
    m=copy.deepcopy(attached)['modules'][TOP];check=m['netnames']['checker_inst.check']['bits'];valid=m['netnames'][PREFIX+'spec_valid']['bits']
    upstream=gate(m,'$and',target['connections']['EN'],valid)
    active_equal=gate(m,'$eq',upstream,gate(m,'$and',signals['active'],check))
    bad_original=gate(m,'$and',upstream,gate(m,'$not',target['connections']['A']))
    bad_helper=gate(m,'$and',check,gate(m,'$not',signals['holds']))
    violation_equal=gate(m,'$eq',bad_original,bad_helper)
    forced=[c for n,c in m['cells'].items() if flavor(c)=='assume' and n.startswith('$flatten\\checker_inst.')]
    if len(forced)!=1 or forced[0]['connections']['A']!=valid:raise ValueError('Forced selection assumption changed')
    enable=gate(m,'$and',gate(m,'$not',m['netnames']['checker_inst.reset']['bits']),check)
    enable_equal=gate(m,'$eq',forced[0]['connections']['EN'],enable)
    model=cone(m,dict(active_equal=active_equal,violation_equal=violation_equal,enable_equal=enable_equal))
    results={};files=[]
    for negative in (False,True):
        name='negative' if negative else 'positive';design=copy.deepcopy(model)
        if negative:
            cells=[c for n,c in design['modules'][TOP]['cells'].items() if n.startswith('__metadata_') and c['type']=='$eq' and c['connections'].get('B')==list(reversed(format(0x67,'07b')))]
            if len(cells)!=1:raise ValueError('Unique metadata guard not found')
            cells[0]['connections']['B'][0]='0'
        job=output_dir(out/name);path=job/'model.json';path.write_text(json.dumps(design));ys=job/'check.ys';trace=job/'counterexample.json'
        ys.write_text(f'read_json {path}\ncheck -assert\nsat '+('' if negative else '-verify ')+
            f'-prove active_equal 1 -prove violation_equal 1 -prove enable_equal 1 -show-inputs -show-outputs -dump_json {trace}\n')
        result=run(['yosys','-Q','-T','-s',ys],job,'check',timeout=120)
        expected='SAT proof finished - model found: FAIL!' if negative else 'SAT proof finished - no model found: SUCCESS!'
        if expected not in result.stdout or negative and not trace.exists():raise ValueError('Metadata guard qualification failed')
        results[name]=dict(status='rejected' if negative else 'proved',seconds=result.elapsed_seconds);files.extend((path,ys))
        if negative:files.append(trace)
    return results,files


def witness(text,role):
    family,kind=role.split('-');wanted={'reset':'checker_inst.reset','valid':'rvfi_valid','instruction':'rvfi_insn',
        'reported':'rvfi_rd_addr' if family=='address' else 'rvfi_trap'}
    scope=[];names={};values={};found=[];time=0
    def sample():
        if any(n not in names or names[n] not in values for n in wanted):return
        raw={n:values[names[n]] for n in wanted}
        if any(set(v)-set('01') for v in raw.values()):return
        d={n:int(v,2) for n,v in raw.items()};i=d['instruction']
        if d['reset'] or not d['valid'] or i&127!=0x67 or i>>12&7:return
        expected=(i>>7)&31 if family=='address' else 0
        if kind=='cover' and family=='address' and expected==0:return
        if d['reported']!=(expected^int(kind=='fault')):return
        found.append(dict(time=time,values=d,expected=expected))
    for line in text.splitlines():
        p=line.split()
        if not p:continue
        if p[0]=='$scope':scope.append(p[2])
        elif p[0]=='$upscope':scope.pop()
        elif p[0]=='$var':
            full='.'.join(scope+[p[4]])
            for n,s in wanted.items():
                if full==TOP+'.'+s:names[n]=p[3]
        elif line.startswith('#'):sample();time=int(line[1:])
        elif line[0] in 'bB' and len(p)==2:values[p[1]]=p[0][1:]
        elif line[0] in '01xXzZ':values[line[1:]]=line[0]
    sample()
    if not found:raise ValueError('No exact active metadata witness')
    return found[0]


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--baseline',default='build/t13/jalr-address-strengthened');ap.add_argument('--output',required=True)
    args=ap.parse_args();base=local(args.baseline);out=output_dir(args.output)
    receipt=dict(status='running',scope='JALR destination/trap metadata only; aggregate ISA unresolved',results={});protected={}
    try:
        raw=base/'result.json';prior=json.loads(raw.read_text());protected=dict(prior['input_sha256'])
        for p in (raw,Path(__file__),ROOT/'hw/ip/perf_core/formal/JalrMetadataProperty.scala',ROOT/'dv/core/check_jalr_link.py',ROOT/'dv/core/qualify_owner_valid.py'):
            protected[str(p)]=digest(p)
        verify_hashes(protected);original=json.loads((base/'original.json').read_text())
        if original['modules'][TOP]['netnames'][PREFIX+'spec_trap']['bits']!=['0']:raise ValueError('Frozen checker spec_trap is not constant false')
        receipt.update(timeout_seconds=120,depth=144,assumptions=prior['assumptions'],spec_trap=['0'])
        run([sys.executable,'tools/sbt.py','set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/perf_core/formal")',
             f'hw/runMain deadhorse.perf_core.formal.EmitJalrMetadataProperty {out}'],out,'emit')
        sv=out/'JalrMetadataProperty.sv';mp=out/'monitor.json';ys=out/'monitor.ys'
        ys.write_text(f'read_slang --top JalrMetadataProperty {sv}\nprep -top JalrMetadataProperty -flatten\nwrite_json {mp}\n')
        run(['yosys','-Q','-T','-s',ys],out,'monitor',timeout=120);protected.update({str(p):digest(p) for p in (sv,mp,ys)})
        attached,signals=attach(original,json.loads(mp.read_text())['modules']['JalrMetadataProperty'])
        complete=True
        for family,line in (('address',176),('trap',198)):
            targets=[n for n,c in original['modules'][TOP]['cells'].items() if flavor(c)=='assert' and f'rvfi_insn_check.sv:{line}$assert' in n]
            if len(targets)!=1:raise ValueError('Unique original metadata assertion missing')
            selected={**signals,'holds':signals[family+'Holds']}
            qualification,files=qualify(attached,selected,original['modules'][TOP]['cells'][targets[0]],output_dir(out/(family+'-qualification')))
            protected.update({str(p):digest(p) for p in files});receipt[family+'_qualification']=qualification;receipt[family+'_original']=targets[0]
            model,removed=independent(original,attached,selected);receipt['removed_only_in_independent_lemmas']=removed
            for kind in ('prove','cover','fault'):
                role=family+'-'+kind;design=copy.deepcopy(model);m=design['modules'][TOP];mode='prove';engine='abc pdr'
                if kind=='cover':
                    activation=signals['nonzero'] if family=='address' else signals['active']
                    m['cells']['__jalr_address_assert']=property_cell('cover',gate(m,'$and',activation,selected['holds']));mode='cover';engine='btor btormc'
                if kind=='fault':
                    field='reportedAddress' if family=='address' else 'reportedTrap'
                    receipt[role+'_driver']=inject(m,m['netnames'][BINDINGS[field]]['bits'][0],signals['active']);mode='bmc';engine='btor btormc'
                job=output_dir(out/role);path=job/'model.json';path.write_text(json.dumps(design));config=job/'check.sby'
                config.write_text(f'[options]\nmode {mode}\ndepth 144\nmulticlock on\ntimeout 120\n[engines]\n{engine}\n[script]\nread_json {path}\nopt_clean\n')
                protected.update({str(p):digest(p) for p in (path,config)});verify_hashes(protected)
                result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=150)
                statuspath=job/'work/status';status=statuspath.read_text().split()[0]
                receipt['results'][role]=dict(status=status,returncode=result.returncode,seconds=result.elapsed_seconds);protected[str(statuspath)]=digest(statuspath)
                if (status,result.returncode)!=(('FAIL',2) if kind=='fault' else ('PASS',0)):
                    complete=False
                    if kind=='prove' and status=='TIMEOUT':print(role+': TIMEOUT (preserved)',flush=True);break
                    raise RuntimeError(role+': '+status)
                if kind!='prove':
                    witnesses=[]
                    for trace in (job/'work').glob('engine_*/trace*.vcd'):
                        try:event=witness(trace.read_text(),role)
                        except ValueError:continue
                        witnesses.append(dict(path=str(trace),sha256=digest(trace),event=event));protected[str(trace)]=digest(trace)
                    if not witnesses:raise ValueError('No active metadata witness')
                    receipt['results'][role]['witnesses']=witnesses
                print(role+': '+status,flush=True)
            (out/'result.json').write_text(json.dumps({**receipt,'input_sha256':protected},indent=2)+'\n')
        verify_hashes(protected)
        if not complete:raise RuntimeError('Metadata proof timeout remains unresolved')
        receipt['status']='pass (JALR destination/trap metadata and original predicates; aggregate ISA unresolved)'
    except BaseException as exc:receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected;(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()

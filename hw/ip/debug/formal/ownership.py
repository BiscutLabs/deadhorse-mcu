"""T32 production control-cone proofs; arbitrary boundary inputs, no protocol assumptions.

This proves admission/permission logic, not a new complete Ibex ISA theorem.
The exact production source hierarchy is authenticated against a fresh replay.
Excluded neighbour outputs become unconstrained inputs (overapproximation).
"""
import argparse, copy, hashlib, json, re, subprocess, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from tools.formal import validate_job

SHA=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
S='subsystem.'
L=S+'loader.control.'
PORTS={
 'entry':dict(clock='mainClock',reset_n=S+'_debugMainUp_r_released',epoch=S+'_perfEpoch_r_released',
   normalBoot='bootReleased',mode=S+'performanceDebugMode',entered=S+'entered',owned=S+'performanceDebugGrant',
   debugFetch=S+'performanceDebugFetch',fetch='core.fetch_enable_i'),
 'loader':dict(clock='i1_aonClock',reset_n=S+'loader.reset_n',owned=S+'liteOwned',loaderWrite=S+'retained.writeLoader',
   retainedHalted=S+'retained.halted',inhibit=S+'loader.debugInhibit',frameValid=L+'frame_valid',opcode=L+'frame_bits_bytes_0',
   phase=L+'phase',start=L+'start',metadata=[L+n for n in ('validImage','length','imageEntry','image','expectedCrc','started','locked','count')]),
 'lite':dict(clock=S+'liteHart.core.clk',reset_n=S+'liteHart.core.reset_n',start=S+'liteHart.core.start',
   notStarted=S+'liteHart.core.notStarted',mode=S+'liteHart.core.debugMode',retired=S+'liteHart.core.retired_valid'),
 'perf':dict(clock='core._core_clock_gate_i_clk_o',reset_n='core.rst_ni',normalBoot='bootReleased',mode='core.debug_mode_o',request='core.instr_req_o',retired='core.rvfi_valid')}
TOPS={'entry':'DebugEntryObserver','loader':'DebugLoaderObserver','lite':'DebugLiteEntryObserver','perf':'DebugPerfFirstEntryObserver'}
SCOPES={'entry':{'','subsystem'},'loader':{'','subsystem','subsystem.loader','subsystem.loader.control','subsystem.retained'},
        'lite':{'','subsystem','subsystem.liteHart.core'},'perf':{'','subsystem'}}
COUNTS={'entry':(3,2),'loader':(5,4),'lite':(2,2),'perf':(2,2)}

def attach(base,observer,bindings):
    m=copy.deepcopy(base);used={b for c in m['cells'].values() for bs in c['connections'].values() for b in bs if isinstance(b,int)}
    nxt=max(used)+1;mapping={};audit={}
    assert set(observer['ports'])==set(bindings)
    for port,names in bindings.items():
        names=[names] if isinstance(names,str) else names
        bits=[b for name in names for b in m['netnames'][name]['bits']]
        op=observer['ports'][port];assert op['direction']=='input' and len(op['bits'])==len(bits),(port,names,len(bits))
        audit[port]=dict(names=names,bits=bits)
        for a,b in zip(op['bits'],bits):
            assert a not in mapping or mapping[a]==b;mapping[a]=b
    inputs=set(mapping);driven=set()
    for c in observer['cells'].values():
        assert c['type']!='$assume' and not(c['type']=='$check' and c['parameters']['FLAVOR'] not in ('assert','cover'))
        for pin,bs in c['connections'].items():
            if c['port_directions'][pin]=='output':
                assert not(set(bs)&(inputs|driven));driven.update(bs)
    def remap(bs):
        nonlocal nxt
        out=[]
        for b in bs:
            if isinstance(b,int):
                if b not in mapping:mapping[b]=nxt;nxt+=1
                b=mapping[b]
            out.append(b)
        return out
    for n,c in observer['cells'].items():
        name='observer.'+n;assert name not in m['cells']
        c=copy.deepcopy(c);c['connections']={p:remap(bs) for p,bs in c['connections'].items()};m['cells'][name]=c
    inverse=copy.deepcopy(m);inverse['cells']={n:c for n,c in inverse['cells'].items() if not n.startswith('observer.')}
    assert inverse==base
    return m,audit

def primitive_scopes(design):
    owners={}
    def visit(typ,path):
        for name,c in design[typ]['cells'].items():
            full=(path+'.' if path else '')+name
            if c['type'] in design and not design[c['type']].get('attributes',{}).get('blackbox'):visit(c['type'],full)
            else:owners[full]=(path,typ)
    visit('DeadhorseSoc','');return owners

def cone(m,allowed):
    drivers={}
    for n,c in m['cells'].items():
        for p,bs in c['connections'].items():
            if c['port_directions'][p]=='output':
                for b in bs:
                    if isinstance(b,int):assert b not in drivers,(b,n,drivers.get(b));drivers[b]=n
    keep=set();free=set()
    def cell(n):
        if n in keep:return
        keep.add(n)
        for p,bs in m['cells'][n]['connections'].items():
            if m['cells'][n]['port_directions'][p]=='input':
                for b in bs:
                    if isinstance(b,int):
                        src=drivers.get(b)
                        if src is not None and (src in allowed or src.startswith('observer.')):cell(src)
                        else:free.add(b)
    for n,c in m['cells'].items():
        if n.startswith('observer.') and c['type'] in ('$check','$assert','$cover'):cell(n)
    cells={n:c for n,c in m['cells'].items() if n in keep}
    cold=m['netnames']['coldReset_n']['bits'];assert len(cold)==1 and cold[0] not in drivers
    free.update(cold);ports={('coldReset_n' if b==cold[0] else 'boundary_'+str(b)):dict(direction='input',bits=[b]) for b in sorted(free)}
    used=free|{b for c in cells.values() for bs in c['connections'].values() for b in bs if isinstance(b,int)}
    nets={n:v for n,v in m['netnames'].items() if set(b for b in v['bits'] if isinstance(b,int))<=used}
    # No original retained cell/pin is changed; only omitted neighbour drivers are freed.
    for n,c in cells.items():assert c==m['cells'][n]
    return dict(attributes={},ports=ports,cells=cells,netnames=nets),dict(retained_cells=len(cells),boundary_bits=sorted(free),retained_sha256=hashlib.sha256(json.dumps(cells,sort_keys=True).encode()).hexdigest())

def fault(m,target,replacement):
    """Redirect actual DUT loads, never observer inputs, to the planted value."""
    result=copy.deepcopy(m);old=m['netnames'][target]['bits'];assert len(old)==len(replacement)
    mapping=dict(zip(old,replacement));changed=[]
    for n,c in result['cells'].items():
        if n.startswith('observer.'):continue
        for p,bs in c['connections'].items():
            if c['port_directions'][p]=='input' and any(b in mapping for b in bs):
                changed.append((n,p));c['connections'][p]=[mapping.get(b,b) for b in bs]
    assert changed
    return result,changed

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--replay',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--roles',nargs='+',choices=PORTS,default=list(PORTS));args=ap.parse_args()
    out=(ROOT/args.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    replay=(ROOT/args.replay).resolve();r=json.loads((replay/'result.json').read_text());assert r['status'].startswith('measurements complete')
    for p,h in r['production_source_sha256'].items():assert SHA(ROOT/p)==h,p
    src={str(p.relative_to(ROOT)):SHA(p) for p in [Path(__file__),Path(__file__).with_name('DebugOwnership.scala'),ROOT/'tools/formal.py',ROOT/'tools/sbt.py',ROOT/'build.sbt',ROOT/'tools/env/lock.json']}
    receipt=dict(status='running',source_sha256=src,production_source_sha256=r['production_source_sha256'],replay_sha256=SHA(replay/'result.json'),jobs=[],
      assumptions=['Initial coldReset_n low; all later resets and boundary inputs arbitrary'],timeout_seconds=120,
      scope='Exact production control cones with omitted neighbouring modules replaced by arbitrary inputs. Admission/loader permissions and lite first entry, not full Ibex retirement/whole-SoC proof. Covers are interface reachability; actual pin-level reachability is independently tested.')
    (out/'runner.py').write_bytes(Path(__file__).read_bytes())
    def run(cmd,label,timeout=180):
        start=time.monotonic()
        with (out/(label+'.log')).open('w') as log:
            try:code=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=timeout).returncode
            except subprocess.TimeoutExpired:code=124
        return dict(command=cmd,returncode=code,seconds=time.monotonic()-start)
    try:
        e=run([sys.executable,'tools/sbt.py','set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/debug/formal")',f'hw/runMain deadhorse.debug.EmitDebugOwnership {out}/emit'],'emit',600);receipt['emission']=e;assert not e['returncode'],'emission'
        hier=replay/'map-8/hier.json';assert SHA(hier)==r['artifact_sha256']['map-8/hier.json']
        design=json.loads(hier.read_text());owners=primitive_scopes(design['modules'])
        ys=out/'production.ys';ys.write_text(f'read_json {hier}\nhierarchy -top DeadhorseSoc\nsetattr -mod -unset keep_hierarchy\nsetattr -unset keep_hierarchy\nflatten\nwrite_json {out}/production.json\n')
        row=run(['yosys','-Q','-T','-s',str(ys)],'production');assert not row['returncode'],'production import'
        base=json.loads((out/'production.json').read_text())['modules']['DeadhorseSoc']
        flattened_names={n.replace('$flatten\\','').replace('\\',''):n for n in base['cells']}
        assert len(flattened_names)==len(base['cells']),'Ambiguous flattened cell identity'
        receipt['hierarchy_sha256']=SHA(hier);receipt['roles']={}
        for role in args.roles:
            scoped={n for n,(owner,typ) in owners.items() if owner in SCOPES[role] or typ.startswith('ResetRelease$') or role=='perf' and (owner=='core' or owner.startswith('core.'))}
            assert scoped<=set(flattened_names),sorted(scoped-set(flattened_names))[:3]
            allowed={flattened_names[n] for n in scoped if base['cells'][flattened_names[n]]['type'].startswith('$')}
            variants=['correct','cover']+({'entry':['early_fetch'],'loader':['permission','inhibit'],'lite':['started'],'perf':['retire']}[role])
            for v in variants:
                observer_variant='cover' if v=='cover' else 'correct';top=TOPS[role];files=list((out/'emit'/role/observer_variant).glob('*.sv'))
                script=out/f'{role}-{v}-observer.ys';obs=out/f'{role}-{v}-observer.json'
                script.write_text('read_slang --top '+top+' '+' '.join(map(str,files))+f'\nprep -top {top} -flatten\nwrite_json {obs}\n')
                assert not run(['yosys','-Q','-T','-s',str(script)],f'{role}-{v}-observer')['returncode']
                observed,bindings=attach(base,json.loads(obs.read_text())['modules'][top],PORTS[role])
                mutation=[]
                if v=='early_fetch':
                    # Bypass the DUT fetch mux by changing its input to enabled.
                    bits=observed['netnames']['core.fetch_enable_i']['bits'];drivers=[]
                    for n,c in observed['cells'].items():
                        if not n.startswith('observer.'):
                            for pin,bs in c['connections'].items():
                                if c['port_directions'][pin]=='output' and bs==bits:drivers.append((n,pin))
                    assert len(drivers)==1;name,pin=drivers[0];c=observed['cells'][name];assert c['type']=='$mux'
                    c['connections']['A']=['1','0','1','0'];c['connections']['B']=['1','0','1','0'];mutation=[(name,'A'),(name,'B')]
                elif v=='permission':
                    bits=observed['netnames'][S+'retained.halted']['bits'];raw=observed['netnames'][S+'_liteHart_halted']['bits']
                    found=[n for n,c in observed['cells'].items() if c['type']=='$and' and c['connections'].get('Y')==bits]
                    assert len(found)==1;cell=observed['cells'][found[0]]
                    assert cell['connections']['A']==raw
                    cell['connections']['B']=['1'];mutation=[(found[0],'B')]
                elif v=='inhibit':observed,mutation=fault(observed,L+'frameReset',['0'])
                elif v=='started':
                    bits=observed['netnames'][S+'liteHart.core.notStarted']['bits'];found=[]
                    for n,c in observed['cells'].items():
                        if not n.startswith('observer.') and c['connections'].get('Q')==bits:found.append(n)
                    assert len(found)==1;observed['cells'][found[0]]['connections']['D']=['0'];mutation=[(found[0],'D')]
                    if 'EN' in observed['cells'][found[0]]['connections']:
                        observed['cells'][found[0]]['connections']['EN']=['1'];mutation.append((found[0],'EN'))
                elif v=='retire':
                    bits=observed['netnames']['core.rvfi_valid']['bits']
                    found=[n for n,c in observed['cells'].items() if c['type']=='$buf' and c['connections'].get('Y')==bits]
                    assert len(found)==1;observed['cells'][found[0]]['connections']['A']=['1'];mutation=[(found[0],'A')]
                model,projection=cone(observed,allowed);path=out/f'{role}-{v}.json';path.write_text(json.dumps(dict(modules={'DeadhorseSoc':model})))
                properties=[n for n,c in model['cells'].items() if c['type']=='$check']
                assert len(properties)==COUNTS[role][v=='cover'],(role,v,properties)
                mode='cover' if v=='cover' else 'prove';config=out/f'{role}-{v}.sby'
                # The exact-model perf-cover triage qualified this portfolio;
                # do not repeat its unchanged Z3 timeout on normal replay.
                engine=('smtbmc yices\nbtor btormc' if role=='perf' else 'smtbmc z3') if mode=='cover' else 'abc pdr'
                config.write_text('\n'.join(['[options]',f'mode {mode}','multiclock on','depth 48','timeout 120','[engines]',engine,'[script]',f'read_json {path.name}','prep -top DeadhorseSoc',"fminit -seq coldReset_n 0,'z",'clk2fflogic','chformal -lower','select -assert-count 1 t:$assume','[files]',str(path),'']))
                row=run(['sby','-d',str(out/f'{role}-{v}'),str(config)],f'{role}-{v}');statusfile=out/f'{role}-{v}/status';status=statusfile.read_text().split()[0] if statusfile.exists() else 'ERROR'
                row.update(role=role,variant=v,solver_status=status,model_sha256=SHA(path),bindings=bindings,projection=projection,mutation=mutation,properties=properties)
                receipt['jobs'].append(row)
                if status=='TIMEOUT':row['status']='unresolved'
                else:
                    failed=validate_job(out/f'{role}-{v}','cover' if v=='cover' else 'proof' if v=='correct' else 'negative',row['returncode'],status)
                    if v not in ('correct','cover'):
                        log=(out/f'{role}-{v}/logfile.txt').read_text()
                        failed=sorted(set(re.findall(r'Assert failed in DeadhorseSoc: observer\.(assert__\w+)',log)))
                        expected={'early_fetch':{'assert__chisel3_builtin_1'},'permission':{'assert__chisel3_builtin','assert__chisel3_builtin_0'},
                                  'inhibit':{'assert__chisel3_builtin_1','assert__chisel3_builtin_2','assert__chisel3_builtin_3'},'started':{'assert__chisel3_builtin'},'retire':{'assert__chisel3_builtin_0'}}[v]
                        assert failed and set(failed)<=expected,('Wrong fault identity',v,failed)
                    row['failed_properties']=failed;row['status']='covered' if v=='cover' else 'proved' if v=='correct' else 'fault_rejected'
                print(role,v,row['status'],flush=True)
        for p,h in src.items():assert SHA(ROOT/p)==h,p
        for p,h in r['production_source_sha256'].items():assert SHA(ROOT/p)==h,p
        receipt['status']='unresolved' if any(j['status']=='unresolved' for j in receipt['jobs']) else 'pass'
    except Exception as e:receipt.update(status='failed',error=str(e))
    receipt['artifact_sha256']={str(p.relative_to(out)):SHA(p) for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt['status'],receipt.get('error',''),flush=True)
    return 0 if receipt['status']=='pass' else 1
if __name__=='__main__':sys.exit(main())

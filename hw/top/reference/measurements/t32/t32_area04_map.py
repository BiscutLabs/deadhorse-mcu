"""Use the project's flattened load-aware mapping, retaining all production logic."""
import copy,hashlib,json,subprocess,sys
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root))
from tools.timing.check import output_aliases
from tools.timing.fanout import buffer_module,verify
base=root/'build/t32/area04/mapped';base.mkdir(exist_ok=False)
usb_map=root/'build/plan03/production-measure04/usb-mapping'
old=root/'build/t32/area03'
cfg=json.loads((root/'phys/gf180-ws-1x1/block-timing.json').read_text())
lib=root/f'build/riscay-mcu/.tools/physical/pdk/{cfg["library"]}__{cfg["corner"]}.lib'
assert hashlib.sha256(lib.read_bytes()).hexdigest()==cfg['sha256']
def bind_usb(hierarchy,out):
    original=json.loads(hierarchy.read_text());design=copy.deepcopy(original)
    candidates=[n for n in design['modules'] if n.split('$')[0]=='Usb'];assert len(candidates)==1
    target=candidates[0];before=copy.deepcopy(design['modules'][target])
    usb=json.loads((usb_map/'mapped.json').read_text())['modules']['Usb']
    usb['attributes']=copy.deepcopy(before.get('attributes',{}))
    owner=usb['ports'].pop('owner');assert len(owner['bits'])==3 and owner['direction']=='input'
    replacements=dict(zip(owner['bits'],['1','0','0']))
    for c in usb['cells'].values():
        c['connections']={p:[replacements.get(b,b) for b in bs] for p,bs in c['connections'].items()}
        c.setdefault('attributes',{})['keep']='1'
    for v in [*usb['ports'].values(),*usb['netnames'].values()]:v['bits']=[replacements.get(b,b) for b in v['bits']]
    for name,p in usb['ports'].items():
        usb['netnames'][name]={'hide_name':0,'bits':p['bits'][:],'attributes':{'keep':'1'}}
    assert {n:(p['direction'],len(p['bits'])) for n,p in before['ports'].items()}=={n:(p['direction'],len(p['bits'])) for n,p in usb['ports'].items()}
    instances=[(n,k,c) for n,m in design['modules'].items() for k,c in m.get('cells',{}).items() if c['type']==target]
    assert len(instances)==1
    for _,_,c in instances:
        assert set(c['connections'])==set(usb['ports'])
        assert all(len(c['connections'][p])==len(v['bits']) and c['port_directions'][p]==v['direction'] for p,v in usb['ports'].items())
    design['modules'][target]=usb
    restored=copy.deepcopy(design);restored['modules'][target]=before
    assert restored==original,'USB splice changed another module or connection'
    (out/'bound-hier.json').write_text(json.dumps(design))
    (out/'splice.json').write_text(json.dumps(dict(module=target,instance=instances,owner=1,
      reference_sha256=hashlib.sha256((usb_map/'mapped.json').read_bytes()).hexdigest(),
      hierarchy_sha256=hashlib.sha256(hierarchy.read_bytes()).hexdigest(),
      verification='Exact module restoration recovers original hierarchy; every port connection preserved'),indent=2)+'\n')
    return usb

def verify_island(usb,mod,out):
    # Match every mapped pin through a single bijective bit relabelling.
    bits={};reverse={};matched={}
    def bind(a,b):
        if isinstance(a,str):assert a==b,(a,b);return
        assert isinstance(b,int)
        assert bits.get(a,b)==b and reverse.get(b,a)==a,(a,b)
        bits[a]=b;reverse[b]=a
    for name,c in usb['cells'].items():
        actual='subsystem.usb.'+name;d=mod['cells'][actual]
        assert c['type']==d['type'] and c['parameters']==d['parameters'] and c['port_directions']==d['port_directions'],actual
        for p,bs in c['connections'].items():
            assert len(bs)==len(d['connections'][p])
            for a,b in zip(bs,d['connections'][p]):bind(a,b)
        matched[name]=actual
    for name,p in usb['ports'].items():
        actual=mod['netnames']['subsystem.usb.'+name]['bits'];assert len(actual)==len(p['bits'])
        for a,b in zip(p['bits'],actual):bind(a,b)
    replicas=sum(n.startswith('usb_enable_replica_') for n in usb['cells'])
    result=dict(status='pass',cells=matched,bits=bits,replicas=replicas,
      verification='Every mapped USB cell type/parameter/pin and port retained under one bijective net relabelling, including constant owner binding')
    (out/'island-preservation.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

for mhz in (8,):
    out=base/f'map-{mhz}';out.mkdir()
    cuts=json.loads((old/f'map-{mhz}/macro-sockets.json').read_text())
    def run(lines,name):
        script=out/(name+'.ys');script.write_text('\n'.join(lines)+'\n')
        with (out/(name+'.log')).open('w') as f:
            subprocess.run(['yosys','-Q','-T','-s',str(script)],stdout=f,stderr=subprocess.STDOUT,check=True)
    bound=bind_usb(old/f'map-{mhz}/hier.json',out)
    run([f'read_json {out}/bound-hier.json','blackbox '+' '.join(i['module'] for i in cuts),
         'flatten','opt_expr','opt_clean','check -assert',f'write_json {out}/flat.json'],'flatten')
    original=json.loads((out/'flat.json').read_text());projected=copy.deepcopy(original)
    top=projected['modules']['DeadhorseSoc'];removed={};ports=[]
    for index,item in enumerate(cuts):
        name=item['instance'].removesuffix('.Memory');cell=top['cells'].pop(name)
        assert cell['type']==item['module'];removed[name]=cell
        item['connections']=cell['connections'];item['ports']={}
        for pin,port in item['interface'].items():
            bits=cell['connections'][pin]
            if pin==item['clock_pin']:
                assert bits==top['ports']['i1_aonClock' if item['clock_domain']=='aon' else 'mainClock']['bits'];continue
            name=f'macro_{index}_{pin}'
            assert name not in top['ports']
            top['ports'][name]=dict(direction='input' if port['direction']=='output' else 'output',bits=bits)
            ports.append(name);item['ports'][pin]=name
    restored=copy.deepcopy(projected)
    for p in ports:del restored['modules']['DeadhorseSoc']['ports'][p]
    restored['modules']['DeadhorseSoc']['cells'].update(removed)
    assert original==restored
    # Physical boundary excludes only verification retirement observation ports.
    physical=copy.deepcopy(projected)
    removed_observers={n:p for n,p in physical['modules']['DeadhorseSoc']['ports'].items() if n.startswith('rvfi_')}
    assert removed_observers and all(p['direction']=='output' for p in removed_observers.values())
    for name in removed_observers:del physical['modules']['DeadhorseSoc']['ports'][name]
    undo=copy.deepcopy(physical);undo['modules']['DeadhorseSoc']['ports'].update(removed_observers)
    assert undo==projected,'Observer boundary changed functional logic/ports'
    (out/'observer-boundary.json').write_text(json.dumps(dict(removed_ports=removed_observers,
      verification='Exact restoration recovers full instrumented hierarchy; no input or functional output or cell changed'),indent=2)+'\n')
    projected=physical
    (out/'cut.json').write_text(json.dumps(projected))
    front=[f'read_json {out}/cut.json','hierarchy -top DeadhorseSoc','check -assert',
           'synth -top DeadhorseSoc -flatten -noabc -nofsm',f'dfflibmap -liberty {lib}']
    run(front+[f'write_json {out}/premapped.json'],'premap')
    pre=json.loads((out/'premapped.json').read_text());multiplicity,aliases=output_aliases(pre['modules']['DeadhorseSoc'])
    target=62500
    constraints=out/'mapping.constr';constraints.write_text(f'set_driving_cell {cfg["library"]}__buf_1\nset_load {cfg["output_load_pf"]*1000*multiplicity:g}\n')
    abc=out/'mapping.abc';abc.write_text('strash; &get -n; &fraig -x; &put; scorr; dc2; strash; '+
      f'&get -n; &dch -f; &nf -D {target}; &put; buffer; upsize -D {target}; dnsize -D {target}; stime -p\n')
    run(front+[f'abc -liberty {lib} -constr {constraints} -script {abc}','clean -purge','check -assert',
      'rename -enumerate',f'write_json {out}/unbuffered.json'],'map')
    design=json.loads((out/'unbuffered.json').read_text());mod=design['modules']['DeadhorseSoc']
    assert output_aliases(mod)[0]<=multiplicity
    island=verify_island(bound,mod,out)
    primary={b for p in mod['ports'].values() if p['direction']=='input' for b in p['bits']}
    clocks={b for c in mod['cells'].values() for b in c['connections'].get('CLK',[])}
    resets={b for c in mod['cells'].values() for p,bits in c['connections'].items() if p in ('RN','SETN') for b in bits if isinstance(b,int)}-primary
    assert not resets&clocks
    new,inserted=buffer_module(mod,'mainClock',source_bits=resets,prefix='soc_reset_')
    verify(mod,new,inserted)
    faulty=copy.deepcopy(new);first=inserted[0];faulty['cells'][first]['connections']['I']=faulty['cells'][first]['connections']['Z'][:]
    try:verify(mod,faulty,inserted)
    except ValueError as e:assert 'cycle' in str(e)
    else:raise AssertionError('Buffer cycle fault escaped')
    # Restore global replica identities for the unchanged certificate helper.
    aliases={}
    for name in list(new['cells']):
        if name.startswith('subsystem.usb.usb_enable_replica_'):
            short=name.removeprefix('subsystem.usb.');assert short not in new['cells']
            cell=new['cells'].pop(name);aliases[name]=short
            cell['attributes']['usb_enable_original']='subsystem.usb.'+cell['attributes']['usb_enable_original']
            new['cells'][short]=cell
    from tools.timing.usb_enable_fanout import identities
    assert len(identities(new))==island['replicas'] and island['replicas']>0
    (out/'replica-renames.json').write_text(json.dumps(aliases,indent=2)+'\n')
    design['modules']['DeadhorseSoc']=new
    (out/'mapped.json').write_text(json.dumps(design))
    run([f'read_json {out}/mapped.json','check -assert','scc -expect 0',
         f'tee -o {out}/area.txt stat -liberty {lib}',f'write_json {out}/canonical.json',f'write_verilog -noattr -noexpr {out}/mapped.v',f'write_verilog -noattr -noexpr {out}/canonical.v'],'export')
    (out/'macro-sockets.json').write_text(json.dumps(cuts,indent=2)+'\n')
    (out/'mapping.json').write_text(json.dumps(dict(target_ps=target,output_alias_multiplier=multiplicity,
      load_ff=cfg['output_load_pf']*1000*multiplicity,reset_buffers=len(inserted),retiming=False,
      fsm_recoding=False,buffer_cycle_fault='rejected',projection='exact restoration',
      scope='Complete production logic; six SRAM/ROM model interfaces exposed, macro timing excluded'),indent=2)+'\n')
    print(mhz,'mapped load-aware flattened production logic',len(inserted),'reset buffers',flush=True)

"""All-state production-context binding; no state or output exclusions."""
import copy,hashlib,json,subprocess
from pathlib import Path
root=Path.cwd();base=root/'build/plan03/production-measure03'
reference=root/'build/plan03/fast02/fast/usb/emit/usb'
for mhz in (8,9):
    out=base/f'context02-{mhz}';out.mkdir(exist_ok=False)
    actual=root/f'build/plan03/production-measure01/emit-{mhz}'
    inventories={'reference':sorted(reference.glob('*.sv'))+sorted(reference.glob('*.v')),
      'production':[actual/s.strip() for s in (actual/'filelist.f').read_text().splitlines() if s.strip()]}
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for ps in inventories.values() for p in ps}
    def run(name,commands,negative=False):
        script=out/(name+'.ys');script.write_text('\n'.join(commands)+'\n')
        r=subprocess.run(['yosys','-Q','-T','-s',str(script)],capture_output=True,text=True,timeout=120)
        log=r.stdout+r.stderr;(out/(name+'.log')).write_text(log)
        assert (r.returncode==1 and 'proof did fail' in log) if negative else r.returncode==0,log[-1000:]
        return log
    modules={};regs={}
    for label,files in inventories.items():
        run(label,['read_slang -DSYNTHESIS --top Usb '+' '.join(map(str,files)),
            'prep -top Usb -flatten','memory_map','opt_clean -purge',f'write_json {out}/{label}.json'])
        m=json.loads((out/(label+'.json')).read_text())['modules']['Usb'];modules[label]=m
        regs[label]={}
        for name,c in m['cells'].items():
            if c['type'] in ('$adff','$aldff','$dff'):
                aliases={n for n,v in m['netnames'].items() if v['bits']==c['connections']['Q']}
                assert aliases
                regs[label][name]=(c,aliases)
            else:assert not any(k in c['type'] for k in ('dff','latch','mem')),c['type']
    # The production emitter folds the actual owner=performance(1) binding.
    # Compare that exact constant-connected instance, not an assumed stimulus.
    assert 'owner' not in modules['production']['ports']
    ref=modules['reference'];owner=ref['ports'].pop('owner')
    assert owner['direction']=='input' and len(owner['bits'])==3
    replacements=dict(zip(owner['bits'],['1','0','0']))
    for c in ref['cells'].values():
        c['connections']={p:[replacements.get(b,b) for b in bs] for p,bs in c['connections'].items()}
    for item in [*ref['ports'].values(),*ref['netnames'].values()]:item['bits']=[replacements.get(b,b) for b in item['bits']]
    shapes=[{n:(p['direction'],len(p['bits'])) for n,p in modules[k]['ports'].items()} for k in ('reference','production')]
    assert shapes[0]==shapes[1],('port shape changed',shapes)
    pairs=[];remaining=set(regs['production'])
    for n,(c,aliases) in regs['reference'].items():
        matches=[k for k in remaining if aliases&regs['production'][k][1]]
        assert len(matches)==1,(n,matches)
        k=matches[0];remaining.remove(k);other=regs['production'][k][0]
        assert (c['type'],c['parameters'])==(other['type'],other['parameters'])
        pairs.append((n,k,sorted(aliases&regs['production'][k][1])))
    assert not remaining
    def cut(original,side):
        m=copy.deepcopy(original)
        for i,pair in enumerate(pairs):
            c=m['cells'].pop(pair[side]);m['ports']['state_'+str(i)]=dict(direction='input',bits=c['connections']['Q'])
            for pin,bits in c['connections'].items():
                if pin!='Q':m['ports'][f'next_{i}_{pin}']=dict(direction='output',bits=bits)
        return m
    for side,label in enumerate(('reference','production')):
        (out/(label+'-cut.json')).write_text(json.dumps({'modules':{label:cut(modules[label],side)}}))
    commands=[f'read_json {out}/reference-cut.json',f'read_json {out}/production-cut.json',
        'miter -equiv -flatten reference production ContextMiter','hierarchy -check -top ContextMiter',
        'check -assert','techmap','opt','sat -set-def-inputs -prove trigger 0 -verify']
    assert 'SUCCESS!' in run('equivalence',commands)
    chosen=[p for p in pairs if 'engine.control.nextCursor' in p[2]];assert len(chosen)==1
    bad=copy.deepcopy(modules['production']);c=bad['cells'][chosen[0][1]];c['connections']['D']=['0']*len(c['connections']['D'])
    (out/'fault-cut.json').write_text(json.dumps({'modules':{'production':cut(bad,1)}}))
    run('wrong-next-cursor',[s.replace('production-cut.json','fault-cut.json') for s in commands],True)
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    (out/'result.json').write_text(json.dumps(dict(status='pass',state_bindings=pairs,assumptions=[],excluded_state=[],excluded_outputs=[],
      source_sha256=hashes,proof='Every state next-value/clock/reset function and public output equal for arbitrary shared current state and inputs',
      reference_binding={'owner':1},jobs={'equivalence':'proved','wrong-next-cursor':'fault_rejected'}),indent=2)+'\n')
    print(mhz,'PASS complete production USB context',len(pairs),'state bindings',flush=True)

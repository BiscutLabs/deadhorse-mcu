"""Apply existing source/mapped USB proofs to an identity view of the complete SoC."""
import copy,json,sys
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root))
from hw.ip.usb.formal.enable_certificate import certify
base=root/'build/plan03/production-measure06'
context_base=root/'build/plan03/production-measure03'
proof=root/'build/plan03/fast02/fast/usb'
lib=root/'build/riscay-mcu/.tools/physical/pdk/gf180mcu_fd_sc_mcu7t5v0__ss_125C_3v00.lib'
for mhz in ([int(sys.argv[1])] if len(sys.argv)>1 else (8,9)):
    out=base/f'certificate09-{mhz}';out.mkdir(exist_ok=False)
    assert (base/f'map-{mhz}/mapped.v').read_bytes()==(base/f'map-{mhz}/canonical.v').read_bytes()
    original=json.loads((base/f'map-{mhz}/canonical.json').read_text())['modules']['DeadhorseSoc']
    view=copy.deepcopy(original)
    bound=json.loads((base/f'map-{mhz}/bound-hier.json').read_text())['modules']
    island=bound[next(n for n in bound if n.split('$')[0]=='Usb')]
    translation={};reverse_bits={}
    def bind(a,b):
        if isinstance(a,str):assert a==b;return
        assert isinstance(b,int) and translation.get(a,b)==b and reverse_bits.get(b,a)==a
        translation[a]=b;reverse_bits[b]=a
    def instance(name):
        return name if name.startswith('usb_enable_replica_') else 'subsystem.usb.'+name
    for name,c in island['cells'].items():
        final=original['cells'][instance(name)]
        assert (c['type'],c['parameters'],c['port_directions'])==(final['type'],final['parameters'],final['port_directions'])
        for p,d in c['port_directions'].items():
            if d=='output':
                assert len(c['connections'][p])==len(final['connections'][p])
                for a,b in zip(c['connections'][p],final['connections'][p]):bind(a,b)
    for name,p in island['ports'].items():
        final=original['netnames']['subsystem.usb.'+name]['bits'];assert len(final)==len(p['bits'])
        for a,b in zip(p['bits'],final):bind(a,b)
    parents={}
    for name,c in original['cells'].items():
        if name.startswith('soc_reset_'):
            assert c['type']=='gf180mcu_fd_sc_mcu7t5v0__buf_4'
            parents[c['connections']['Z'][0]]=c['connections']['I'][0]
    def resolve(b):
        seen=set()
        while b in parents:
            assert b not in seen;seen.add(b);b=parents[b]
        return b
    translate=lambda b: translation[b] if isinstance(b,int) else b
    for name,c in island['cells'].items():
        final=original['cells'][instance(name)]
        for p,bs in c['connections'].items():
            actual=final['connections'][p];assert len(bs)==len(actual)
            assert [translate(b) for b in bs]==[resolve(b) if c['port_directions'][p]=='input' else b for b in actual],(name,p)
    added_aliases=[];unused_aliases={}
    used={b for c in island['cells'].values() for bs in c['connections'].values() for b in bs}
    used.update(b for p in island['ports'].values() for b in p['bits'])
    for name,v in island['netnames'].items():
        missing={b for b in v['bits'] if isinstance(b,int) and b not in translation}
        if missing:
            assert not missing & used,'Missing live USB bit identity'
            unused_aliases[name]=sorted(missing);continue
        target='subsystem.usb.'+name;entry=copy.deepcopy(v)
        entry['bits']=[translate(b) for b in v['bits']]
        if target in view['netnames']:assert view['netnames'][target]['bits']==entry['bits']
        else:view['netnames'][target]=entry;added_aliases.append(target)
    (out/'alias-binding.json').write_text(json.dumps(dict(status='pass',translation=translation,added=added_aliases,unrestored_partially_dead_aliases=unused_aliases,
        verification='Every original USB output/port and every input resolved only through recorded positive reset buffers; no type, parameter or connection changed'),indent=2)+'\n')
    view['ports']['usbClock']=view['ports'].pop('i1_usbClock')
    renames={n:n.removeprefix('subsystem.usb.') for n in view['netnames'] if n.startswith('subsystem.usb.')}
    # JSON import generated these private labels for newly inserted buffers.
    # A second import allocates from the same global counter; use private,
    # collision-free labels (still '$'-hidden from certificate alias matching).
    renames.update({n:'$soc_proof_private_'+str(i) for i,n in enumerate(view['netnames']) if n.startswith('$auto$jsonparse.')})
    collisions=set(renames.values()) & (set(view['netnames'])-set(renames))
    renames.update({n:'$soc_unrelated_alias_'+str(i) for i,n in enumerate(sorted(collisions))})
    assert len(set(renames.values()))==len(renames)
    assert not set(renames.values()) & (set(view['netnames'])-set(renames))
    view['netnames']={renames.get(n,n):v for n,v in view['netnames'].items()}
    restored=copy.deepcopy(view);restored['ports']['i1_usbClock']=restored['ports'].pop('usbClock')
    reverse={v:k for k,v in renames.items()}
    restored['netnames']={reverse.get(n,n):v for n,v in restored['netnames'].items()}
    for name in added_aliases:del restored['netnames'][name]
    assert restored==original,'Identity view changed production graph'
    # The existing certificate cuts every sequential Q to an independent input.
    # It does not recognize an ICG as a data flip-flop. Free only those clock
    # outputs as well: an over-approximation, never an assumed gate value.
    gates={n:c for n,c in view['cells'].items() if c['type']=='gf180mcu_fd_sc_mcu7t5v0__icgtp_1'}
    for n,c in gates.items():
        assert c['connections']['Q']!=view['ports']['usbClock']['bits']
        del view['cells'][n]
        view['ports']['proof_free_clock_'+n]=dict(direction='input',bits=c['connections']['Q'])
    (out/'projection.json').write_text(json.dumps(dict(identity_view='exact graph restored before clock cut',
        free_clock_outputs=gates,scope='Local value invariants over every value of unrelated gate outputs; no assumptions'),indent=2)+'\n')
    mapped=out/'identity-view.json';mapped.write_text(json.dumps({'modules':{'Usb':view}}))
    context=json.loads((context_base/f'context02-{mhz}/result.json').read_text())
    assert context['status']=='pass' and context['jobs']=={'equivalence':'proved','wrong-next-cursor':'fault_rejected'}
    assert context['assumptions']==[] and context['excluded_state']==[] and context['excluded_outputs']==[]
    import hashlib
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in context['source_sha256'].items())
    emit=proof/'emit/usb'
    sources=sorted(emit.glob('*.sv'))+sorted(emit.glob('*.v'))
    assert all(str(p) in context['source_sha256'] for p in sources)
    r=certify('Usb',sources,mapped,lib,out/'proof',json.loads((proof/'formal/result.json').read_text()),
              json.loads((proof/'preenable-equivalence/result.json').read_text()))
    selected=set(r['certified'])|set(r['pre_enable']['capture_pins'])|set(r['cadence_binding']['mapped_registers'])
    assert all(original['cells'][n]['connections']['CLK']==original['ports']['i1_usbClock']['bits'] for n in selected)
    (out/'composition.json').write_text(json.dumps(dict(status='pass',context_receipt=str(context_base/f'context02-{mhz}/result.json'),
      context_sha256=hashlib.sha256((context_base/f'context02-{mhz}/result.json').read_bytes()).hexdigest(),
      mapped_sha256=hashlib.sha256((base/f'map-{mhz}/canonical.json').read_bytes()).hexdigest(),
      certificate_sha256=hashlib.sha256((out/'proof/result.json').read_bytes()).hexdigest(),
      all_selected_clocks='actual i1_usbClock',assumptions=[]),indent=2)+'\n')
    print(mhz,r['status'],len(r['certified']),flush=True)

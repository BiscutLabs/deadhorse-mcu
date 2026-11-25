"""PLAN04 production digital mapping, with audited SRAM/ROM and analog sockets.

The macro sockets are exclusions, never macro timing/area signoff. The USB island
retains its authenticated mapped cells. No behavioral model replaces digital RTL.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(Path(__file__).parent/'t32'))
from tools.timing.check import output_aliases
from tools.timing.fanout import verify,buffer_module
from t32_layered_reset import layered
from plan04_usb_binding import bind_source
from plan05_usb_boundary import isolate,audit as audit_boundary
from t33_analog_socket import threshold_driver
from t36_rom_identity import authenticate as authenticate_rom

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main(base,usb_ref,target_ps=62500,stability_reference=None,threshold_control=False,sram=False,rom_image=None):
    if not isinstance(target_ps,int) or not 0<target_ps<=62500:raise ValueError('Invalid optimization target')
    base=(ROOT/base).resolve();base.relative_to(ROOT/'build')
    ref=(ROOT/usb_ref).resolve();ref.relative_to(ROOT/'build')
    emit=base/'emit';out=base/'map';out.mkdir(exist_ok=False)
    rom_image=(ROOT/rom_image).resolve() if rom_image else None
    if rom_image:
        assert sram, 'ROM implementation requires production hard SRAM'
        rom_image.relative_to(ROOT/'build')
    cfg=json.loads((ROOT/'phys/gf180-ws-1x1/block-timing.json').read_text())
    lib=ROOT/cfg['liberty']
    assert digest(lib)==cfg['sha256']
    sram_lib=None;sram_libs=[];macro_widths={}
    if sram:
        lock=ROOT/'hw/vendor/gf180_sram/gf180_sram.lock.json'
        macro_lock=json.loads(lock.read_text());macro=macro_lock['macro']
        macro_widths={macro:10,macro_lock['retained_macro']:9}
        for cell in macro_widths:
            relative=f'cells/{cell}/{cell}__{cfg["corner"]}.lib'
            view=ROOT/'build/vendor/gf180_sram'/relative
            assert digest(view)==macro_lock['files'][relative]
            sram_libs.append(view)
        sram_lib=sram_libs[0]
    files=[emit/line.strip() for line in (emit/'filelist.f').read_text().splitlines() if line.strip()]
    reference_certificate=json.loads((ref/'certificate/result.json').read_text())
    pdk_rebind=None
    if reference_certificate['library_sha256']!=digest(lib):
        from tools.timing.pdk_rebind import reference_library
        pdk_rebind=reference_library(ref,lib)
    counter_ref=(ROOT/stability_reference).resolve() if stability_reference else None
    if counter_ref:counter_ref.relative_to(ROOT/'build')
    certified_sources=[ROOT/n.removeprefix('/work/') for field in ('sources','proof_source_sha256')
        for n in reference_certificate[field]]
    dependencies=files+certified_sources+[Path(__file__),Path(__file__).with_name('plan04_usb_binding.py'),
        Path(__file__).with_name('t33_analog_socket.py'),Path(__file__).with_name('plan05_usb_boundary.py'),
        ROOT/'dv/core/state_equiv.py',Path(__file__).parent/'t32/t32_layered_reset.py',
        Path(__file__).parent/'t32/t32_packed_reset.py',ROOT/'tools/timing/fanout.py',
        ROOT/'tools/timing/check.py',ROOT/'phys/gf180-ws-1x1/block-timing.json',
        ref/'certificate/result.json',ref/'mapped.json',lib]
    dependencies += [Path(__file__).with_name('t36_rom_identity.py')]
    if pdk_rebind:dependencies += [ROOT/n for n in pdk_rebind['input_sha256']]
    if rom_image:dependencies += [rom_image]
    if sram:dependencies += sram_libs+[lock]
    if counter_ref:
        counter_receipt=json.loads((counter_ref/'result.json').read_text())
        assert counter_receipt['status']=='pass' and counter_receipt['top']=='OscStability'
        assert counter_receipt['assumptions']['sha256']==digest(lib)
        assert counter_receipt['mapped_sha256']==digest(counter_ref/'mapped.json')
        assert counter_receipt['mapped_verilog_sha256']==digest(counter_ref/'mapped.v')
        dependencies += [counter_ref/'result.json',counter_ref/'mapped.json',counter_ref/'mapped.v']
        dependencies += [ROOT/n for n in counter_receipt['source_sha256']]
    def sealed():return {p.relative_to(ROOT).as_posix():digest(p) for p in dependencies}
    start_hashes=sealed()
    receipt=dict(status='running',commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        emitted_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in files},liberty_sha256=digest(lib),
        scope='Mapped digital logic, pre-layout; six memory sockets and two uncharacterized analog macros excluded')
    if pdk_rebind:receipt['usb_library_rebind']=pdk_rebind
    if sram:
        receipt.update(scope='Mapped digital logic and twenty hard SRAM macros; ROM and two analog interfaces remain sockets.',
                       sram_liberty=sram_lib.relative_to(ROOT).as_posix(),sram_liberty_sha256=digest(sram_lib),
                       sram_liberties={p.relative_to(ROOT).as_posix():digest(p) for p in sram_libs})
    (out/'result.json').write_text(json.dumps(receipt,indent=2))
    def run(lines,name):
        script=out/(name+'.ys');script.write_text('\n'.join(lines)+'\n')
        with (out/(name+'.log')).open('w') as log:
            subprocess.run(['yosys','-Q','-T','-s',str(script)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
    # Port-only Yosys blackbox views. Their pins are audited again against the
    # emitted instance; no handwritten HDL and no analog timing claim.
    definitions={
        'LfRcMacro':{'vdd':('inout',1),'vss':('inout',1),'enable':('input',1),'trim':('input',6),'test':('input',1),'clock':('output',1),'ready':('output',1)},
        'PorBrownoutMacro':{'vdd':('inout',1),'vss':('inout',1),'threshold':('input',2),'test':('input',1),
            'supplyReset_n':('output',1),'powerOn_n':('output',1),'brownout':('output',1)}}
    analog={'modules':{}}
    for name,ports in definitions.items():
        module=dict(attributes={'blackbox':'1'},ports={},cells={},netnames={});bit=2
        for pin,(direction,width) in ports.items():
            bits=list(range(bit,bit+width));bit+=width
            module['ports'][pin]=dict(direction=direction,bits=bits)
            module['netnames'][pin]=dict(hide_name=0,bits=bits,attributes={})
        analog['modules'][name]=module
    (out/'analog-interfaces.json').write_text(json.dumps(analog))
    run([f'read_liberty -lib {lib}']+[f'read_liberty -lib {p}' for p in sram_libs]+[f'read_json {out}/analog-interfaces.json',
        'read_slang --keep-hierarchy -DSYNTHESIS '+('-DENABLE_INITIAL_MEM_ ' if rom_image else '')+'--top DeadhorseSoc '+' '.join(map(str,files)),
        'hierarchy -check -top DeadhorseSoc','proc','chformal -remove','memory_collect',
        f'write_json {out}/hier.json'],'import')
    design=json.loads((out/'hier.json').read_text());inventory=[]
    def walk(module,path):
        for name,c in design['modules'][module]['cells'].items():
            instance=path+'.'+name if path else name
            if c['type']=='$mem_v2':
                inventory.append(dict(instance=instance,module=module,name=name,
                    parameters={k:int(v,2) for k,v in c['parameters'].items() if k in
                        ('WIDTH','SIZE','ABITS','RD_PORTS','WR_PORTS','RD_CLK_ENABLE','WR_CLK_ENABLE')}))
            elif c['type'] in design['modules'] and not design['modules'][c['type']].get('attributes',{}).get('blackbox'):
                walk(c['type'],instance)
    walk('DeadhorseSoc','')
    (out/'memory-inventory.json').write_text(json.dumps(inventory,indent=2))
    cuts=[i for i in inventory if i['parameters']['SIZE']>=512]
    expected={f'digital.memory.outputs_memory{s}_ext.Memory':(1024,32,4,10) for s in ('','_1','_2','_3')}
    expected.update({'digital.memory.rom_ext.Memory':(16384,32,0,14),
        'digital.subsystem.retained.memory_ext.Memory':(512,32,4,9)})
    if sram:
        expected={'digital.memory.rom_ext.Memory':(16384,32,0,14)}
    assert {i['instance']:tuple(i['parameters'][k] for k in ('SIZE','WIDTH','WR_PORTS','ABITS')) for i in cuts}==expected
    for item in cuts:
        mod=design['modules'][item['module']]
        clock='R0_clk' if item['parameters']['WR_PORTS']==0 else 'RW0_clk'
        edges={};sequential=[]
        for n,c in mod['cells'].items():
            p=c['connections']
            if c['type'] in ('$dff','$dffe'):
                assert p['CLK']==mod['ports'][clock]['bits'] and int(c['parameters']['CLK_POLARITY'],2)==1
                sequential.append(n);continue
            if c['type']=='$mem_v2':
                assert int(c['parameters']['RD_CLK_ENABLE'],2)==0
                if item['parameters']['WR_PORTS']:
                    assert set(p['WR_CLK'])==set(mod['ports'][clock]['bits']) and int(c['parameters']['WR_CLK_ENABLE'],2)==15
                inputs=p['RD_ADDR']+p['RD_EN'];outputs=p['RD_DATA']
            else:
                assert c['type'].startswith('$')
                inputs=[b for k,v in p.items() if c['port_directions'][k]=='input' for b in v]
                outputs=[b for k,v in p.items() if c['port_directions'][k]=='output' for b in v]
            for b in outputs:edges.setdefault(b,set()).update(inputs)
        assert sequential
        inputs={b for p in mod['ports'].values() if p['direction']=='input' for b in p['bits']}
        todo=[b for p in mod['ports'].values() if p['direction']=='output' for b in p['bits']];seen=set()
        while todo:
            b=todo.pop()
            if not isinstance(b,int) or b in seen:continue
            assert b not in inputs,('Asynchronous macro read',item,b)
            seen.add(b);todo.extend(edges.get(b,()))
        item.update(clock_pin=clock,interface=mod['ports'],registered_read=True,
            clock_domain='aon' if item['instance'].startswith('digital.subsystem.retained.') else 'main')
    if rom_image:
        assert len(cuts)==1
        rom_module=cuts[0]['module']
        receipt['implemented_rom']=authenticate_rom(design,cuts[0],rom_image,files)
        receipt['implemented_rom']['module']=rom_module
        # Rejection controls exercise the same identity validator, not a second oracle.
        wrong=copy.deepcopy(design)
        params=wrong['modules'][cuts[0]['module']]['cells'][cuts[0]['name']]['parameters']
        init=params['INIT']
        rejected=[]
        for label,value in [('wrong-word',('1' if init[0]=='0' else '0')+init[1:]),
                            ('missing-initialization','x'*len(init))]:
            params['INIT']=value
            try:authenticate_rom(wrong,cuts[0],rom_image,files)
            except ValueError as error:
                assert 'ROM INIT' in str(error);rejected.append(label)
            else:raise AssertionError('ROM identity fault escaped: '+label)
        receipt['implemented_rom']['negative_controls_rejected']=rejected
        receipt['scope']='Mapped production digital logic including initialized performance ROM and twenty hard SRAM macros; only two analog interfaces remain sockets.'
        cuts=[]
    # Authenticate unchanged producer proof sources and the mapped island.
    cert=json.loads((ref/'certificate/result.json').read_text())
    assert cert['status']=='pass' and digest(ref/'mapped.json')==cert['mapped_sha256']
    assert cert['library_sha256']==digest(lib) or (pdk_rebind and
        pdk_rebind['original_library_sha256']==cert['library_sha256'] and
        pdk_rebind['selected_library_sha256']==digest(lib))
    for name,value in cert['proof_source_sha256'].items():
        p=ROOT/name.removeprefix('/work/');assert digest(p)==value,('Changed USB proof source',name)
    original=copy.deepcopy(design)
    targets=[n for n in design['modules'] if n.split('$')[0]=='Usb'];assert len(targets)==1
    target=targets[0];before=copy.deepcopy(design['modules'][target])
    source_binding=bind_source(out/'hier.json',target,cert,out/'usb-source-binding')
    usb=copy.deepcopy(json.loads((ref/'mapped.json').read_text())['modules']['Usb'])
    usb['attributes']=copy.deepcopy(before.get('attributes',{}))
    owner=usb['ports'].pop('owner');assert owner['direction']=='input' and len(owner['bits'])==3
    replacements=dict(zip(owner['bits'],['1','0','0']))
    for c in usb['cells'].values():
        c['connections']={p:[replacements.get(b,b) for b in bits] for p,bits in c['connections'].items()}
        c.setdefault('attributes',{})['keep']='1'
    for v in [*usb['ports'].values(),*usb['netnames'].values()]:v['bits']=[replacements.get(b,b) for b in v['bits']]
    for name,p in usb['ports'].items():usb['netnames'][name]=dict(hide_name=0,bits=p['bits'][:],attributes={'keep':'1'})
    assert {n:(p['direction'],len(p['bits'])) for n,p in before['ports'].items()}=={n:(p['direction'],len(p['bits'])) for n,p in usb['ports'].items()}
    instances=[c for m in design['modules'].values() for c in m.get('cells',{}).values() if c['type']==target]
    assert len(instances)==1
    for p,v in usb['ports'].items():assert len(instances[0]['connections'][p])==len(v['bits']) and instances[0]['port_directions'][p]==v['direction']
    design['modules'][target]=usb
    restore=copy.deepcopy(design);restore['modules'][target]=before;assert restore==original
    counter=None
    if counter_ref:
        counter_targets=[n for n in design['modules'] if n.split('$')[0]=='OscStability'];assert len(counter_targets)==1
        counter_target=counter_targets[0]
        counter_prefix=counter_target.split('$',1)[1].removeprefix('DeadhorseSoc.')+'.'
        assert counter_prefix in ('clocks.counter.','clocks.executor.counter.')
        counter_binding=bind_source(out/'hier.json',counter_target,{'sources':counter_receipt['source_sha256']},
            out/'counter-source-binding',reference_top='OscStability',fault_pin='stable',unused_inputs=('oscillatorOn',))
        run([f'read_json {counter_ref}/mapped.json','rename -enumerate',
            f'write_json {out}/counter-reference.json'],'counter-canonical')
        counter=copy.deepcopy(json.loads((out/'counter-reference.json').read_text())['modules']['OscStability'])
        old_counter=copy.deepcopy(design['modules'][counter_target]);counter_original=copy.deepcopy(design)
        if 'oscillatorOn' not in old_counter['ports']:
            # The qualified counter's mode uses clear, so firtool omits this
            # unused legacy input at the integrated instance. Fail if it has
            # acquired any logic or output dependency in the mapped reference.
            from hw.top.reference.measurements.plan04_usb_binding import drop_unused_input
            drop_unused_input(counter,'oscillatorOn')
        counter['attributes']=copy.deepcopy(old_counter.get('attributes',{}))
        assert {n:(p['direction'],len(p['bits'])) for n,p in counter['ports'].items()}=={n:(p['direction'],len(p['bits'])) for n,p in old_counter['ports'].items()}
        for c in counter['cells'].values():c.setdefault('attributes',{})['keep']='1'
        for n,p in counter['ports'].items():counter['netnames'][n]=dict(hide_name=0,bits=p['bits'][:],attributes={'keep':'1'})
        design['modules'][counter_target]=counter
        undo=copy.deepcopy(design);undo['modules'][counter_target]=old_counter;assert undo==counter_original
    (out/'bound-hier.json').write_text(json.dumps(design))
    run([f'read_json {out}/bound-hier.json']+(['blackbox '+' '.join(i['module'] for i in cuts)] if cuts else [])+[
        'flatten','opt_expr','opt_merge','opt_clean','check -assert',f'write_json {out}/flat.json'],'flatten')
    original=json.loads((out/'flat.json').read_text());projected=copy.deepcopy(original)
    top=projected['modules']['DeadhorseSoc'];removed={};ports=[]
    if sram:
        physical={n:c for n,c in top['cells'].items() if c['type'] in macro_widths}
        assert len(physical)==20 and sum(n.startswith('digital.memory.') for n in physical)==16
        assert sum(n.startswith('digital.subsystem.retained.') for n in physical)==4
        assert all(c['type']==macro for n,c in physical.items() if n.startswith('digital.memory.'))
        assert all(c['type']==macro_lock['retained_macro'] for n,c in physical.items() if n.startswith('digital.subsystem.retained.'))
        for c in physical.values():
            assert {p:len(b) for p,b in c['connections'].items()}==dict(CLK=1,CEN=1,GWEN=1,WEN=8,A=macro_widths[c['type']],D=8,Q=8)
        (out/'sram-instances.json').write_text(json.dumps(physical,indent=2)+'\n')
    for index,item in enumerate(cuts):
        name=item['instance'].removesuffix('.Memory');cell=top['cells'].pop(name)
        assert cell['type']==item['module'];removed[name]=cell
        item['connections']=cell['connections'];item['ports']={}
        for pin,port in item['interface'].items():
            bits=cell['connections'][pin]
            if pin==item['clock_pin']:
                item['clock_bits']=bits;continue
            name=f'macro_{index}_{pin}';assert name not in top['ports']
            top['ports'][name]=dict(direction='input' if port['direction']=='output' else 'output',bits=bits)
            ports.append(name);item['ports'][pin]=name
    analog_cuts=[]
    for name,c in list(top['cells'].items()):
        if c['type'] not in definitions:continue
        missing=set(definitions[c['type']])-set(c['connections'])
        assert set(c['connections'])<=set(definitions[c['type']])
        assert all(definitions[c['type']][p][0]=='output' for p in missing)
        removed[name]=top['cells'].pop(name)
        row=dict(instance=name,module=c['type'],connections=c['connections'],ports={},unused_outputs=sorted(missing))
        for pin,(direction,width) in definitions[c['type']].items():
            if pin in missing:continue
            bits=c['connections'][pin];assert len(bits)==width
            assert c['port_directions'][pin]==direction
            if direction=='inout':
                assert bits==top['ports'][pin]['bits'];continue
            if direction=='input' and c['type']=='PorBrownoutMacro' and pin=='threshold' and threshold_control:
                row['threshold_driver']=threshold_driver(top,bits)
                port=f'analog_{name}_{pin}';assert port not in top['ports']
                top['ports'][port]=dict(direction='output',bits=bits)
                ports.append(port);row['ports'][pin]=port
                continue
            if direction=='input':
                expected_value=['1'] if c['type']=='LfRcMacro' and pin=='enable' else ['0']*width
                assert bits==expected_value,('Unexpected analog control',name,pin,bits)
                continue
            port=f'analog_{name}_{pin}';assert port not in top['ports']
            top['ports'][port]=dict(direction='input' if direction=='output' else 'output',bits=bits)
            ports.append(port);row['ports'][pin]=port
        analog_cuts.append(row)
    assert sorted(i['module'] for i in analog_cuts)==sorted(definitions)
    # Supply pads have no digital arcs; their original connections remain audited.
    supply={n:top['ports'].pop(n) for n in ('vdd','vss')}
    restored=copy.deepcopy(projected);r=restored['modules']['DeadhorseSoc']
    for p in ports:del r['ports'][p]
    r['ports'].update(supply);r['cells'].update(removed);assert restored==original
    (out/'macro-sockets.json').write_text(json.dumps(cuts,indent=2))
    (out/'analog-sockets.json').write_text(json.dumps(analog_cuts,indent=2))
    if threshold_control:
        # Preserve the audited endpoint/clock aliases through opt_clean -purge.
        # This is the same net-name retention used for island interface pins;
        # the strict mapped Q/cell/clock audit below remains unchanged.
        endpoints=[row['threshold_driver'] for row in analog_cuts
                   if row['module']=='PorBrownoutMacro']
        assert len(endpoints)==1
        endpoint=endpoints[0]
        expected={'digital.subsystem.powerReset.threshold':
                  endpoint['registered_bits']+endpoint['reserved_bits'],
                  'digital.subsystem.powerReset.clk':endpoint['clock_bits']}
        receipt['preserved_threshold_aliases']={}
        for alias,bits in expected.items():
            net=top['netnames'][alias];assert net['bits']==bits
            previous=copy.deepcopy(net.get('attributes',{}))
            net.setdefault('attributes',{})['keep']='1'
            receipt['preserved_threshold_aliases'][alias]=dict(bits=bits,
                previous_attributes=previous,attributes=copy.deepcopy(net['attributes']))
    projected['modules']['DeadhorseSoc'],boundary_bindings=isolate(top,usb)
    top=projected['modules']['DeadhorseSoc']
    receipt['usb_boundary_buffers']=dict(bindings=boundary_bindings,
        equivalence='Every original pin unchanged after collapsing real non-inverting buffers',
        negative_controls=['cycle rejected','wrong input rejected'])
    (out/'cut.json').write_text(json.dumps(projected))
    # Exact parent input aliases are known after flattening, before mapping.
    # Only those boundary aliases may merge; internal state remains injective.
    input_groups={};quotient={};prefix='digital.subsystem.usb.';input_origins={}
    # Kept island input nets can prevent opt_merge from coalescing identical
    # parent ANDs. Exact recursive driver identity also proves that alias; it
    # never derives aliases from a post-mapping net collision.
    parent_drivers={}
    for cell_name,c in top['cells'].items():
        for pin,bs in c['connections'].items():
            if c['port_directions'][pin]=='output':
                for index,b in enumerate(bs):
                    assert b not in parent_drivers
                    parent_drivers[b]=(cell_name,c,pin,index)
    memo={}
    def origin(bit,seen=None):
        if bit in memo:return memo[bit]
        if isinstance(bit,str):
            assert bit in ('0','1');return ('constant',bit)
        seen=set() if seen is None else seen
        assert bit not in seen,'Parent input combinational loop'
        if bit not in parent_drivers:return ('primary',bit)
        name,c,pin,index=parent_drivers[bit]
        if c['type'] not in ('$and','$or','$not','$mux','$eq','$ne','$xor','$xnor',
                '$reduce_and','$reduce_or','$reduce_bool','$logic_and','$logic_or','$logic_not'):
            return ('state_or_macro',name,pin,index)
        seen=seen|{bit}
        value=(c['type'],tuple(sorted(c['parameters'].items())),pin,index,
            tuple((p,tuple(origin(b,seen) for b in bs)) for p,bs in sorted(c['connections'].items()) if c['port_directions'][p]=='input'))
        memo[bit]=value;return value
    for name,p in usb['ports'].items():
        if p['direction']!='input':continue
        actual=top['netnames'][prefix+name]['bits'];assert len(actual)==len(p['bits'])
        for source_bit,parent_bit in zip(p['bits'],actual):
            if isinstance(source_bit,int):
                identity=origin(parent_bit)
                representative=input_groups.setdefault(identity,source_bit) if isinstance(parent_bit,int) else parent_bit
                assert representative not in ('x','z')
                quotient[source_bit]=representative
                input_origins[str(source_bit)]=dict(port=name,parent_bit=parent_bit,cone_sha256=hashlib.sha256(repr(identity).encode()).hexdigest())
    front=[f'read_json {out}/cut.json','hierarchy -top DeadhorseSoc','check -assert',
        'synth -top DeadhorseSoc -flatten -noabc -nofsm',f'dfflibmap -liberty {lib}']
    run(front+[f'write_json {out}/premapped.json'],'premap')
    pre=json.loads((out/'premapped.json').read_text());multiplicity,_=output_aliases(pre['modules']['DeadhorseSoc'])
    constraints=out/'mapping.constr';constraints.write_text(f'set_driving_cell {cfg["library"]}__buf_1\nset_load {cfg["output_load_pf"]*1000*multiplicity:g}\n')
    abc=out/'mapping.abc';abc.write_text('strash; &get -n; &fraig -x; &put; scorr; dc2; strash; '+
        f'&get -n; &dch -f; &nf -D {target_ps}; &put; buffer; upsize -D {target_ps}; dnsize -D {target_ps}; stime -p\n')
    if rom_image:
        isolated_constraints=out/'rom-mapping.constr'
        isolated_constraints.write_text(f'set_driving_cell {cfg["library"]}__buf_1\nset_load {cfg["output_load_pf"]*1000:g}\n')
        run([f'read_json {out}/hier.json',f'hierarchy -top {rom_module}',
            f'synth -top {rom_module} -flatten -noabc -nofsm',f'dfflibmap -liberty {lib}',
            f'abc -liberty {lib} -constr {isolated_constraints} -script {abc}',
            'clean -purge','check -assert',f'tee -o {out}/rom-area.txt stat -liberty {lib}',
            f'write_json {out}/rom-mapped.json'],'rom-map')
        receipt['implemented_rom']['isolated_mapped_sha256']=digest(out/'rom-mapped.json')
        receipt['implemented_rom']['area_scope']='Isolated mapping of the exact ROM including its read registers; not an additive partition of parent ABC optimization. Integrated whole-map includes the initialized ROM.'
    run(front+[f'abc -liberty {lib} -constr {constraints} -script {abc}','clean -purge','check -assert',
        'rename -enumerate',f'write_json {out}/unbuffered.json'],'map')
    design=json.loads((out/'unbuffered.json').read_text());mod=design['modules']['DeadhorseSoc']
    assert output_aliases(mod)[0]<=multiplicity
    audit_boundary(mod,boundary_bindings)
    # Pin-by-pin bijection, before reset buffers: every island bit and port remains.
    bits={};reverse={};matched={};prefix='digital.subsystem.usb.'
    def bind(a,b):
        a=quotient.get(a,a)
        if isinstance(a,str):assert a==b;return
        assert isinstance(b,int) and bits.get(a,b)==b and reverse.get(b,a)==a
        bits[a]=b;reverse[b]=a
    for name,c in usb['cells'].items():
        actual=prefix+name;d=mod['cells'][actual]
        assert c['type']==d['type'] and c['parameters']==d['parameters'] and c['port_directions']==d['port_directions']
        for pin,bs in c['connections'].items():
            assert len(bs)==len(d['connections'][pin])
            for a,b in zip(bs,d['connections'][pin]):bind(a,b)
        matched[name]=actual
    for name,p in usb['ports'].items():
        actual=mod['netnames'][prefix+name]['bits'];assert len(actual)==len(p['bits'])
        for a,b in zip(p['bits'],actual):bind(a,b)
    (out/'island-preservation.json').write_text(json.dumps(dict(status='pass',cells=matched,bits=bits,
        reference_sha256=digest(ref/'mapped.json'),certificate_sha256=digest(ref/'certificate/result.json')),indent=2))
    if counter:
        forward={};backward={}
        def counter_bit(a,b):
            if isinstance(a,str):assert a==b;return
            assert isinstance(b,int) and forward.get(a,b)==b and backward.get(b,a)==a
            forward[a]=b;backward[b]=a
        for name,c in counter['cells'].items():
            d=mod['cells'][counter_prefix+name]
            assert c['type']==d['type'] and c['parameters']==d['parameters'] and c['port_directions']==d['port_directions']
            for pin,bs in c['connections'].items():
                assert len(bs)==len(d['connections'][pin])
                for a,b in zip(bs,d['connections'][pin]):counter_bit(a,b)
        for name,p in counter['ports'].items():
            actual=mod['netnames'][counter_prefix+name]['bits'];assert len(actual)==len(p['bits'])
            for a,b in zip(p['bits'],actual):counter_bit(a,b)
        (out/'counter-preservation.json').write_text(json.dumps(dict(status='pass',bits=forward,
            source_binding=counter_binding['method'],reference_sha256=digest(counter_ref/'mapped.json')),indent=2))
    primary={b for p in mod['ports'].values() if p['direction']=='input' for b in p['bits']}
    clocks={b for c in mod['cells'].values() for b in c['connections'].get('CLK',[])}
    resets={b for c in mod['cells'].values() for p,bs in c['connections'].items() if p in ('RN','SETN') for b in bs if isinstance(b,int)}-primary
    assert not resets&clocks
    new,inserted,reset_rows=layered(mod,resets);verify(mod,new,inserted)
    faulty=copy.deepcopy(new);first=inserted[0];faulty['cells'][first]['connections']['I']=faulty['cells'][first]['connections']['Z'][:]
    try:verify(mod,faulty,inserted)
    except ValueError as e:assert 'cycle' in str(e)
    else:raise AssertionError('Reset buffer-cycle fault escaped')
    sram_buffers=[]
    if sram:
        # ABC sees macros as black boxes and does not size for their relatively
        # large pin loads. Bound non-clock macro fanout to four real loads;
        # paired-corner STA still checks actual Liberty capacitance and slew.
        sources={b for c in new['cells'].values() if c['type'] in macro_widths
            for p,d in c['port_directions'].items() if d=='input' and p!='CLK'
            for b in c['connections'][p] if isinstance(b,int)}
        before=new
        new,sram_buffers=buffer_module(before,'oscIn',limit=4,source_bits=sources,prefix='sram_load_')
        verify(before,new,sram_buffers)
        assert sram_buffers
        fault=copy.deepcopy(new);name=sram_buffers[0]
        fault['cells'][name]['connections']['I']=fault['cells'][name]['connections']['Z'][:]
        try:verify(before,fault,sram_buffers)
        except ValueError as e:assert 'cycle' in str(e)
        else:raise AssertionError('SRAM buffer-cycle fault escaped')
        receipt['sram_load_buffers']=dict(count=len(sram_buffers),fanout_limit=4,
            connection_equivalence='Every original pin preserved after collapsing non-inverting buffers',
            cycle_fault='rejected',electrical='Actual pin capacitance and slew checked by paired-corner STA')
    aliases={}
    for name in list(new['cells']):
        if name.startswith(prefix+'usb_enable_replica_'):
            short=name.removeprefix(prefix);assert short not in new['cells']
            cell=new['cells'].pop(name);aliases[name]=short
            cell['attributes']['usb_enable_original']=prefix+cell['attributes']['usb_enable_original']
            new['cells'][short]=cell
    design['modules']['DeadhorseSoc']=new
    (out/'mapped.json').write_text(json.dumps(design))
    run([f'read_json {out}/mapped.json','check -assert','scc -expect 0',
        f'tee -o {out}/area.txt stat -liberty {lib}',f'write_json {out}/canonical.json',
        f'write_verilog -noattr -noexpr {out}/mapped.v'],'export')
    if threshold_control:
        canonical=json.loads((out/'canonical.json').read_text())['modules']['DeadhorseSoc']
        sockets=[i['ports']['threshold'] for i in analog_cuts if i['module']=='PorBrownoutMacro']
        assert len(sockets)==1
        receipt['threshold_socket']=dict(port=sockets[0],
            **threshold_driver(canonical,canonical['ports'][sockets[0]]['bits'],mapped=True))
    receipt.update(status='mapped',mapped_sha256=digest(out/'canonical.json'),verilog_sha256=digest(out/'mapped.v'),target_ps=target_ps,
        output_alias_multiplier=multiplicity,reset_buffers=len(inserted),reset_roots=reset_rows,
        replica_renames=aliases,projection='Exact restoration',reset_cycle_fault='rejected',retiming=False,fsm_recoding=False)
    assert sealed()==start_hashes,'Mapping inputs changed during run'
    receipt.update(input_sha256=start_hashes,usb_source_binding=source_binding['method'],
        usb_input_alias_quotient=quotient,usb_input_origins=input_origins)
    if counter_ref:receipt['stability_reference']=counter_ref.relative_to(ROOT).as_posix()
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('MAPPED production digital logic; timing and macro qualification still required',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',required=True);parser.add_argument('--usb-reference',required=True)
    parser.add_argument('--target-ps',type=int,default=62500,help='ABC optimization goal only; never an STA budget')
    parser.add_argument('--stability-reference',help='Strict-48MHz mapped counter; source equivalence and exact pin preservation required')
    parser.add_argument('--threshold-control',action='store_true',help='T33 audited live AON threshold output socket')
    parser.add_argument('--sram',action='store_true',help='T35: retain and audit twenty pinned hard SRAM instances; only ROM remains a memory socket')
    parser.add_argument('--rom-image',help='T36 exact initialized production ROM image; requires --sram, maps ROM contents and read registers')
    args=parser.parse_args();main(args.base,args.usb_reference,args.target_ps,args.stability_reference,args.threshold_control,args.sram,args.rom_image)

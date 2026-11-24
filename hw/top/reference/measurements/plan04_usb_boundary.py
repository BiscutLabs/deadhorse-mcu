"""PLAN04 production binding and fresh STA of the identical historical USB fixture.

Historical placement is reused only after fresh emitted-source, wiring, mapped
Q/clock and complete composed-graph equality checks. No whole-chip signoff.
"""
from pathlib import Path
import argparse,copy,fcntl,hashlib,json,re,shutil,subprocess,sys,time
ROOT=Path.cwd();sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'hw/ip/usb'))
from tools.timing.usb_boundary import groups
from physical_evidence import collect
from plan04_screen import clock_manifest
from plan04_usb_binding import bind_source
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base',required=True);parser.add_argument('--output',required=True)
args=parser.parse_args()
base=(ROOT/args.base).resolve();base.relative_to(ROOT/'build')
old=ROOT/'build/plan03/usb-closure';out=(ROOT/args.output).resolve();out.relative_to(ROOT/'build')
out.mkdir(parents=True,exist_ok=False)
def snapshot():
    names=subprocess.check_output(['git','ls-files','-c','-o','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
    return {p:sha(ROOT/p) for p in sorted(set(names)) if p and not p.endswith('.md') and (ROOT/p).is_file()}
frozen=snapshot()
receipt=dict(status='running',commands=[],source_sha256={str(Path(__file__)):sha(__file__)})
def save(): (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
def run(cmd,label):
    start=time.monotonic()
    with(out/(label+'.log')).open('w') as f:code=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT).returncode
    receipt['commands'].append(dict(command=cmd,returncode=code,seconds=time.monotonic()-start));save()
    if code:raise RuntimeError(label+' failed')
    print('PASS '+label,flush=True)
try:
    current=dict(production_source_sha256=frozen)
    mapping=json.loads((base/'map/result.json').read_text())
    assert mapping['status']=='mapped'
    for p,h in mapping['input_sha256'].items():assert sha(ROOT/p)==h,p
    for p,h in mapping['emitted_sha256'].items():assert sha(ROOT/p)==h,p
    assert sha(base/'map/canonical.json')==mapping['mapped_sha256']
    with (ROOT/'build/sbt/compile.lock').open('a') as lock:fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
    usb_json=ROOT/'build/t19/regmap/usb_regs.json'
    assert usb_json.read_bytes()==(ROOT/'build/t20/i1/usb/usb_regs.json').read_bytes()
    run([sys.executable,'tools/sbt.py',f'hw/runMain deadhorse.top.EmitSoc {out.relative_to(ROOT).as_posix()}/fresh-emit production 8',
         f'hw/runMain deadhorse.usb.EmitUsb {out}/fresh-usb {usb_json}'],'fresh-emission')
    old_files={str(p.relative_to(base/'emit')):sha(p) for p in (base/'emit').rglob('*') if p.suffix in ('.sv','.v')}
    fresh_files={str(p.relative_to(out/'fresh-emit')):sha(p) for p in (out/'fresh-emit').rglob('*') if p.suffix in ('.sv','.v')}
    assert old_files==fresh_files,'Production emission differs from measured mapping'
    receipt['fresh_emission_equality']=fresh_files
    # Rebuild the hierarchy from those authenticated fresh inputs; do not trust
    # an unsealed intermediate hier.json left by the earlier mapping run.
    expected={'LfRcMacro':{'vdd':('inout',1),'vss':('inout',1),'enable':('input',1),'trim':('input',6),'test':('input',1),'clock':('output',1),'ready':('output',1)},
        'PorBrownoutMacro':{'vdd':('inout',1),'vss':('inout',1),'threshold':('input',2),'test':('input',1),'supplyReset_n':('output',1),'powerOn_n':('output',1),'brownout':('output',1)}}
    analog={'modules':{}}
    for name,ports in expected.items():
        m={'attributes':{'blackbox':'1'},'cells':{},'ports':{},'netnames':{}};bit=2
        for pin,(direction,width) in ports.items():
            bits=list(range(bit,bit+width));bit+=width
            m['ports'][pin]={'direction':direction,'bits':bits}
            m['netnames'][pin]={'hide_name':0,'bits':bits,'attributes':{}}
        analog['modules'][name]=m
    analog_file=out/'analog-interfaces.json';analog_file.write_text(json.dumps(analog))
    libraries=[ROOT/p for p,h in mapping['input_sha256'].items() if p.endswith('.lib') and h==mapping['liberty_sha256']]
    assert len(libraries)==1
    files=[out/'fresh-emit'/line.strip() for line in (out/'fresh-emit/filelist.f').read_text().splitlines() if line.strip()]
    expected_inputs={str((ROOT/p).relative_to(base/'emit')):h for p,h in mapping['emitted_sha256'].items()}
    assert {str(p.relative_to(out/'fresh-emit')):sha(p) for p in files}==expected_inputs
    hierarchy=out/'fresh-hierarchy.json';script=out/'hierarchy.ys'
    script.write_text('\n'.join([f'read_liberty -lib {libraries[0]}',f'read_json {analog_file}',
        'read_slang --keep-hierarchy -DSYNTHESIS --top DeadhorseSoc '+' '.join(map(str,files)),
        'hierarchy -check -top DeadhorseSoc','proc','chformal -remove','memory_collect',f'write_json {hierarchy}'])+'\n')
    run(['yosys','-Q','-T','-s',str(script)],'fresh-hierarchy')
    previous=old/'bus-source-qualified01/result.json';bound=json.loads(previous.read_text())
    for p,h in bound['artifact_sha256'].items():assert sha(p)==h,p
    for p,h in bound['library_sha256'].items():assert sha(p)==h,p
    slot_file=out/'fresh-emit/SocResetSlot.sv'
    original_slot=ROOT/'build/plan03/adc-retirement/soc-8-production/SocResetSlot.sv'
    assert sha(slot_file)==bound['hdl_sha256'][str(original_slot.relative_to(ROOT))]==sha(original_slot)
    design=json.loads(hierarchy.read_text())['modules']
    parent_name='SocI1Peripherals$DeadhorseSoc.digital.subsystem'
    parent=design[parent_name];usb=parent['cells'][bound['usb']];slot=parent['cells'][bound['source']]
    assert slot['type'].startswith('SocResetSlot$') and usb['type'].startswith('Usb$')
    usb_files=sorted((out/'fresh-usb/usb').glob('*.sv'))+sorted((out/'fresh-usb/usb').glob('*.v'))
    binding=bind_source(hierarchy,usb['type'],{'sources':{str(p):sha(p) for p in usb_files}},out/'usb-logic-binding')
    assert binding['status']=='proved'
    assert slot['connections']['clk']==usb['connections']['appClock']
    # Slot reset release and the raw USB reset are deliberately distinct.
    # Audit the actual shared release/endpoint gate from arbitrary raw resets.
    aliases={c['connections']['Y'][0]:c['connections']['A'][0] for c in parent['cells'].values()
        if c['type']=='$buf' and len(c['connections']['Y'])==len(c['connections']['A'])==1}
    def bit(bits):
        assert len(bits)==1;b=bits[0];seen=set()
        while b in aliases:assert b not in seen;seen.add(b);b=aliases[b]
        return b
    main_release=parent['cells']['mainUp_r'];endpoint_release=parent['cells']['usbAppUp_r']
    for c in (main_release,endpoint_release):
        assert c['type'].startswith('ResetRelease$') and bit(c['connections']['clk'])==bit(usb['connections']['appClock'])
    assert bit(main_release['connections']['reset_n'])==bit(usb['connections']['appReset_n'])
    assert bit(main_release['connections']['released'])==bit(slot['connections']['reset_n'])
    assert bit(endpoint_release['connections']['released'])==bit(slot['connections']['endpointReady'])
    endpoint=bit(slot['connections']['endpointReset_n'])
    assert bit(endpoint_release['connections']['reset_n'])==endpoint
    and_cells=[c for c in parent['cells'].values() if c['type'] in ('$and','$logic_and') and bit(c['connections']['Y'])==endpoint]
    assert len(and_cells)==1 and {bit(and_cells[0]['connections'][p]) for p in ('A','B')}=={
        bit(usb['connections']['appReset_n']),bit(usb['connections']['usbReset_n'])}
    reset_file=out/'fresh-emit/ResetRelease.sv'
    assert sha(reset_file)==bound['hdl_sha256']['build/plan03/adc-retirement/soc-8-production/ResetRelease.sv']
    bus_ports={p:v for p,v in design[usb['type']]['ports'].items() if p.startswith('bus_')}
    for p in bus_ports:assert usb['connections'][p]==slot['connections'][p.replace('bus_','target_')],p
    mapped_origin=base/'map/canonical.json';mapped_path=out/'production-mapped-graph.json'
    shutil.copyfile(mapped_origin,mapped_path);assert sha(mapped_path)==sha(mapped_origin)
    mapped=json.loads(mapped_path.read_text())['modules']['DeadhorseSoc']
    domains=clock_manifest(mapped)
    drivers={b:(n,p) for n,c in mapped['cells'].items() for p,bits in c['connections'].items()
        if c['port_directions'][p]=='output' for b in bits}
    actual={}
    for port,p in bus_ports.items():
        if p['direction']!='input':continue
        bits=mapped['netnames']['digital.subsystem.usb.'+port]['bits']
        for index,bit in enumerate(bits):
            name=port if len(bits)==1 else f'{port}[{index}]';cell,pin=drivers[bit];c=mapped['cells'][cell]
            assert pin=='Q' and c['type']==bound['ports'][name]['type']
            assert c['connections']['CLK']==mapped['netnames']['digital.subsystem.usb.appClock']['bits']
            assert domains[cell+'/CLK']=='main','Bus driver not on the divider-derived main clock'
            actual[name]=dict(cell=cell,type=c['type'],pin=pin)
    assert len(actual)==len(bound['ports'])==73
    # Fresh extrema calculation, identical library tables and actual driver types.
    extrema={}
    for filename,h in bound['library_sha256'].items():
        lib=Path(filename);corner=lib.stem.split('__')[1];cells=dict(groups(lib.read_text(),'cell'));extrema[corner]={}
        for typ in {r['type'] for r in actual.values()}:
            values=[];q=dict(groups(cells[typ],'pin'))['Q']
            for _,arc in groups(q,'timing'):
                if not re.search(r'related_pin\s*:\s*"CLK"',arc):continue
                for kind in ('cell_rise','cell_fall'):
                    for _,table in groups(arc,kind):
                        raw=re.search(r'values\s*\((.*?)\)\s*;',table,re.S)[1]
                        values.extend(float(v) for v in re.findall(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?',raw))
            assert values and min(values)>0
            extrema[corner][typ]=dict(min_ns=min(values),max_ns=max(values))
    assert extrema==bound['corners']
    bound['source_sha256']=current['production_source_sha256']
    bound['production_parent']=parent_name
    bound['hdl_sha256']={str(p):sha(p) for p in (out/'fresh-emit').rglob('*') if p.suffix in ('.sv','.v')}
    bound['artifact_sha256'].update({str(p):sha(p) for p in (hierarchy,script,analog_file,base/'map/result.json',mapped_path,slot_file,out/'usb-logic-binding/result.json')})
    bound['current_mapped_ports']=actual
    bound['requalification']=dict(original=str(previous),sha256=sha(previous),runner_sha256=sha(__file__),
        production_mapped_origin=str(mapped_origin),production_mapped_origin_sha256=sha(mapped_origin),
        qualification='Fresh both-way production wiring/clock/reset and all actual mapped Q checks; byte-identical slot HDL; unchanged mapped fixture cell names retained in ports, actual full-SoC identities separately recorded. Recomputed five-corner CQ extrema.')
    binding=out/'bus-source-qualified01/result.json';binding.parent.mkdir();binding.write_text(json.dumps(bound,indent=2)+'\n')
    bus=out/'bus-physical01'
    run([sys.executable,'tools/physical/usb_bus_fixture.py','--usb',str(ROOT/'build/t19/boundary-frozen-fast-01/fast/usb/timing/usb/mapped.json'),
        '--slot',str(old/'source-slot01/mapped.json'),'--binding',str(binding),'--output',str(bus)],'compose')
    assert json.loads((bus/'composed.json').read_text())==json.loads((old/'bus-physical01/composed.json').read_text()),'Fresh fixture graph differs'
    copied={}
    for p in (old/'bus-physical01').iterdir():
        if p.name in ('composed.json','composition.json','boundary-result.json','boundary-timing'):continue
        target=bus/p.name
        if p.is_dir():shutil.copytree(p,target)
        else:shutil.copyfile(p,target)
    for p in bus.rglob('*'):
        if p.is_file() and p.name not in ('composed.json','composition.json'):
            q=old/'bus-physical01'/p.relative_to(bus);assert sha(p)==sha(q);copied[str(p)]=sha(p)
    receipt['reused_placement_sha256']=copied
    for name in ('plan03_bus_hold.py','plan03_bus_timing.py'):
        source=ROOT/'scratch'/name;code=source.read_text()
        assert sha(source)=={'plan03_bus_hold.py':'f8a12ed4ddc330653adf3ed9c37f83ec307b4ba7db684382e9c70e05504519af',
            'plan03_bus_timing.py':'5a0d7473f287d478d91929846f2fa11cbf39595f3e8c1c89d4d921be0717fd5b'}[name]
        rewrites=([( "Path('build/plan03/usb-closure')",f"Path('{out.relative_to(ROOT).as_posix()}')"),
            ("physical=root/'physical-hold01-audited'",f"physical=Path('{old}/physical-hold01-audited')")]
            if name=='plan03_bus_hold.py' else [
            ("root/'build/plan03/usb-closure/bus-physical01'",f"root/'{bus.relative_to(ROOT).as_posix()}'"),
            ("out.parent/'physical-hold01/replacements.json'",f"Path('{old}/physical-hold01/replacements.json')")])
        for before,after in rewrites:
            assert code.count(before)==1,(name,before)
            code=code.replace(before,after)
        driver=out/name;driver.write_text(code)
        run([sys.executable,str(driver)],name)
    manifest=json.loads((old/'physical-manifest03.json').read_text())
    manifest.update(seal=str(ROOT/'build/t32/usb-physical-binding03/derived-seal.json'),source=str(binding),
        bus=str(bus),hold=str(out/'bus-hold01/result.json'))
    # Collector requires scratch provenance for this historical driver interface.
    hold_driver=ROOT/'scratch'/('plan04_bus_hold_'+out.name+'.py');shutil.copyfile(out/'plan03_bus_hold.py',hold_driver)
    manifest['hold_driver']=str(hold_driver)
    manifest_path=out/'physical-manifest.json';manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    result=collect(manifest_path,out/'fresh-usb/usb',out/'physical-audit')
    assert result['status']=='pass'
    acceptance=dict(schema=1,physical=str(manifest_path),sampling='build/t32/usb-acceptance-inputs01/sampling-manifest.json',packet='build/t32/usb-acceptance-inputs01/packet-manifest.json')
    (out/'acceptance-manifest.json').write_text(json.dumps(acceptance,indent=2)+'\n')
    assert snapshot()==frozen,'Sources changed during boundary qualification'
    receipt['status']='pass'
    receipt['qualification']='Fresh production binding and STA of byte-identical historical USB fixtures: historical app/AON 41.6 ns, USB 20.8333 ns, asynchronous groups and 24.96 ns bus ceiling. Not generated-8MHz/32kHz whole-top STA, clock-insertion/reset-control or physical crossing-phase qualification.'
except Exception as e:receipt.update(status='failed',error=str(e))
receipt['artifact_sha256']={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
save();print(receipt['status'],receipt.get('error',''),flush=True)
sys.exit(0 if receipt['status']=='pass' else 1)

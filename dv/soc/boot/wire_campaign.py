"""Run the real production cores against pin-only NOR/UART boot peers."""
import argparse,hashlib,json,os,pathlib,shutil,subprocess,sys,time
from image import header,bundle
from wire_protocol import request,record,replies

ROOT=pathlib.Path.cwd();HERE=pathlib.Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot():
 names=subprocess.check_output(['git','ls-files','-c','-o','--exclude-standard','-z'],text=True).split('\0')
 return {n:sha(ROOT/n) for n in sorted(set(names)) if n and (ROOT/n).is_file()}
def main():
 p=argparse.ArgumentParser();p.add_argument('--warm-only',action='store_true');p.add_argument('--prepared',required=True);p.add_argument('--rom-build',required=True);p.add_argument('--output',required=True)
 a=p.parse_args();prepared=(ROOT/a.prepared).resolve();rom=(ROOT/a.rom_build).resolve();out=(ROOT/a.output).resolve()
 out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
 inputs=json.loads((prepared/'prepared.json').read_text());built=json.loads((rom/'result.json').read_text())
 assert inputs['status']=='prepared' and built['status']=='built'
 assert set(inputs['cases'])=={'core-smoke','a','newest-b','golden','held','empty','strap','corrupt-newest','uncommitted','warm-match','warm-reload','warm-lite-reload','warm-bad-context',
   'tie-a','bad-directory','bad-range','bad-generation','bad-compatibility','bad-extent','warm-flash-missing','warm-flash-corrupt','warm-newer','warm-dma-drain','warm-dma-stall','warm-bad-context-reset','watcher-held','max-lite-held'}
 for base,receipt in ((prepared,inputs),(rom,built)):
  for n,h in receipt['artifact_sha256'].items():assert sha(base/n)==h,n
  for n,h in receipt['source_sha256'].items():assert sha(pathlib.Path(n))==h,n
 assert (rom/'rom.hex').read_bytes()==(prepared/'rom.hex').read_bytes()
 receipt=dict(status='running',selection='warm-only' if a.warm_only else 'all',unrun_cases=([n for n in inputs['cases'] if not n.startswith('warm-')] if a.warm_only else []),commands=[],cases={},scope='Production top with passive RVFI/reset outputs and independent NOR/UART pins; no injected bus master',
  source_sha256=snapshot(),
  inputs={str(q):sha(q) for q in [prepared/'prepared.json',rom/'result.json',HERE/'sim.cpp',HERE/'nor.hpp',pathlib.Path(__file__),HERE/'wire_protocol.py',HERE/'image.py']})
 if a.warm_only:
  payload_bytes=len((prepared/'b.bin').read_bytes());payload_bytes+=(4-payload_bytes%4)%4
  lite_bytes=len((prepared/'lite.bin').read_bytes());lite_bytes+=(4-lite_bytes%4)%4
  cuts=(1,5,4+(payload_bytes+lite_bytes+4)//4+23)
  receipt['unrun_cases'] += ['uart-basic','uart-update','updated-cold-boot','early-release']
  receipt['unrun_cases'] += [label+str(cut) for cut in cuts for label in ('cut-','restart-cut-')]
 probe=ROOT/'hw/top/reference/src/test/scala/deadhorse/top/SocBootRomProbe.scala'
 receipt['inputs'][str(probe)]=sha(probe)
 generated=[ROOT/'build/t20/map/soc.json']
 for directory in ('build/t20/i1','build/t21/gpio','build/t21/timers','build/t21/aon_timer',
    'build/t23/dma','build/t24/pinmux','build/t26/watchdog','build/t28/boot_control',
    'build/t30/qspi','build/plan05/aon_spi','build/plan05/aon_gpio'):
  generated+=sorted((ROOT/directory).rglob('*_regs.json'))
 assert len(generated)>=18
 receipt['generated_configuration_sha256']={str(q):sha(q) for q in generated}
 def save():(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
 def run(command,label,env=None,expected=0,timeout=600):
  start=time.monotonic()
  with (out/(label+'.log')).open('w') as log:
   r=subprocess.run(list(map(str,command)),env=env,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
  receipt['commands'].append(dict(command=list(map(str,command)),seconds=time.monotonic()-start,returncode=r.returncode,expected=expected));save()
  if r.returncode!=expected:raise RuntimeError(label)
 def execute(label,image,scenario,marker,selected=None,records=None,power_cut=None):
  env=os.environ.copy()
  for key in ('DH_FAIL_PC','DH_EXPECTED_MARKER','DH_SELECTED_SLOT','DH_POWER_CUT','DH_COMPETING_BLOB','DH_MAX_LITE_LOAD_D104'):env.pop(key,None)
  env.update(DH_FAIL_PC=str(built['fail_pc']),DH_EXPECTED_MARKER=str(marker))
  if selected is not None:env['DH_SELECTED_SLOT']=str(selected)
  if power_cut is not None:env['DH_POWER_CUT']=str(power_cut)
  if scenario=='warm-newer':env['DH_COMPETING_BLOB']=str(prepared/'competing-b.bundle')
  if label=='max-lite-held':env['DH_MAX_LITE_LOAD_D104']='1'
  command=[out/'obj/VSocBootRomProbe',image,scenario]
  response=out/(label+'.reply')
  if records is not None:
   path=out/(label+'.requests');path.write_bytes(records);command += [path,response]
  run(command,label,env,3 if power_cut is not None else 0)
  lines=(out/(label+'.log')).read_text().splitlines();result=json.loads(next(x for x in reversed(lines) if x.startswith('{')))
  assert result['status']==('power-cut' if power_cut is not None else 'pass')
  if power_cut is None:
   assert result['lite_load_budget_met'] or (label=='max-lite-held' and result['lite_load_D104_exception'])
   assert not result['lite_load_D104_exception'] or label=='max-lite-held'
  receipt['cases'][label]=dict(result=result,input_sha256=sha(image),scenario=scenario,marker=marker,selected_slot=selected,
   rom_sha256=sha(out/'active-rom.hex'),request_sha256=None if records is None else hashlib.sha256(records).hexdigest())
  save();return result,response
 try:
  active=out/'active-rom.hex';shutil.copyfile(rom/'rom.hex',active)
  emit=out/'emit';run([sys.executable,'tools/sbt.py',f'hw/Test/runMain deadhorse.top.EmitBootRomProbe {emit} {active}'],'emit')
  sources=sorted(emit.glob('*.sv'))+sorted(emit.glob('*.v'));package=emit/'dm_pkg.sv';sources.remove(package);sources.insert(0,package)
  assert sha(emit/'dm_csrs.sv')=='1614f20608419d944fee249dd706e4f275dabc6cdbc9102159806ef73d05d641'
  gate=ROOT/'hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv'
  control=out/'debug-selector.vlt';control.write_text('`verilator_config\n'+f'lint_off -rule CMPCONST -file "{emit}/dm_csrs.sv" -match "Comparison is constant due to limited range*"\n')
  run(['verilator','--cc','--exe','--build','--assert','-DENABLE_INITIAL_MEM_','-DENABLE_INITIAL_REG_','-j','4',
    '--top-module','SocBootRomProbe','--Mdir',out/'obj',control,*sources,gate,HERE/'sim.cpp'],'compile')
  receipt['emission_sha256']={str(q):sha(q) for q in [*sources,gate,control]}
  for name,c in inputs['cases'].items():
   if not a.warm_only or name.startswith('warm-'):execute(name,prepared/(name+'.flash'),c['scenario'],c['marker'],c['selected_slot'])
  if not a.warm_only:
   # Independent frame expectations bind exact opcode, sequence and address,
   # including malformed/no-response records and staging byte masks.
   commands=[(5,1,0,b'',b'\0\1'+(0x35304844).to_bytes(4,'little')+(0x117).to_bytes(4,'little')),
    (3,2,0x20003980,b'abcd',b'\0\4\0'),(1,3,0x20003980,b'',b'\0abcd'),
    (2,4,0x20003980,b'WXYZ\x05',b'\0'),(1,5,0x20003980,b'',b'\0WbYd'),
    (2,6,0x30000000,b'1234\x0f',b'\2'),(4,7,0,b'',b'\1')]
   records=b''.join(record(request(op,seq,addr,payload)) for op,seq,addr,payload,_ in commands)
   # Bad COBS framing is ignored, and the next valid request still responds.
   records+=record(b'\x05\x01\0',0,deadline=960000)
   records+=record(request(5,8))
   _,response=execute('uart-basic',prepared/'strap.flash','strap',0,records=records)
   actual=replies(response.read_bytes());expected=[dict(op=op,seq=seq,address=addr,payload=value) for op,seq,addr,_,value in commands]
   expected.append(dict(op=5,seq=8,address=0,payload=commands[0][-1]));assert actual==expected
   perf=(prepared/'b.bin').read_bytes();perf+=bytes((-len(perf))%4)
   lite=(prepared/'lite.bin').read_bytes();lite+=bytes((-len(lite))%4);payload=perf+lite+b'CFG1'
   candidate=header(perf,lite,b'CFG1',generation=2,committed=False,lite_data=8,lite_stack=16)
   begin=request(0x10,1,1,candidate)
   # INFO arrives while BEGIN executes; it must return BUSY without nesting an update.
   records=record(begin+request(5,2),2)+record(begin)
   expectations=[dict(op=0x10,seq=1,address=1,payload=b'\0'),dict(op=5,seq=2,address=0,payload=b'\5')]
   expectations.append(dict(op=0x10,seq=1,address=1,payload=b'\0'))
   seq=3
   for at in range(0,len(payload),256):
    data=payload[at:at+256];records+=record(request(0x11,seq,256+at,data))
    expectations.append(dict(op=0x11,seq=seq,address=256+at,payload=b'\0'));seq+=1
   # Exercise concurrent COMMIT/BUSY replies; arrival need not hit peak stack use.
   records+=record(request(0x12,seq)+request(5,seq+1),2)
   expectations.append(dict(op=0x12,seq=seq,address=0,payload=b'\0'))
   expectations.append(dict(op=5,seq=seq+1,address=0,payload=b'\5'))
   measured,response=execute('uart-update',prepared/'strap.flash','strap',0,records=records)
   actual=replies(response.read_bytes())
   assert len(actual)==len(expectations)
   assert sorted(actual[:2],key=lambda x:x['seq'])==expectations[:2]
   assert actual[2:-2]==expectations[2:-2] and sorted(actual[-2:],key=lambda x:x['seq'])==expectations[-2:]
   assert measured['erases']==4 and measured['programs']==len(payload)//4+24 and measured['last_program_address']==36864+92
   updated=pathlib.Path(str(response)+'.flash');image=updated.read_bytes();old=(prepared/'strap.flash').read_bytes()
   assert image[:36864]==old[:36864] and image[36864+16384:]==old[36864+16384:]
   expected_bundle=bundle(perf,lite,b'CFG1',generation=2,lite_data=8,lite_stack=16)
   assert image[36864:36864+len(expected_bundle)]==expected_bundle
   execute('updated-cold-boot',updated,'normal',0xb2,2)
   # Three actual wire operation-boundary power cuts supplement the exhaustive
   # native partial-write/erase model checks. Every restart uses a new whole SoC.
   for cut in (1,5,4+len(payload)//4+23):
    _,response=execute('cut-'+str(cut),prepared/'strap.flash','strap',0,records=records,power_cut=cut)
    cut_image=pathlib.Path(str(response)+'.flash')
    assert cut_image.read_bytes()[:36864]==old[:36864]
    execute('restart-cut-'+str(cut),cut_image,'normal',0xa1,1)
   negative=out/'early-release-rom'
   run([sys.executable,ROOT/'sw/boot/build_rom.py','--output',negative,'--negative-control','EARLY_RELEASE'],'build-early-release')
   fault=json.loads((negative/'result.json').read_text());assert fault['status']=='built-negative-control'
   env=os.environ.copy();env.update(DH_EXPECTED_MARKER=str(0xa1),DH_SELECTED_SLOT='1')
   try:
    shutil.copyfile(negative/'rom.hex',active)
    run([out/'obj/VSocBootRomProbe',prepared/'a.flash','normal'],'early-release',env,1)
    assert 'early lite release' in (out/'early-release.log').read_text()
    receipt['cases']['early-release']=dict(status='fault-rejected',rom_sha256=sha(active),input_sha256=sha(prepared/'a.flash'))
   finally:shutil.copyfile(rom/'rom.hex',active)
  # The paired-image scoreboards must reject skipped warm reload, independent
  # of whether a corrupt instruction would happen to execute successfully.
  negative=out/'warm-skip-rom'
  run([sys.executable,ROOT/'sw/boot/build_rom.py','--output',negative,'--negative-control','WARM_SKIP_RELOAD'],'build-warm-skip')
  fault=json.loads((negative/'result.json').read_text());assert fault['status']=='built-negative-control'
  env=os.environ.copy();env.update(DH_FAIL_PC=str(fault['fail_pc']),DH_EXPECTED_MARKER=str(0xe2),DH_SELECTED_SLOT='1')
  try:
   shutil.copyfile(negative/'rom.hex',active)
   run([out/'obj/VSocBootRomProbe',prepared/'warm-reload.flash','warm-reload'],'warm-skip',env,1)
   assert 'early warm lite release before paired-image confirmation' in (out/'warm-skip.log').read_text()
   receipt['cases']['warm-skip']=dict(status='fault-rejected',rom_sha256=sha(active),input_sha256=sha(prepared/'warm-reload.flash'))
  finally:shutil.copyfile(rom/'rom.hex',active)
  assert all(sha(pathlib.Path(q))==h for q,h in receipt['inputs'].items())
  assert all(sha(pathlib.Path(q))==h for q,h in receipt['generated_configuration_sha256'].items())
  assert snapshot()==receipt['source_sha256'],'Production sources changed during campaign'
  receipt['exceptions']={name:'D104: maximum 1KiB lite load exceeds250ms; T42 follow-up' for name,case in receipt['cases'].items() if case.get('result',{}).get('lite_load_D104_exception')}
  receipt['status']='pass_with_exception' if receipt['exceptions'] else 'pass'
 except Exception as error:receipt.update(status='failed',error=str(error));raise
 finally:
  receipt['artifact_sha256']={str(q.relative_to(out)):sha(q) for q in out.rglob('*') if q.is_file() and q.name!='result.json'};save()
 print('PASS '+('warm-only' if a.warm_only else 'full')+' production boot pin campaign; bounded persistence only')
if __name__=='__main__':main()

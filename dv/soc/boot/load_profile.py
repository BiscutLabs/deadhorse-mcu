"""T42 passive production boot baseline: exactly two load cases, no CI."""
import argparse,json,os,pathlib,shutil,subprocess,sys,time
from wire_campaign import sha,snapshot

ROOT=pathlib.Path.cwd();HERE=pathlib.Path(__file__).resolve().parent
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
 out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
 receipt=dict(status='running',base_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
  source_sha256=snapshot(),commands=[],cases={},scope='Passive profiling of watcher-held and max-lite-held only; all other boot cases unrun in this investigation; no CI/proof/implementation claim')
 def save():(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
 def run(cmd,name,env=None):
  start=time.monotonic()
  with (out/(name+'.log')).open('w') as log:
   r=subprocess.run(list(map(str,cmd)),stdout=log,stderr=subprocess.STDOUT,env=env,timeout=600)
  receipt['commands'].append(dict(command=list(map(str,cmd)),seconds=time.monotonic()-start,returncode=r.returncode));save()
  if r.returncode:raise RuntimeError(name+' failed; see log')
 try:
  run([sys.executable,'dv/soc/prepare_production.py'],'prepare')
  rom=ROOT/'build/t36/rom';built=json.loads((rom/'result.json').read_text())
  assert built['status']=='built'
  for path,digest in built['source_sha256'].items():assert sha(pathlib.Path(path))==digest
  for path,digest in built['artifact_sha256'].items():assert sha(rom/path)==digest
  prepared=out/'prepared'
  run([sys.executable,HERE/'wire_prepare.py','--output',prepared,'--rom',rom/'rom.bin'],'fixtures')
  fixtures=json.loads((prepared/'prepared.json').read_text())
  active=out/'active-rom.hex';shutil.copyfile(rom/'rom.hex',active)
  assert (prepared/'rom.hex').read_bytes()==active.read_bytes()
  emit=out/'emit'
  run([sys.executable,'tools/sbt.py',f'hw/Test/runMain deadhorse.top.EmitBootRomProbe {emit} {active}'],'emit')
  sources=sorted(emit.glob('*.sv'))+sorted(emit.glob('*.v'));package=emit/'dm_pkg.sv';sources.remove(package);sources.insert(0,package)
  assert sha(emit/'dm_csrs.sv')=='1614f20608419d944fee249dd706e4f275dabc6cdbc9102159806ef73d05d641'
  gate=ROOT/'hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv'
  control=out/'debug-selector.vlt';control.write_text('`verilator_config\n'+f'lint_off -rule CMPCONST -file "{emit}/dm_csrs.sv" -match "Comparison is constant due to limited range*"\n')
  run(['verilator','--cc','--exe','--build','--assert','-DENABLE_INITIAL_MEM_','-DENABLE_INITIAL_REG_','-j','4',
   '--top-module','SocBootRomProbe','--Mdir',out/'obj',control,*sources,gate,HERE/'sim.cpp'],'compile')
  receipt['emission_sha256']={str(q):sha(q) for q in [*sources,gate,control]}
  for name in ('watcher-held','max-lite-held'):
   case=fixtures['cases'][name];env=os.environ.copy()
   for key in ('DH_POWER_CUT','DH_COMPETING_BLOB','DH_MAX_LITE_LOAD_D104'):env.pop(key,None)
   env.update(DH_FAIL_PC=str(built['fail_pc']),DH_EXPECTED_MARKER=str(case['marker']),
    DH_SELECTED_SLOT=str(case['selected_slot']),DH_TRANSFER_TRACE=str(out/(name+'.csv')))
   if name=='max-lite-held':env['DH_MAX_LITE_LOAD_D104']='1'
   run([out/'obj/VSocBootRomProbe',prepared/(name+'.flash'),case['scenario']],name,env)
   result=json.loads(next(s for s in reversed((out/(name+'.log')).read_text().splitlines()) if s.startswith('{')))
   assert result['status']=='pass'
   assert result['lite_load_budget_met'] or name=='max-lite-held' and result['lite_load_D104_exception']
   receipt['cases'][name]=result;save()
  assert snapshot()==receipt['source_sha256'],'sources changed during profiling'
  receipt['status']='measured_with_D104_exception' if receipt['cases']['max-lite-held']['lite_load_D104_exception'] else 'measured'
 except Exception as error:receipt.update(status='failed',error=str(error));raise
 finally:
  receipt['artifact_sha256']={str(q.relative_to(out)):sha(q) for q in out.rglob('*') if q.is_file() and q!=out/'result.json'};save()
 print(receipt['status']+'; only two boot cases executed; no CI')
if __name__=='__main__':main()

"""Focused T36 native/wire campaign; no aggregate CI or unrelated IP tests."""
import argparse,hashlib,json,os,pathlib,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[3];HERE=pathlib.Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True)
 a=p.parse_args();out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
 source_paths=sorted((ROOT/'sw/boot').glob('*'))+sorted(HERE.glob('*'))+[ROOT/'tools/env/lock.json']
 sources={str(q):sha(q) for q in source_paths if q.is_file()}
 receipt=dict(status='running',commands=[],source_sha256=sources,scope='Native ROM policy/recovery plus production pin-level NOR/UART tests; finite simulation, not proof')
 def save():(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
 def run(args,label,expected=0,env=None,marker=None):
  start=time.monotonic()
  with (out/(label+'.log')).open('w') as log:r=subprocess.run(list(map(str,args)),cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
  receipt['commands'].append(dict(command=list(map(str,args)),returncode=r.returncode,expected=expected,seconds=time.monotonic()-start));save()
  text=(out/(label+'.log')).read_text()
  if r.returncode!=expected or marker and marker not in text:raise RuntimeError(label)
 try:
  run([sys.executable,'dv/soc/prepare_production.py'],'prepare')
  for script,name in [('test_policy.py','policy'),('test_recovery.py','recovery')]:
   env=os.environ.copy();env.pop('DH_BOOT_FAULT',None);env['DH_BOOT_TEST_OUTPUT']=str(out/('native-'+name))
   run([sys.executable,HERE/script,'-v'],'native-'+name,env=env,marker='OK')
  for script,fault,test in [('test_policy.py','CRC','Policy.test_crc'),
    ('test_recovery.py','RANGE','Recovery.test_capability_permissions_duplicates'),
    ('test_recovery.py','COMMIT','Recovery.test_stream_commit_and_busy')]:
   env=os.environ.copy();env.update(DH_BOOT_FAULT=fault,DH_BOOT_TEST_OUTPUT=str(out/('fault-'+fault)))
   run([sys.executable,HERE/script,test,'-v'],'fault-'+fault,expected=1,env=env,marker='FAIL: '+test.split('.')[-1])
  run([sys.executable,HERE/'wire_prepare.py','--output',out/'prepared','--rom','build/t36/rom/rom.bin'],'wire-prepare')
  run([sys.executable,HERE/'wire_campaign.py','--prepared',out/'prepared','--rom-build','build/t36/rom','--output',out/'wire'],'wire')
  wire=json.loads((out/'wire/result.json').read_text());assert wire['status'] in ('pass','pass_with_exception')
  assert all(sha(pathlib.Path(q))==h for q,h in sources.items())
  receipt['exceptions']=wire.get('exceptions',{});receipt['status']=wire['status']
 except Exception as e:receipt.update(status='failed',error=str(e));raise
 finally:
  receipt['artifact_sha256']={str(q.relative_to(out)):sha(q) for q in out.rglob('*') if q.is_file() and q!=out/'result.json'};save()
 print('PASS focused T36 ROM native and serial-wire checks; no CI run')
if __name__=='__main__':main()

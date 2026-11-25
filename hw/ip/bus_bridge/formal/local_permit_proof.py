"""T42 exact local grant, arbitrary request/reset/clocks; capped proof and faults."""
import argparse,hashlib,json,pathlib,subprocess,sys,time
ROOT=pathlib.Path.cwd()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
 out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
 paths=[pathlib.Path(__file__),ROOT/'hw/ip/bus_bridge/formal/LocalPermitFormal.scala',ROOT/'hw/ip/bus_bridge/src/main/scala/deadhorse/bus_bridge/LocalPermit.scala']
 receipt=dict(status='running',runs=[],source_sha256={str(q):sha(q) for q in paths},assumptions=['reset asserted initially, thereafter arbitrary'],
  scope='unconstrained requests and independent observation/source clocks; local grant only, not bridge composition')
 start=time.monotonic()
 def run(cmd,label,timeout=150):
  before=time.monotonic()
  with (out/(label+'.log')).open('w') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
  item=dict(command=cmd,seconds=time.monotonic()-before,returncode=r.returncode);receipt['runs'].append(item);return item
 try:
  assert run([sys.executable,'tools/sbt.py',f'hw/runMain deadhorse.bus_bridge.EmitLocalPermitFormal {out}/emit'],'emit',600)['returncode']==0
  for v in ('correct','stuck','late','reset','cover'):
   sources=sorted((out/'emit'/v).glob('*.sv'));cover=v=='cover';expected='FAIL' if v in ('stuck','late','reset') else 'PASS'
   config=out/(v+'.sby')
   config.write_text('\n'.join(['[options]','mode '+('cover' if cover else 'prove'),'multiclock on','depth 64','timeout 120','',
    '[engines]','smtbmc z3' if cover else 'abc pdr','','[script]',
    'read_slang --top LocalPermitFormal '+' '.join(q.name for q in sources),'prep -top LocalPermitFormal -flatten',
    "fminit -seq reset_n 0,'z",'clk2fflogic','chformal -lower',
    'select -assert-count '+('3 t:$cover' if cover else '2 t:$assert'),'','[files]',*map(str,sources),'']))
   item=run(['sby','-d',str(out/v),str(config)],v)
   status=(out/v/'status').read_text().split()[0];item['status']=status
   assert status==expected and item['returncode']==(2 if expected=='FAIL' else 0),v+': '+status
   if v!='correct':assert list((out/v).glob('engine_*/trace*.vcd'))
   print(v+': '+status,flush=True)
  assert receipt['source_sha256']=={str(q):sha(q) for q in paths}
  receipt['status']='pass'
 except Exception as e:receipt.update(status='unresolved' if isinstance(e,subprocess.TimeoutExpired) or 'TIMEOUT' in str(e) else 'failed',error=str(e))
 finally:
  receipt['seconds']=time.monotonic()-start
  receipt['artifact_sha256']={str(q.relative_to(out)):sha(q) for q in out.rglob('*') if q.is_file() and q.name!='result.json'}
  (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
 if receipt['status']!='pass':raise SystemExit(receipt.get('error','proof failed'))
if __name__=='__main__':main()

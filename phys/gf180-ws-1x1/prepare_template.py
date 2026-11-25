"""Materialize selected byte-exact wafer.space template inputs under build/."""
import argparse,hashlib,json,pathlib,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[2]
HERE=pathlib.Path(__file__).resolve().parent
def main():
 start=time.monotonic();p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 source=(ROOT/a.source).resolve();source.relative_to(ROOT/'build')
 out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
 lock=json.loads((HERE/'template.lock.json').read_text())
 revision=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip();assert revision==lock['revision']
 for name,expected in lock['files'].items():
  relative=pathlib.PurePosixPath(name);assert not relative.is_absolute() and '..' not in relative.parts
  raw=subprocess.check_output(['git','-C',str(source),'show',revision+':'+name]);assert hashlib.sha256(raw).hexdigest()==expected,name
  target=out/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
 receipt=dict(status='authenticated_not_qualified',revision=revision,files=lock['files'],patches=lock['patches'],seconds=time.monotonic()-start,command=sys.argv,source_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
  lock_sha256=hashlib.sha256((HERE/'template.lock.json').read_bytes()).hexdigest(),scope='Original example and physical collateral only; no Deadhorse pad-library decision, PDK adoption or flow pass')
 (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('PASS '+str(len(lock['files']))+' authenticated template files; physical qualification not claimed')
if __name__=='__main__':main()

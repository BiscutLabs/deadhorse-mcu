"""Prepare the production ROM, reusing only a source-authenticated exact build."""
import hashlib,json,pathlib,shutil,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 target=ROOT/'build/t36/rom';receipt=target/'result.json'
 if receipt.exists():
  old=json.loads(receipt.read_text())
  if old.get('status')=='built' and all(pathlib.Path(n).is_file() and sha(pathlib.Path(n))==h for n,h in old['source_sha256'].items()) and all((target/n).is_file() and sha(target/n)==h for n,h in old['artifact_sha256'].items()):
   print('REUSED exact authenticated production ROM build');return
 build=ROOT/'build/t36/rom-builds'/str(time.time_ns())
 subprocess.run([sys.executable,ROOT/'sw/boot/build_rom.py','--output',build],cwd=ROOT,check=True)
 target.mkdir(parents=True,exist_ok=True)
 built=json.loads((build/'result.json').read_text());assert built['status']=='built'
 for name,value in built['artifact_sha256'].items():
  source=build/name;assert sha(source)==value
  dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
 shutil.copyfile(build/'result.json',receipt)
 print('BUILT production ROM',built['rom_payload_bytes'],'measured firmware bytes; area not measured here')
if __name__=='__main__':main()

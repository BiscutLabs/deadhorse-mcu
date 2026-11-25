"""Authenticate the selected PDK analog models for scoped diagnostics."""
import argparse,hashlib,json,pathlib,subprocess
root=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
out=(root/a.output).resolve();out.relative_to(root/'build')
out.mkdir(parents=True,exist_ok=False)
archive=root/'build/t43/pdk-candidate/common.tar.zst'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
lock=root/'phys/gf180-ws-1x1/pdk-lock.json'
assert sha(archive)==json.loads(lock.read_text())['archives']['common.tar.zst']['sha256']
subprocess.run(['tar','--zstd','-xf',str(archive),'-C',str(out),'gf180mcuD/libs.tech/ngspice'],check=True)
receipt=dict(archive_sha256=sha(archive),lock_sha256=sha(lock),helper_sha256=sha(pathlib.Path(__file__)),files={str(q.relative_to(out)):sha(q) for q in out.rglob('*') if q.is_file()})
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('PASS authenticated analog model extraction')

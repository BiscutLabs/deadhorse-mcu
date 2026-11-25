"""Scoped native cursor oracle and RV32 driver/example compilation."""
import argparse,hashlib,json,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',default='build/t40/driver')
out=(ROOT/ap.parse_args().output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
paths=[ROOT/p for p in ['sw/hal/dma_ring.h','sw/hal/dma_ring_example.c',
 'sw/hal/tests/dma_ring_test.c','sw/hal/tests/test_dma_ring.py','build/t23/dma/dma_regs.h','build/t20/map/soc.h','tools/env/lock.json']]
hashes=lambda:{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
r=dict(source_sha256=hashes(),commands=[])
for cmd in [
 ['cc','-std=c11','-Wall','-Wextra','-Werror','-Isw/hal','-Ibuild/t23/dma','-Ibuild/t20/map','sw/hal/tests/dma_ring_test.c','-o',str(out/'native')],
 [str(out/'native')],
 ['riscv64-unknown-elf-gcc','-march=rv32imfc','-mabi=ilp32','-Os','-ffreestanding','-Wall','-Wextra','-Werror','-Isw/hal','-Ibuild/t23/dma','-Ibuild/t20/map','-c','sw/hal/dma_ring_example.c','-o',str(out/'example.o')]]:
 start=time.monotonic();v=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
 r['commands'].append(dict(command=cmd,returncode=v.returncode,seconds=time.monotonic()-start,output=v.stdout+v.stderr))
 if v.returncode:break
r['status']='pass' if hashes()==r['source_sha256'] and all(x['returncode']==0 for x in r['commands']) else 'failed'
(out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(r['status'],flush=True)
raise SystemExit(r['status']!='pass')

"""Build the scoped production-core UART circular-DMA test ROM; no CI."""
from pathlib import Path
import hashlib,json,subprocess,time
ROOT=Path(__file__).resolve().parents[2]
out=ROOT/'build/t40/firmware';out.mkdir(parents=True,exist_ok=True)
sources=[ROOT/p for p in ['dv/soc/dma_circular.c','dv/soc/dma_circular_start.S',
 'dv/soc/prepare_dma_circular.py','sw/hal/dma_ring.h','build/t23/dma/dma_regs.h','build/t20/map/soc.h','tools/env/lock.json']]
r=dict(status='running',source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},commands=[])
(out/'boot.ld').write_text('ENTRY(_start)\nSECTIONS { . = 0x80; .text : { *(.start) *(.text*) *(.rodata*) } }\n')
for cmd in [
 ['riscv64-unknown-elf-gcc','-march=rv32im','-mabi=ilp32','-msmall-data-limit=0','-nostdlib','-ffreestanding','-Os','-Wall','-Wextra','-Werror','-Isw/hal','-Ibuild/t23/dma','-Ibuild/t20/map','-Wl,--no-relax','-Wl,-T,'+str(out/'boot.ld'),'dv/soc/dma_circular_start.S','dv/soc/dma_circular.c','-o',str(out/'boot.elf')],
 ['riscv64-unknown-elf-objcopy','-O','binary',str(out/'boot.elf'),str(out/'boot.bin')]]:
 start=time.monotonic();subprocess.run(cmd,cwd=ROOT,check=True);r['commands'].append(dict(command=cmd,seconds=time.monotonic()-start))
raw=bytes(128)+(out/'boot.bin').read_bytes();assert len(raw)<=65536
r['image_bytes']=len(raw);raw+=bytes(65536-len(raw))
(out/'boot.hex').write_text(''.join(f'{int.from_bytes(raw[i:i+4],"little"):08x}\n' for i in range(0,len(raw),4)))
r['rom_sha256']=hashlib.sha256((out/'boot.hex').read_bytes()).hexdigest();r['status']='prepared_not_executed'
(out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print('PREPARED',r['image_bytes'])

"""Prepare existing functional profiles plus the limited output mux; no CI."""
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
def main():
    for args in ([sys.executable,'dv/soc/prepare_dma.py'],
                 [sys.executable,'hw/regmap/regmap.py','hw/ip/pinmux/pinmux.regmap.yaml','--out','build/t24/pinmux']):
        subprocess.run(args,cwd=ROOT,check=True)
    out=ROOT/'build/t24/firmware';out.mkdir(parents=True,exist_ok=True)
    linker=out/'boot.ld';linker.write_text('ENTRY(_start)\nSECTIONS { . = 0x80; .text : { *(.start) } }\n')
    subprocess.run(['riscv64-unknown-elf-gcc','-march=rv32i','-mabi=ilp32','-nostdlib','-Wl,--no-relax',
        '-Wl,-T,'+str(linker),'dv/soc/pinmux_reset.S','-o',str(out/'boot.elf')],cwd=ROOT,check=True)
    subprocess.run(['riscv64-unknown-elf-objcopy','-O','binary',str(out/'boot.elf'),str(out/'boot.bin')],cwd=ROOT,check=True)
    raw=bytes(128)+(out/'boot.bin').read_bytes()
    assert len(raw)<=65536
    raw+=bytes(65536-len(raw))
    (out/'boot.hex').write_text(''.join(f'{int.from_bytes(raw[i:i+4],"little"):08x}\n' for i in range(0,len(raw),4)))
if __name__=='__main__':main()

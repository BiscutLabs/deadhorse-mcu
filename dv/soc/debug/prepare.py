"""Prepare the minimal performance-owned debug fixture boot; no production ROM claim."""
from pathlib import Path
import subprocess

def main():
    out=Path('build/plan05/debug-firmware');out.mkdir(parents=True,exist_ok=True)
    ld=out/'boot.ld';ld.write_text('ENTRY(_start)\nSECTIONS { . = 0x80; .text : { *(.start) } }\n')
    subprocess.run(['riscv64-unknown-elf-gcc','-march=rv32i_zicsr','-mabi=ilp32','-nostdlib','-Wl,--no-relax','-Wl,-T,'+str(ld),'dv/soc/debug/boot.S','-o',str(out/'boot.elf')],check=True)
    subprocess.run(['riscv64-unknown-elf-objcopy','-O','binary',str(out/'boot.elf'),str(out/'boot.bin')],check=True)
    raw=bytes(128)+(out/'boot.bin').read_bytes();assert len(raw)<=65536
    raw+=bytes(65536-len(raw))
    (out/'boot.hex').write_text(''.join(f'{int.from_bytes(raw[i:i+4],"little"):08x}\n' for i in range(0,len(raw),4)))
if __name__=='__main__':main()

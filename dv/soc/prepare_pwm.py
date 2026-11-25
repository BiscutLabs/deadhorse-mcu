"""Prepare generic PWM registers and focused core-reset ROM; no CI."""
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]

def main():
    def run(args):subprocess.run(args,cwd=ROOT,check=True)
    run([sys.executable,'dv/soc/prepare_io.py'])
    out=ROOT/'build/t22/firmware';out.mkdir(parents=True,exist_ok=True)
    linker=out/'boot.ld';linker.write_text('ENTRY(_start)\nSECTIONS { . = 0x80; .text : { *(.start) } }\n')
    run(['riscv64-unknown-elf-gcc','-march=rv32i','-mabi=ilp32','-nostdlib','-Wl,--no-relax',
         '-Wl,-T,'+str(linker),'dv/soc/pwm_reset.S','-o',str(out/'boot.elf')])
    run(['riscv64-unknown-elf-objcopy','-O','binary',str(out/'boot.elf'),str(out/'boot.bin')])
    raw=bytes(128)+(out/'boot.bin').read_bytes()
    assert len(raw)<=65536
    raw+=bytes(65536-len(raw))
    (out/'boot.hex').write_text(''.join(f'{int.from_bytes(raw[i:i+4],"little"):08x}\n' for i in range(0,len(raw),4)))

if __name__=='__main__':main()

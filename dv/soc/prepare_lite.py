"""Prepare the opt-in recovery-loaded RV32E profile; no CI."""
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]

def main():
    subprocess.run([sys.executable,'dv/soc/prepare_pinmux.py'],cwd=ROOT,check=True)
    out=ROOT/'build/t25/firmware';out.mkdir(parents=True,exist_ok=True)
    linker=out/'lite.ld'
    linker.write_text('ENTRY(_start)\nSECTIONS { . = 0x30000000; .text : { *(.start) } }\n')
    subprocess.run(['riscv64-unknown-elf-gcc','-march=rv32e_zicsr','-mabi=ilp32e','-nostdlib','-Wl,--no-relax',
        '-Wl,-T,'+str(linker),'dv/soc/lite_recovery.S','-o',str(out/'lite.elf')],cwd=ROOT,check=True)
    subprocess.run(['riscv64-unknown-elf-objcopy','-O','binary',str(out/'lite.elf'),str(out/'lite.bin')],cwd=ROOT,check=True)
    raw=(out/'lite.bin').read_bytes()
    assert 16<len(raw)<=2048 and len(raw)%4==0
    (out/'lite.hex').write_text(''.join(f'{int.from_bytes(raw[i:i+4],"little"):08x}\n' for i in range(0,len(raw),4)))
    print('PASS global RV32E recovery image, entry offset 16')
if __name__=='__main__':main()

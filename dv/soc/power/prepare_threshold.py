"""Real lite firmware for production threshold/reason integration tests."""
from pathlib import Path
import subprocess

def main():
    out=Path('build/t33/threshold-firmware');out.mkdir(parents=True,exist_ok=True)
    source=Path('dv/soc/power/threshold_lite.S')
    linker=out/'lite.ld'
    linker.write_text('ENTRY(_start)\nSECTIONS { . = 0x30000000; .text : { *(.start) } }\n')
    for name,flags in [('lite',[]),('lite-bad-key',['-DWRONG_KEY'])]:
        subprocess.run(['riscv64-unknown-elf-gcc','-march=rv32e_zicsr','-mabi=ilp32e',
            '-nostdlib','-Wl,--no-relax',*flags,'-Wl,-T,'+str(linker),str(source),'-o',str(out/(name+'.elf'))],check=True)
        subprocess.run(['riscv64-unknown-elf-objcopy','-O','binary',str(out/(name+'.elf')),str(out/(name+'.bin'))],check=True)
        raw=(out/(name+'.bin')).read_bytes()
        assert len(raw)%4==0 and 16<len(raw)<=2048
        (out/(name+'.hex')).write_text(''.join(f'{int.from_bytes(raw[i:i+4],"little"):08x}\n' for i in range(0,len(raw),4)))
    linker=out/'boot.ld';linker.write_text('ENTRY(_start)\nSECTIONS { . = 0x80; .text : { *(.start) } }\n')
    subprocess.run(['riscv64-unknown-elf-gcc','-march=rv32i_zicsr','-mabi=ilp32',
        '-nostdlib','-Wl,--no-relax','-Wl,-T,'+str(linker),'dv/soc/power/threshold_boot.S','-o',str(out/'boot.elf')],check=True)
    subprocess.run(['riscv64-unknown-elf-objcopy','-O','binary',str(out/'boot.elf'),str(out/'boot.bin')],check=True)
    raw=bytes(128)+(out/'boot.bin').read_bytes();assert len(raw)<=65536
    raw+=bytes(65536-len(raw))
    (out/'boot.hex').write_text(''.join(f'{int.from_bytes(raw[i:i+4],"little"):08x}\n' for i in range(0,len(raw),4)))
    print('PASS production threshold firmware prepared')

if __name__=='__main__':main()

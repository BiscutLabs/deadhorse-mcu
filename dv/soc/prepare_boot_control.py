"""Prepare performance-first lite-loading diagnostic images; no CI."""
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]

def main():
    def run(args):subprocess.run(args,cwd=ROOT,check=True)
    run([sys.executable,'dv/soc/prepare_watchdog.py'])
    run([sys.executable,'hw/regmap/regmap.py','hw/ip/boot_control/boot_control.regmap.yaml','--out','build/t28/boot_control'])
    out=ROOT/'build/t28/firmware';out.mkdir(parents=True,exist_ok=True)
    for name,arch,abi,base in [('lite','rv32e_zicsr','ilp32e',0x30000000),('boot','rv32i','ilp32',0x80)]:
        linker=out/(name+'.ld')
        linker.write_text(f'ENTRY(_start)\nSECTIONS {{ . = {base}; .text : {{ *(.start) }} }}\n')
        run(['riscv64-unknown-elf-gcc','-march='+arch,'-mabi='+abi,'-nostdlib','-Wl,--no-relax',
             '-Wl,-T,'+str(linker),f'dv/soc/boot_release_{name}.S','-o',str(out/(name+'.elf'))])
        run(['riscv64-unknown-elf-objcopy','-O','binary',str(out/(name+'.elf')),str(out/(name+'.bin'))])
        raw=(out/(name+'.bin')).read_bytes()
        assert len(raw)%4==0 and 16<len(raw)<=(1024 if name=="lite" else 65536-128)
        if name=='boot':raw=bytes(128)+raw;raw+=bytes(65536-len(raw))
        (out/(name+'.hex')).write_text(''.join(f'{int.from_bytes(raw[i:i+4],"little"):08x}\n' for i in range(0,len(raw),4)))
    print('PASS performance-first release firmware prepared')
if __name__=='__main__':main()

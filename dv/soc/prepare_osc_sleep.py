"""Production performance-owned sleep setup; lite handles only AON timer/mail/watchdog."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[2]
def main():
    out=ROOT/'build/plan04/sleep-firmware';out.mkdir(parents=True,exist_ok=True)
    variants=[('lite-helper','lite',[]),('boot','boot',['-DIDLE_ONLY']),('boot-lite','boot',[]),
        ('boot-lite-extra','boot',['-DEXTRA_WAKE']),('boot-lite-reset','boot',['-DLITE_WD_RESET']),
        ('boot-lite-gpio','boot',['-DGPIO_WAKE','-DHOST_WAKE=2']),
        ('boot-lite-jtag','boot',['-DHOST_WAKE=128']),('boot-lite-usb','boot',['-DUSB_WAKE','-DHOST_WAKE=32'])]
    for name,source,flags in variants:
        lite=source=='lite';base=0x30000000 if lite else 0x80
        linker=out/(name+'.ld');linker.write_text(f'ENTRY(_start)\nSECTIONS {{ . = {base}; .text : {{ *(.start) }} }}\n')
        subprocess.run(['riscv64-unknown-elf-gcc','-march='+('rv32e_zicsr' if lite else 'rv32i_zicsr'),
            '-mabi='+('ilp32e' if lite else 'ilp32'),'-nostdlib','-Wl,--no-relax',*flags,'-Wl,-T,'+str(linker),
            str(ROOT/f'dv/soc/osc_sleep_{source}.S'),'-o',str(out/(name+'.elf'))],cwd=ROOT,check=True)
        subprocess.run(['riscv64-unknown-elf-objcopy','-O','binary',str(out/(name+'.elf')),str(out/(name+'.bin'))],check=True)
        raw=(out/(name+'.bin')).read_bytes();assert len(raw)%4==0 and 16<len(raw)<=(1024 if lite else 2048)
        if not lite:raw=bytes(128)+raw;raw+=bytes(65536-len(raw))
        (out/(name+'.hex')).write_text(''.join(f'{int.from_bytes(raw[i:i+4],"little"):08x}\n' for i in range(0,len(raw),4)))
    print('PASS production oscillator sleep firmware prepared')
if __name__=='__main__':main()

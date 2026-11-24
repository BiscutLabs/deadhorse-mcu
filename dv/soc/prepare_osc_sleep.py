"""PLAN04 production loader/WFI sleep firmware; no RTL or register substitution."""
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]


def main():
    out=ROOT/'build/plan04/sleep-firmware';out.mkdir(parents=True,exist_ok=True)
    for name,arch,abi,base in [('lite','rv32e_zicsr','ilp32e',0x30000000),
            ('lite-extra','rv32e_zicsr','ilp32e',0x30000000),
            ('lite-reset','rv32e_zicsr','ilp32e',0x30000000),
            ('lite-gpio','rv32e_zicsr','ilp32e',0x30000000),
            ('lite-jtag','rv32e_zicsr','ilp32e',0x30000000),
            ('lite-usb','rv32e_zicsr','ilp32e',0x30000000),
            ('lite-flight-base','rv32e_zicsr','ilp32e',0x30000000),
            ('lite-flight-wake','rv32e_zicsr','ilp32e',0x30000000),
            ('boot','rv32i_zicsr','ilp32',0x80),('boot-gpio','rv32i_zicsr','ilp32',0x80),
            ('boot-usb','rv32i_zicsr','ilp32',0x80)]:
        linker=out/(name+'.ld')
        linker.write_text(f'ENTRY(_start)\nSECTIONS {{ . = {base}; .text : {{ *(.start) }} }}\n')
        source=name.split('-')[0]
        defines={'lite-reset':['-DLITE_WD_RESET'],'lite-extra':['-DEXTRA_WAKE'],'lite-gpio':['-DHOST_WAKE=2'],
            'lite-jtag':['-DHOST_WAKE=128'],'lite-usb':['-DHOST_WAKE=32'],
            'lite-flight-base':['-DSKIP_SLEEP'],'lite-flight-wake':['-DHOST_WAKE=4'],
            'boot-gpio':['-DGPIO_WAKE'],'boot-usb':['-DUSB_WAKE']}.get(name,[])
        subprocess.run(['riscv64-unknown-elf-gcc','-march='+arch,'-mabi='+abi,'-nostdlib','-Wl,--no-relax',
            *defines,'-Wl,-T,'+str(linker),str(ROOT/f'dv/soc/osc_sleep_{source}.S'),'-o',str(out/(name+'.elf'))],check=True)
        subprocess.run(['riscv64-unknown-elf-objcopy','-O','binary',str(out/(name+'.elf')),str(out/(name+'.bin'))],check=True)
        raw=(out/(name+'.bin')).read_bytes()
        assert len(raw)%4==0 and 16<len(raw)<=2048
        if source=='boot':raw=bytes(128)+raw;raw+=bytes(65536-len(raw))
        (out/(name+'.hex')).write_text(''.join(f'{int.from_bytes(raw[i:i+4],"little"):08x}\n' for i in range(0,len(raw),4)))
    print('PASS production oscillator sleep firmware prepared')


if __name__=='__main__':main()

"""Build the optional combined register map from two validated canonical maps."""
import copy
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import yaml
from hw.regmap.regmap import UniqueLoader,validate,emit

def description():
    base=yaml.load((ROOT/'hw/ip/qspi/qspi.regmap.yaml').read_text(),Loader=UniqueLoader)
    extra=yaml.load((ROOT/'hw/ip/qspi_xip/qspi_xip.regmap.yaml').read_text(),Loader=UniqueLoader)
    validate(base,'qspi');validate(extra,'qspi_xip')
    assert base['address_width']==extra['address_width'] and base['data_width']==extra['data_width']
    merged=copy.deepcopy(base);merged['registers']+=extra['registers']
    result=validate(merged,'qspi')
    assert result['registers'][:len(validate(base)['registers'])]==validate(base)['registers']
    return result

def firmware():
    out=ROOT/'build/t30/firmware';out.mkdir(parents=True,exist_ok=True)
    for name,arch,abi,base in [('boot','rv32i','ilp32',0x80),('flash','rv32i','ilp32',0x10000000)]:
        linker=out/(name+'.ld')
        linker.write_text(f'ENTRY(_start)\nSECTIONS {{ . = {base}; .text : {{ *(.start) }} }}\n')
        subprocess.run(['riscv64-unknown-elf-gcc','-march='+arch,'-mabi='+abi,'-nostdlib','-Wl,--no-relax',
            '-Wl,-T,'+str(linker),f'dv/soc/xip_{name}.S','-o',str(out/(name+'.elf'))],cwd=ROOT,check=True)
        subprocess.run(['riscv64-unknown-elf-objcopy','-O','binary',str(out/(name+'.elf')),str(out/(name+'.bin'))],check=True)
        raw=(out/(name+'.bin')).read_bytes()
        assert len(raw)%4==0 and 16<len(raw)<=2048
        if name=='boot':raw=bytes(128)+raw;raw+=bytes(65536-len(raw))
        (out/(name+'.hex')).write_text(''.join(f'{int.from_bytes(raw[i:i+4],"little"):08x}\n' for i in range(0,len(raw),4)))

if __name__=='__main__':
    subprocess.run([sys.executable,'dv/soc/prepare_qspi.py'],cwd=ROOT,check=True)
    emit(description(),ROOT/'build/t30/qspi')
    firmware()
    print('PASS validated T29 map plus disjoint XIP registers')

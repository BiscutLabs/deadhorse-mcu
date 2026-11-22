"""Explicit QEMU-map verification configuration of the real I0 SoC path."""
import hashlib
import json
import re
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'dv/core'))
sys.path.insert(0,str(ROOT/'hw/top/reference'))
from common import run, output_dir, inputs
import check_soc_map as mapping
from hw.regmap.regmap import load, emit

RAM=0x80000000
CAPACITY=0x4000
ROM=0x80010000
ENTRY=ROM+0x80


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bootstrap(destination):
    displacement=destination-ENTRY
    if displacement%2 or not -(1<<20)<=displacement<(1<<20): raise ValueError('Bootstrap displacement')
    return (((displacement>>20)&1)<<31 | ((displacement>>1)&1023)<<21 |
            ((displacement>>11)&1)<<20 | ((displacement>>12)&255)<<12 | 0x6f).to_bytes(4,'little')


def write_images(directory, workload, entry):
    if len(workload)>CAPACITY: raise ValueError('Workload exceeds physical modeled SRAM')
    ram=workload+bytes(CAPACITY-len(workload))
    rom=bytearray(0x10000); rom[0x80:0x84]=bootstrap(entry)
    def hexfile(path,words): path.write_text(''.join(f'{int.from_bytes(w,"little"):08x}\n' for w in words))
    hexfile(directory/'rom.hex',(rom[i:i+4] for i in range(0,len(rom),4)))
    for bank in range(4):
        hexfile(directory/f'ram{bank}.hex',(ram[i:i+4] for i in range(bank*4,len(ram),16)))
    # QEMU image explicitly includes the gap and distinct ROM bootstrap.
    image=ram+bytes(ENTRY-RAM-len(ram))+bootstrap(entry)
    (directory/'qemu.bin').write_bytes(image)
    return directory/'qemu.bin'


def prepare(directory):
    directory=output_dir(directory)
    config=mapping.yaml.load((ROOT/'hw/top/reference/soc.yaml').read_text(),Loader=mapping.UniqueLoader)
    for region in config['regions']:
        if region['name']=='boot_rom': region['base']=ROM
        if region['name']=='performance_sram': region['base']=RAM
    model=mapping.validate(config)
    mapping.emit(model,directory)
    emit(load(ROOT/'hw/ip/uart/uart.regmap.yaml'),directory)
    write_images(directory,b'',RAM)
    return directory


def compile_sim(directory, images):
    directory=output_dir(directory)
    inputs() # Authenticate the unchanged generic gate model.
    emitted=directory/'emit'
    run([sys.executable,'tools/sbt.py',f'hw/runMain deadhorse.top.EmitSocFixture {images} {emitted}'],directory,'emit')
    sources=sorted(emitted.glob('*.sv'))
    gate=ROOT/'hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv'
    # The pinned firtool guards file initialization separately from randomization.
    run(['verilator','--cc','--exe','--build','--assert','-DENABLE_INITIAL_MEM_',
         '-DENABLE_INITIAL_REG_','-j','4','-Wno-fatal',
         '--top-module','SocMinimalI0','--Mdir',directory/'obj',*sources,gate,ROOT/'dv/soc/sim_main.cpp'],directory,'compile')
    return directory/'obj/VSocMinimalI0'


def allocated_sections(elf,directory,stack_bytes=0):
    text=run(['riscv64-unknown-elf-objdump','-h',elf],directory,'sections').stdout
    lines=text.splitlines(); sections=[]
    for index,line in enumerate(lines):
        match=re.match(r'\s*\d+\s+(\S+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)',line)
        if match and index+1<len(lines) and 'ALLOC' in lines[index+1]:
            name,size,address,lma=match.groups(); size=int(size,16); address=int(address,16); lma=int(lma,16)
            if address!=lma or address<RAM or address+size>RAM+CAPACITY-stack_bytes:
                raise ValueError(f'Allocated section does not fit SRAM/stack reservation: {name}')
            sections.append(dict(name=name,address=address,size=size))
    if not sections: raise ValueError('No allocated ELF sections')
    return sections


def build_flight(directory,floating):
    directory=output_dir(directory); source=ROOT/'sw/flight/loop-measurement'
    run([sys.executable,'-I',source/'scenario/gen_scenario.py',directory/'scenario.c','40'],directory,'scenario')
    run([sys.executable,'-I',source/'scenario/gen_params.py',directory/'params_gen.inc'],directory,'parameters')
    startup=source/'src/crt0.S'
    if floating:
        startup=directory/'crt0.S'
        startup.write_text('.section .text.start,"ax"\n.global _start\n.option norelax\n_start:\n'+
            'li t0,0x2000\ncsrw mstatus,t0\n'+
            '\n'.join(f'fmv.w.x f{i},zero' for i in range(32))+'\nla sp,_stack_top\ncall main\nj .\n')
    flags=['-std=gnu11','-march=rv32imfc_zicsr' if floating else '-march=rv32im',
           '-mabi=ilp32f' if floating else '-mabi=ilp32','-O2',*(['-DNUM_FLOAT'] if floating else []),
           '-ffreestanding','-nostdlib','-ffunction-sections','-fdata-sections',
           '-I'+str(source/'src'),'-I'+str(directory),'-DNITER_RUN=40','-DPLAT_QEMU']
    sources=[startup,*[source/'src'/f'{name}.c' for name in ('harness','control_step','control_init')],directory/'scenario.c']
    objects=[]
    for path in sources:
        obj=directory/(path.stem+'.o'); objects.append(obj)
        run(['riscv64-unknown-elf-gcc',*flags,'-c',path,'-o',obj],directory,'compile-'+path.stem)
    linker=directory/'link.ld'
    linker.write_text((source/'src/link.ld').read_text().replace('0x80000000 + 0x300000','0x80000000 + 0x4000'))
    elf=directory/'program.elf'; raw=directory/'workload.bin'
    linkflags=flags if floating else ['-march=rv32im','-mabi=ilp32','-nostdlib']
    run(['riscv64-unknown-elf-gcc',*linkflags,'-Wl,--gc-sections','-Wl,--no-warn-rwx-segments',
         '-T',linker,'-o',elf,*objects,'-lgcc'],directory,'link')
    run(['riscv64-unknown-elf-objcopy','-O','binary',elf,raw],directory,'binary')
    sections=allocated_sections(elf,directory,2048)
    return elf,raw.read_bytes(),sections

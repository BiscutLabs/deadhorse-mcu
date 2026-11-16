"""RV32IMFC architectural, reproducible mixed, and hard-float flight fixtures."""
import hashlib
import json
import random
import sys

from common import ROOT, output_dir, run
from candidate import manifest
from lockstep import BASE, compile_sim, qemu_trace
from float_compare import compare, negative_controls,interrupt_reentry
from suites import arch_programs, flight_reentry

PROBE='csrr x28,fcsr'
FINISH='li x30,0x100000\nli x31,0x5555\nsw x31,0(x30)\nj .\n'
VALUES=(0,0x80000000,0x3f800000,0xc0000000,0x00000001,0x007fffff,
        0x00800000,0x7f7fffff,0x7f800000,0xff800000,0x7fc12345,0x7f800001,
        0x33800000,0x4f000000,0xcf000001,0x3f800001)


def preamble():
    code=['.section .text.start','.global _start','.option norvc','.option norelax','_start:']
    code += [f'li x{i},0' for i in range(1,32)]
    code += ['li x1,0x2000','csrw mstatus,x1']
    for index in range(32):
        code += [f'li x1,0x{VALUES[index%len(VALUES)]:08x}',f'fmv.w.x f{index},x1',PROBE]
    code += ['la sp,buffer','mv x8,sp','li x5,17','li x6,-9']
    return code


def build(directory,lines,handler=''):
    directory=output_dir(directory)
    source=directory/'program.S'; elf=directory/'program.elf'; binary=directory/'program.bin'
    source.write_text('\n'.join(lines)+'\n'+FINISH+handler+'\n.section .data\n.balign 16\nbuffer: .zero 128\n')
    run(['riscv64-unknown-elf-gcc','-march=rv32imfc_zicsr','-mabi=ilp32f','-nostdlib',
         '-Wl,--no-relax','-T','dv/core/arch/link.ld',source,'-o',elf],directory,'compile')
    run(['riscv64-unknown-elf-objcopy','-O','binary',elf,binary],directory,'binary')
    return directory,elf,binary,BASE,[],True


def instructions(a=2,b=3,c=12,d=0,rm='rne'):
    return [f'{op}.s f{d},f{a},f{b},{rm}' for op in ('fadd','fsub','fmul','fdiv')]+[
        f'fsqrt.s f{d},f{a},{rm}']+[
        f'{op}.s f{d},f{a},f{b},f{c},{rm}' for op in ('fmadd','fmsub','fnmsub','fnmadd')]+[
        f'{op}.s f{d},f{a},f{b}' for op in ('fmin','fmax','fsgnj','fsgnjn','fsgnjx')]+[
        f'{op}.s x7,f{a},f{b}' for op in ('feq','flt','fle')]+[
        f'fclass.s x7,f{a}',f'fmv.x.w x7,f{a}',f'fmv.w.x f{d},x5',
        f'fcvt.w.s x7,f{a},{rm}',f'fcvt.wu.s x7,f{a},{rm}',
        f'fcvt.s.w f{d},x6,{rm}',f'fcvt.s.wu f{d},x6,{rm}']


def floating_arch(output):
    for mode,rm in enumerate(('rne','rtz','rdn','rup','rmm','dyn')):
        code=preamble()+[f'csrwi frm,{mode%5}',PROBE]
        for index in range(len(VALUES)):
            for instruction in instructions(index,(index+3)%16,(index+7)%16,16+index%16,rm):
                code += [instruction,PROBE]
        # Raw-bit load/store including all compressed forms and writable f0.
        code += ['fsw f17,0(sp)','flw f0,0(sp)','.option rvc',
                 'c.fswsp f0,4(sp)','c.flwsp f0,4(sp)',
                 'c.flw f8,0(x8)','c.fsw f8,8(x8)','.option norvc',
                 'csrwi fflags,31',PROBE,'csrci fflags,9',PROBE,
                 'csrrsi x7,frm,1',PROBE,'csrrci x7,fcsr,3',PROBE]
        yield build(output/rm,code)


def mixed(output):
    for seed in (0xDEAD1301,0xDEAD1302):
        rng=random.Random(seed); code=preamble()
        code += ['la x29,trap_vector','ori x29,x29,1','csrw mtvec,x29',
                 'csrsi mie,8','csrsi mstatus,8','li x26,0x02000000','li x27,1']
        for n in range(180):
            a,b,c,d=[rng.randrange(32) for _ in range(4)]
            rm=rng.choice(('rne','rtz','rdn','rup','rmm','dyn'))
            code += [rng.choice(instructions(a,b,c,d,rm)),PROBE]
            code += [rng.choice(('add x9,x5,x6','xor x5,x5,x6','mul x9,x5,x6',
                                  'div x9,x5,x6','rem x9,x5,x6','addi x6,x6,1'))]
            if n%7==0:
                code += [f'fsw f{d},12(sp)',f'flw f{a},12(sp)',
                         f'csrwi frm,{rng.randrange(5)}',PROBE]
            if n%60==30: code += ['sw x27,0(x26)']
        directory=output/f'seed-{seed:08x}'
        handler='\n.section .text.irq,"ax"\n.balign 256\ntrap_vector:\n.space 12\nsw x0,0(x26)\ncsrr x24,mcause\ncsrr x25,mepc\nmret\n'
        program=build(directory,code,handler)
        (directory/'seed.json').write_text(json.dumps(dict(seed=seed,instructions=180))+'\n')
        yield program


def flight(output):
    """Compile original T02 C/scenario sources using actual hardware F operations."""
    directory=output_dir(output/'T02-hard-float'); source=ROOT/'sw/flight/loop-measurement'
    run([sys.executable,'-I',source/'scenario/gen_scenario.py',directory/'scenario.c','40'],directory,'scenario')
    run([sys.executable,'-I',source/'scenario/gen_params.py',directory/'params_gen.inc'],directory,'parameters')
    # Startup enables F and defines all FP payloads before entering unchanged C.
    startup=directory/'crt0.S'
    startup.write_text('.section .text.start,"ax"\n.global _start\n.option norelax\n_start:\n'+
        'li t0,0x2000\ncsrw mstatus,t0\n'+
        '\n'.join(f'fmv.w.x f{i},zero' for i in range(32))+\
        '\nla sp,_stack_top\ncall main\nj .\n')
    flags=['-std=gnu11','-march=rv32imfc_zicsr','-mabi=ilp32f','-O2','-DNUM_FLOAT',
           '-ffreestanding','-nostdlib','-ffunction-sections','-fdata-sections',
           '-I'+str(source/'src'),'-I'+str(directory),'-DNITER_RUN=40','-DPLAT_QEMU']
    sources=[startup,*[source/'src'/f'{name}.c' for name in ('harness','control_step','control_init')],directory/'scenario.c']
    objects=[]
    for path in sources:
        obj=directory/(path.stem+'.o'); objects.append(obj)
        run(['riscv64-unknown-elf-gcc',*flags,'-c',path,'-o',obj],directory,'compile-'+path.stem)
    elf=directory/'program.elf'; raw=directory/'workload.bin'
    run(['riscv64-unknown-elf-gcc',*flags,'-Wl,--gc-sections','-Wl,--no-warn-rwx-segments',
         '-T',source/'src/link.ld','-o',elf,*objects,'-lgcc'],directory,'link')
    run(['riscv64-unknown-elf-objcopy','-O','binary',elf,raw],directory,'binary')
    base,entry=0x80000000,0x80010080
    displacement=base-entry
    jump=(((displacement>>20)&1)<<31 | ((displacement>>1)&1023)<<21 |
          ((displacement>>11)&1)<<20 | ((displacement>>12)&255)<<12 | 0x6f)
    workload=raw.read_bytes()
    if len(workload)>entry-base: raise ValueError('Hard-float workload overlaps bootstrap')
    image=bytearray(entry-base+4); image[:len(workload)]=workload; image[-4:]=jump.to_bytes(4,'little')
    binary=directory/'program.bin'; binary.write_bytes(image)
    (directory/'sources.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                                                  for p in sources},indent=2)+'\n')
    yield directory,elf,binary,base,['flight'],False


def run_suites(candidate,selected,output):
    if not candidate or (manifest(candidate) or {}).get('implementation')!='rv32imfc-v1':
        raise ValueError('F lockstep requires the authenticated F candidate')
    names=selected.split(',')
    if len(set(names))!=len(names) or set(names)-{'arch','random','flight-float'}:
        raise ValueError('F suites must be arch,random,flight-float')
    sim=compile_sim(output/'candidate',candidate); results={}; faults={}
    for suite in names:
        if suite=='arch':
            programs=iter([*[(d,e,b,base,flags,False) for d,e,b,base,flags in arch_programs(output/'integer')],
                           *floating_arch(output/'floating')])
        else: programs=mixed(output/'random') if suite=='random' else flight(output/'flight')
        results[suite]=[]
        for directory,elf,binary,base,flags,probes in programs:
            run_result=run([sim,binary,*flags],directory,'candidate-run')
            rows=[json.loads(line) for line in run_result.stdout.splitlines() if line.startswith('{')]
            iss=qemu_trace(elf,directory,base,binary if flags else None,0x80010080 if flags else None,True)
            if suite=='random':
                iss,duplicates=interrupt_reentry(iss,binary.read_bytes(),base)
                (directory/'iss-reentry.json').write_text(json.dumps(duplicates,indent=2)+'\n')
            if flags:
                iss,duplicates=flight_reentry(iss,binary.read_bytes(),base,allow_compressed=True)
                (directory/'iss-reentry.json').write_text(json.dumps(duplicates,indent=2)+'\n')
            result=compare(rows,iss,binary.read_bytes(),base,probes)
            if suite=='random' and result['interrupts']!=3: raise ValueError('Missing seeded-stream interrupts')
            if not faults and probes:
                faults=negative_controls(rows,iss,binary.read_bytes(),base)
                (output/'negative-controls.json').write_text(json.dumps(faults,indent=2)+'\n')
            result.update(status='pass',name=directory.name)
            results[suite].append(result)
            (directory/'result.json').write_text(json.dumps(result,indent=2)+'\n')
            print(f'PASS F lockstep {suite}/{directory.name}: {result["retirements"]} retirements',flush=True)
    if any(not rows for rows in results.values()): raise ValueError('Empty F suite')
    receipt=dict(status='pass',isa='rv32imfc',suites=results,negative_controls=faults,
        coverage='QEMU integer/FP state, operands, destinations and memory at every retirement; '
                 'FCSR after each architectural/random FP operation; flight flags not independently observed',
        interrupts='three CLINT software interrupts per mixed stream; separate port-level timer/NMI/debug/reset tests')
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS selected F lockstep suites',flush=True)
    return 0

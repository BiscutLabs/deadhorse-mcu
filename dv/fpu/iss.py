"""Cross-check RISC-V-specific reference behavior against pinned QEMU."""
import json
from pathlib import Path
import subprocess
from vectors import ROOT, run

MNEMONICS=['fadd.s f3,f0,f1','fsub.s f3,f0,f1','fmul.s f3,f0,f1',
           'fmadd.s f3,f0,f1,f2','fmsub.s f3,f0,f1,f2',
           'fnmsub.s f3,f0,f1,f2','fnmadd.s f3,f0,f1,f2',
           'fdiv.s f3,f0,f1','fsqrt.s f3,f0','fmin.s f3,f0,f1',
           'fmax.s f3,f0,f1','feq.s a0,f0,f1','flt.s a0,f0,f1','fle.s a0,f0,f1',
           'fsgnj.s f3,f0,f1','fsgnjn.s f3,f0,f1','fsgnjx.s f3,f0,f1',
           'fclass.s a0,f0','fmv.x.w a0,f0','fmv.w.x f3,t0',
           'fcvt.w.s a0,f0','fcvt.wu.s a0,f0','fcvt.s.w f3,t0','fcvt.s.wu f3,t0']
INTEGER_RESULTS={11,12,13,17,18,20,21}

def check():
    out=ROOT/'build/t12/iss';out.mkdir(parents=True,exist_ok=True)
    pin=json.loads((ROOT/'dv/core/iss.json').read_text())
    version=run([pin['executable'],'--version'])
    package=run(['dpkg-query','-W','-f=${Version}',pin['package']]).strip()
    if pin['version'] not in version or package!=pin['package_version']:
        raise ValueError('QEMU does not match pinned simulator')
    corners=[0,0x80000000,0x7f800000,0xff800000,0x7fc12345,0xffc12345,
             0x7f800001,0xff800001,0xbe800000,0x4f800000]
    cases=[(op,rm,a,b,corners[(i+j)%len(corners)]) for op in range(24)
           for rm in range(5) for i,a in enumerate(corners) for j,b in enumerate(corners)]
    inputs=''.join(f'{o} {r} {a:08x} {b:08x} {c:08x}\n' for o,r,a,b,c in cases)
    expected=run([ROOT/'build/t12/oracle'],input=inputs).splitlines()
    code=['.option norvc','.option norelax','.section .text','.globl _start','_start:',
          'li t0,0x6000','csrs mstatus,t0']
    for op,rm,a,b,c in cases:
        code += [f'li t0,0x{a:08x}','fmv.w.x f0,t0',f'li t1,0x{b:08x}',
                 'fmv.w.x f1,t1',f'li t1,0x{c:08x}','fmv.w.x f2,t1',
                 f'li t1,{rm<<5}','csrw fcsr,t1',MNEMONICS[op]]
        if op not in INTEGER_RESULTS: code += ['fmv.x.w a0,f3']
        code += ['csrr s0,fflags','jal ra,hex','mv a0,s0','jal ra,hex',
                 'li t1,0x10000000','li t2,10','sb t2,0(t1)']
    code += ['li t1,0x100000','li t2,0x5555','sw t2,0(t1)','1: j 1b',
             'hex:','li t1,0x10000000','li t2,8','2:',
             'srli t3,a0,28','li t4,10','bltu t3,t4,3f','addi t3,t3,39',
             '3: addi t3,t3,48','sb t3,0(t1)','slli a0,a0,4',
             'addi t2,t2,-1','bnez t2,2b','ret']
    source=out/'special.S';source.write_text('\n'.join(code)+'\n')
    elf=out/'special.elf'
    run(['riscv64-unknown-elf-gcc','-march=rv32imafc_zicsr','-mabi=ilp32f',
         '-nostdlib','-Wl,-Ttext=0x80000000','-Wl,--entry=_start','-Wl,--no-relax',
         source,'-o',elf])
    result=subprocess.run([pin['executable'],'-machine','virt','-cpu','rv32',
                           '-bios','none','-nographic','-monitor','none','-kernel',str(elf)],
                          cwd=ROOT,capture_output=True,text=True,timeout=60)
    (out/'qemu.log').write_text(result.stdout+result.stderr)
    result.check_returncode()
    actual=result.stdout.splitlines()
    if len(actual)!=len(expected): raise ValueError('QEMU vector count mismatch')
    for i,(got,want) in enumerate(zip(actual,expected)):
        value,flags=(int(x,16) for x in want.split())
        if got!=f'{value:08x}{flags:08x}':
            raise ValueError(f'QEMU reference mismatch {cases[i]}: {got} != {want}')
    (out/'result.json').write_text(json.dumps(dict(status='pass',count=len(cases),
                                                 pin=pin),indent=2)+'\n')
    print(f'PASS QEMU RISC-V special values: {len(cases)} cases',flush=True)

if __name__=='__main__': check()

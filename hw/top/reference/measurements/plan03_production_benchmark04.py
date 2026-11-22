"""Production-map full-loop cycle measurement; workload evidence, not ISS lockstep."""
import copy,hashlib,importlib.util,json,re,shutil,subprocess,sys,time
from pathlib import Path
root=Path.cwd();sys.path[:0]=[str(root/'dv/soc'),str(root/'dv/core'),str(root)]
import fixture
spec=importlib.util.spec_from_file_location('metrics',root/'tools/spikes/s1_core/performance.py')
metrics=importlib.util.module_from_spec(spec);spec.loader.exec_module(metrics)
base=root/'build/plan03/production-performance04';base.mkdir(exist_ok=False)
source=root/'sw/flight/loop-measurement';ram=0x20000000;marker=ram+0x3800
def run(args,out,name,timeout=600):
    p=subprocess.run(list(map(str,args)),cwd=root,text=True,capture_output=True,timeout=timeout)
    (out/(name+'.log')).write_text(p.stdout+p.stderr)
    assert p.returncode==0,(name,p.returncode,(p.stdout+p.stderr)[-1500:])
    return p.stdout
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
artifacts={};started=time.monotonic()
for name,floating in [('fixed',False),('hard-float',True)]:
    out=base/name;out.mkdir();reference=out/'reference'
    # Existing reference build remains unchanged, including its QEMU-map markers.
    refelf,refbinary,refsections=fixture.build_flight(reference,floating)
    for file in ('scenario.c','scenario.h','params_gen.inc'):(out/file).write_bytes((reference/file).read_bytes())
    startup=reference/'crt0.S' if floating else source/'src/crt0.S'
    harness=out/'harness.c';harness.write_text((source/'src/harness.c').read_text().replace('0x10000000u','0x40012000u').replace('0x100000u','0x40012000u'))
    flags=['-std=gnu11','-march=rv32imfc_zicsr' if floating else '-march=rv32im','-mabi=ilp32f' if floating else '-mabi=ilp32','-O2',
      *(['-DNUM_FLOAT'] if floating else []),'-ffreestanding','-nostdlib','-ffunction-sections','-fdata-sections',
      '-I'+str(source/'src'),'-I'+str(out),'-DNITER_RUN=40','-DPLAT_QEMU']
    files=[startup,harness,source/'src/control_step.c',source/'src/control_init.c',out/'scenario.c'];objects=[]
    for p in files:
        obj=out/(p.stem+'.o');objects.append(obj);run(['riscv64-unknown-elf-gcc',*flags,'-c',p,'-o',obj],out,'compile-'+p.stem)
    for n in ('control_step.o','control_init.o','scenario.o'):
        assert (out/n).read_bytes()==(reference/n).read_bytes(),('Workload object changed',n)
    linker=out/'link.ld';linker.write_text((source/'src/link.ld').read_text().replace('0x80000000','0x20000000').replace('0x300000','0x4000'))
    elf=out/'program.elf';raw=out/'workload.bin'
    run(['riscv64-unknown-elf-gcc',*(flags if floating else ['-march=rv32im','-mabi=ilp32','-nostdlib']),
      '-Wl,--gc-sections','-Wl,--no-warn-rwx-segments','-T',linker,'-o',elf,*objects,'-lgcc'],out,'link')
    run(['riscv64-unknown-elf-objcopy','-O','binary',elf,raw],out,'binary')
    sections=run(['riscv64-unknown-elf-objdump','-h',elf],out,'sections').splitlines();allocated=[]
    for i,line in enumerate(sections[:-1]):
        match=re.match(r'\s*\d+\s+(\S+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)',line)
        if match and 'ALLOC' in sections[i+1]:
            n,size,addr,lma=match.groups();size=int(size,16);addr=int(addr,16)
            assert addr==int(lma,16) and ram<=addr and addr+size<=marker,(n,addr,size)
            allocated.append(dict(name=n,address=addr,size=size))
    assert allocated and marker==ram+0x4000-2048
    disasm=run(['riscv64-unknown-elf-objdump','-d','--disassemble=main',elf],out,'main-disassembly')
    bounds=metrics.historical.loop_boundaries(disasm)
    refdisasm=run(['riscv64-unknown-elf-objdump','-d','--disassemble=main',refelf],out,'reference-main-disassembly')
    refbounds=metrics.historical.loop_boundaries(refdisasm)
    def loop_listing(text,bounds):
        rows=[]
        for line in text.splitlines():
            m=re.match(r'\s*([0-9a-f]+):\s+([0-9a-f]+)\s+(.+)',line)
            if m and bounds['start']<=int(m[1],16)<=bounds['end']:
                rows.append(dict(pc=int(m[1],16),instruction=m[2],assembly=m[3]))
        assert rows;return rows
    candidate=loop_listing(disasm,bounds);old=loop_listing(refdisasm,refbounds)
    (out/'loop-comparison.json').write_text(json.dumps(dict(production=candidate,reference=old,
      identical_workload_objects=['control_step.o','control_init.o','scenario.o'],
      scope='Full main-loop window; relocation and marker-induced layout differences require review'),indent=2)+'\n')
    # Independent host execution of the same scenario; no RTL-derived oracle.
    host=out/'host'
    run(['gcc','-std=gnu11','-O2','-ffp-contract=off','-DHOST','-DNITER_RUN=40',*(['-DNUM_FLOAT'] if floating else []),
      '-I'+str(source/'src'),'-I'+str(out),source/'src/harness.c',source/'src/control_step.c',source/'src/control_init.c',out/'scenario.c','-lm','-o',host],out,'host-compile')
    checks=run([host],out,'host-checks');expected=[(int(a),int(b,16)) for a,b in re.findall(r'CHK (\d+) ([0-9a-fA-F]+)',checks)]
    assert len(expected)==3
    # ROM writes every SRAM word before the workload runs; no SRAM backdoor.
    payload=out/'payload.bin';payload.write_bytes(raw.read_bytes()+bytes(0x4000-len(raw.read_bytes())))
    bootstrap=out/'bootstrap.S';bootstrap.write_text('.section .text.start,"ax"\n.global _start\n.option norelax\n_start:\n'+
      'la t0,payload\nli t1,0x20000000\nli t2,0x20004000\n1: lw t3,0(t0)\nsw t3,0(t1)\naddi t0,t0,4\naddi t1,t1,4\nbne t1,t2,1b\nli t0,0x20000000\njr t0\n.balign 4\npayload:\n.incbin "'+str(payload)+'"\n')
    bootlink=out/'boot.ld';bootlink.write_text('ENTRY(_start)\nSECTIONS { . = 0x80; .text : { *(.text.start) } }\n')
    run(['riscv64-unknown-elf-gcc','-march=rv32i','-mabi=ilp32','-nostdlib','-Wl,--no-relax','-T',bootlink,bootstrap,'-o',out/'boot.elf'],out,'boot-compile')
    run(['riscv64-unknown-elf-objcopy','-O','binary',out/'boot.elf',out/'boot.bin'],out,'boot-binary')
    rom=bytes(128)+(out/'boot.bin').read_bytes();assert len(rom)<=65536;rom+=bytes(65536-len(rom))
    (out/'rom.hex').write_text(''.join(f'{int.from_bytes(rom[i:i+4],"little"):08x}\n' for i in range(0,len(rom),4)))
    artifacts[name]=dict(out=out,bounds=bounds,expected=expected,floating=floating,sections=allocated)
print('PASS workload preparation; compile and simulation next',flush=True)
(base/'prepared.json').write_text(json.dumps({n:{k:str(v) if isinstance(v,Path) else v for k,v in d.items()} for n,d in artifacts.items()},indent=2)+'\n')

"""Prepare actual ROM/paired-image inputs for the production pin-level peer."""
import argparse,hashlib,json,pathlib,subprocess,time
from image import bundle,flash,crc

ROOT=pathlib.Path.cwd();SRC=pathlib.Path(__file__).resolve().parent
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--rom',required=True)
 a=p.parse_args();out=ROOT/a.output;out.mkdir(parents=True,exist_ok=False);commands=[]
 def run(cmd,label):
  start=time.monotonic();r=subprocess.run(list(map(str,cmd)),capture_output=True,text=True)
  (out/(label+'.log')).write_text(r.stdout+r.stderr)
  commands.append(dict(command=list(map(str,cmd)),seconds=time.monotonic()-start,returncode=r.returncode))
  if r.returncode:raise RuntimeError(label)
 def program(name,text,lite=False,floating=False):
  source=out/(name+'.S');source.write_text(text)
  base=0x30000000 if lite else 0x20000000
  run(['riscv64-unknown-elf-gcc','-march=rv32e' if lite else '-march=rv32imfc_zicsr' if floating else '-march=rv32imc_zicsr',
   '-mabi=ilp32e' if lite else '-mabi=ilp32','-nostdlib','-Wl,--no-relax',
   '-Wl,-Ttext='+hex(base),'-Wl,-e,_start',source,'-o',out/(name+'.elf')],name+'-link')
  run(['riscv64-unknown-elf-objcopy','-O','binary',out/(name+'.elf'),out/(name+'.bin')],name+'-binary')
  data=(out/(name+'.bin')).read_bytes();return data+bytes((-len(data))%4)
 lite=program('lite','''.section .text
.global _start
.option norelax
_start:
li s0,0
li s1,0x40001000
li t1,0x57415443
send:
lw t0,12(s1)
andi t0,t0,1
beqz t0,send
sw t1,0(s1)
li t0,1
sw t0,4(s1)
receive:
lw t0,12(s1)
andi t0,t0,2
beqz t0,receive
lw t0,8(s1)
li t0,2
sw t0,4(s1)
addi s0,s0,1
mv t1,s0
j send
''',True)
 def perf(name,marker,held=False):
  wait='' if held else '''li t0,0x40001000
li t1,0x57415443
1: lw t2,12(t0)
andi t2,t2,2
beqz t2,1b
lw t2,8(t0)
bne t1,t2,1b
li t1,2
sw t1,4(t0)
'''
  return program(name,''' .section .text
.global _start
.option norelax
_start:
'''+wait+f'''li t0,0x40012000
li t1,{marker}
sw t1,0(t0)
2: wfi
j 2b
''')
 images={}
 for name,marker,held in [('a',0xa1,False),('b',0xb2,False),('golden',0xc3,False),('held',0xd4,True)]:
  images[name]=bundle(perf(name,marker,held),lite,b'CFG1',generation={'a':1,'b':2,'golden':0,'held':1}[name],start_lite=not held,lite_data=8,lite_stack=16)
 cases={'a':flash({1:images['a']}),'newest-b':flash({0:images['golden'],1:images['a'],2:images['b']}),
  'golden':flash({0:images['golden']}),'held':flash({1:images['held']}),
  'empty':flash({}),'strap':flash({1:images['a']})}
 core=program('core-smoke',""".section .text
.global _start
.option norelax
_start:
li t0,0x6000
csrs mstatus,t0
csrw fcsr,zero
li t0,0x3fc00000
fmv.w.x f0,t0
li t0,0x40100000
fmv.w.x f1,t0
fadd.s f2,f0,f1
fmv.x.w t0,f2
li t1,0x40700000
bne t0,t1,bad
fmul.s f3,f0,f1
fmv.x.w t0,f3
li t1,0x40580000
bne t0,t1,bad
csrr t0,fflags
bnez t0,bad
li t0,0x123
li t1,0x456
mul t2,t0,t1
li t3,0x4edc2
bne t2,t3,bad
divu t3,t2,t0
bne t3,t1,bad
li t0,0x40001000
1: lw t1,12(t0)
andi t1,t1,2
beqz t1,1b
lw t1,8(t0)
li t2,0x57415443
bne t1,t2,bad
li t1,0xa5
j publish
bad: li t1,0xee
publish:
li t0,0x40012000
sw t1,0(t0)
2: wfi
j 2b
""",floating=True)
 cases['core-smoke']=flash({1:bundle(core,lite,b'CFG1',generation=1,lite_data=8,lite_stack=16,perf_isa=0x40001124)})
 broken=bytearray(images['b']);broken[256]^=1
 cases['corrupt-newest']=flash({0:images['golden'],1:images['a'],2:broken})
 incomplete=bytearray(images['b']);incomplete[92:96]=b'\xff'*4
 cases['uncommitted']=flash({1:images['a'],2:incomplete})
 tie=bytearray(images['b']);tie[8:12]=(1).to_bytes(4,'little');tie[88:92]=crc(tie[:88]).to_bytes(4,'little')
 cases['tie-a']=flash({1:images['a'],2:tie})
 directory_fault=flash({1:images['a']});directory_fault[0]^=1;cases['bad-directory']=directory_fault
 for name,index,value in [('bad-range',4,14340),('bad-generation',2,0xffffffff),
                          ('bad-compatibility',17,2),('bad-extent',18,0xffffffff)]:
  malformed=bytearray(images['a']);malformed[4*index:4*index+4]=value.to_bytes(4,'little')
  malformed[88:92]=crc(malformed[:88]).to_bytes(4,'little');cases[name]=flash({1:malformed})
 watcher=ROOT/'sw/lite/watcher';objects=[]
 flags=['-march=rv32e_zicsr','-mabi=ilp32e','-Os','-ffreestanding','-fno-builtin',
  '-ffunction-sections','-fdata-sections','-fstack-usage','-fno-common','-msmall-data-limit=0','-Wall','-Wextra','-Werror']
 for name in ('start.S','watcher.c'):
  obj=out/('watcher-'+pathlib.Path(name).stem+'.o');objects.append(obj)
  run(['riscv64-unknown-elf-gcc',*flags,'-c',watcher/name,'-o',obj],'watcher-'+name)
 run(['riscv64-unknown-elf-gcc',*flags,'-nostdlib','-Wl,--no-relax','-Wl,--gc-sections',
  '-Wl,-T,'+str(watcher/'watcher.ld'),*objects,'-o',out/'watcher.elf'],'watcher-link')
 run(['riscv64-unknown-elf-objcopy','-O','binary',out/'watcher.elf',out/'watcher.bin'],'watcher-binary')
 watched=(out/'watcher.bin').read_bytes();assert 0<len(watched)<=1024 and len(watched)%4==0
 held_perf=(out/'held.bin').read_bytes();held_perf+=bytes((-len(held_perf))%4)
 # Non-executed copy fixtures: actual watcher bytes, with its measured 8-byte
 # data allocation and ABI-minimum conservative 16-byte stack reservation.
 # These cases measure loading only; the Phase2 dormant test executes watcher.
 for name,data in [('watcher-held',watched),('max-lite-held',watched+bytes(1024-len(watched)))]:
  cases[name]=flash({1:bundle(held_perf,data,b'CFG1',generation=1,start_lite=False,lite_data=8,lite_stack=16)})
 # T41 watchdog warm reset uses real MMIO. Both cores restart; ROM validates
 # both retained images before releasing lite, whose protocol counter restarts.
 for name in ('warm-match','warm-reload','warm-lite-reload','warm-bad-context','warm-bad-context-reset','warm-flash-missing','warm-flash-corrupt','warm-newer','warm-dma-drain','warm-dma-stall'):
  damage={'warm-lite-reload':'''li t0,0x40000300
li t1,0x484f4c44
sw t1,12(t0)
held_for_damage:
lw t1,0(t0)
andi t1,t1,1
beqz t1,held_for_damage
li t0,0x30000000
lw t1,0(t0)
xori t1,t1,1
sw t1,0(t0)
''','warm-match':'','warm-newer':'','warm-flash-missing':'','warm-dma-drain':'','warm-dma-stall':'','warm-reload':'''li t0,0x20000000
lw t1,0(t0)
xori t1,t1,1
sw t1,0(t0)
''','warm-flash-corrupt':'''li t0,0x20000000
lw t1,0(t0)
xori t1,t1,1
sw t1,0(t0)
''','warm-bad-context':'''li t0,0x20003900
sw zero,0(t0)
''','warm-bad-context-reset':'''li t0,0x20003900
sw zero,0(t0)
'''}[name]
  dma=''
  if name.startswith('warm-dma-'):
   dma='''li t0,0x20003000
li t1,0x20003040
li t2,0x55555555
fill_dma:
sw t2,0(t0)
addi t0,t0,4
bne t0,t1,fill_dma
li t0,0x40010000
li t1,944
sw t1,4(t0)
'''+f'''li t1,{2 if name.endswith('stall') else 1}
sw t1,0(t0)
li t1,1
sw t1,8(t0)
li t0,0x40011000
li t1,0x20003000
sw t1,32(t0)
li t1,64
sw t1,48(t0)
li t1,{1 if name.endswith('stall') else 0}
sw t1,64(t0)
li t1,1
sw t1,0(t0)
'''
  application=program(name,''' .section .text
.global _start
.option norelax
_start:
# Model application startup reinitializes data on every entry.
li t0,0x20003710
li t1,0x12345678
sw t1,0(t0)
li s0,0x40000100
li t0,0x40000300
lw t0,0(t0)
andi t0,t0,8
bnez t0,restarted
li s1,0x40001000
li t1,0x57415443
1: lw t2,12(s1)
andi t2,t2,2
beqz t2,1b
lw t2,8(s1)
bne t1,t2,failed
li t0,2
sw t0,4(s1)
li a0,1
call exchange
li t0,0x20003710
sw zero,0(t0)
'''+damage+'''li t0,0x40012000
li t1,0xf1
sw t1,0(t0)
'''+dma+f'''li t0,{1 if name.startswith('warm-dma-') else 32}
sw t0,0(s0)
sw zero,4(s0)
sw zero,8(s0)
li t0,0x57445354
sw t0,12(s0)
2: wfi
j 2b
restarted:
# Performance watchdog cause is handed to the application in a3.
andi t0,a3,8
beqz t0,failed
li s1,0x40001000
li t1,0x57415443
fresh_watcher:
lw t2,12(s1)
andi t2,t2,2
beqz t2,fresh_watcher
lw t2,8(s1)
bne t1,t2,failed
li t0,2
sw t0,4(s1)
li a0,1
call exchange
li t0,0x20003710
lw t1,0(t0)
li t2,0x12345678
bne t1,t2,failed
li t0,0x40012000
li t1,0xe2
sw t1,0(t0)
j 2b
exchange:
lw t0,12(s1)
andi t0,t0,1
beqz t0,exchange
sw a0,0(s1)
li t0,1
sw t0,4(s1)
reply:
lw t0,12(s1)
andi t0,t0,2
beqz t0,reply
lw t0,8(s1)
bne t0,a0,failed
li t0,2
sw t0,4(s1)
ret
failed:
li t0,0x40012000
li t1,0xee
sw t1,0(t0)
j 2b
''')
  cases[name]=flash({1:bundle(application,lite,b'CFG1',generation=1,allocation=14336,lite_data=8,lite_stack=16)})
 for name,data in cases.items():(out/(name+'.flash')).write_bytes(data)
 (out/'competing-b.bundle').write_bytes(images['b'])
 raw=bytes(128)+(ROOT/a.rom).read_bytes();assert len(raw)<=65536
 raw+=bytes(65536-len(raw));(out/'rom.hex').write_text(''.join(f'{int.from_bytes(raw[i:i+4],"little"):08x}\n' for i in range(0,len(raw),4)))
 (out/'prepared.json').write_text(json.dumps(dict(status='prepared',commands=commands,
  source_sha256={str(q):hashlib.sha256(q.read_bytes()).hexdigest() for q in [pathlib.Path(__file__),SRC/'image.py',ROOT/a.rom,*[watcher/n for n in ('start.S','watcher.c','crc16.h','watcher.ld')]]},
  cases={n:dict(scenario=n if n.startswith('warm-') else 'held' if n in ('held','watcher-held','max-lite-held') else 'recovery' if n=='empty' or n.startswith('bad-') else 'strap' if n=='strap' else 'normal',
   marker={'core-smoke':0xa5,'a':0xa1,'newest-b':0xb2,'golden':0xc3,'held':0xd4,'corrupt-newest':0xa1,'uncommitted':0xa1,'empty':0,'strap':0,
     'warm-match':0xe2,'warm-reload':0xe2,'warm-lite-reload':0xe2,'warm-bad-context':0xf1,'warm-bad-context-reset':0xf1,'tie-a':0xa1,
     'warm-flash-missing':0xf1,'warm-flash-corrupt':0xf1,'warm-newer':0xe2,'warm-dma-drain':0xe2,'warm-dma-stall':0xe2,
     'bad-directory':0,'bad-range':0,'bad-generation':0,'bad-compatibility':0,'bad-extent':0,'watcher-held':0xd4,'max-lite-held':0xd4}[n],
   selected_slot=None if n in ('empty','strap') or n.startswith('bad-') else 0 if n=='golden' else 2 if n=='newest-b' else 1) for n in cases},
  artifact_sha256={str(q.relative_to(out)):hashlib.sha256(q.read_bytes()).hexdigest() for q in out.rglob('*') if q.is_file()}),indent=2)+'\n')
 print('PREPARED; no production simulation claimed')
if __name__=='__main__':main()

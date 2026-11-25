"""Build the performance ROM from the pinned compiler and generated maps."""
import argparse,hashlib,json,pathlib,subprocess,sys,time

ROOT=pathlib.Path.cwd();SRC=pathlib.Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True)
 p.add_argument('--negative-control',choices=('CRC','RANGE','COMMIT','EARLY_RELEASE','WARM_SKIP_RELOAD'))
 a=p.parse_args();out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
 inputs=[SRC/n for n in ('start.S','policy.c','platform.c','main.c','recovery.c','boot.h','platform.h','rom.ld')]
 includes=['build/t20/map','build/t30/qspi','build/t20/i1/uart','build/t28/boot_control','build/t23/dma']
 for directory in includes:inputs+=sorted((ROOT/directory).glob('*.h'))
 sources={str(q):sha(q) for q in [*inputs,pathlib.Path(__file__)]}
 receipt=dict(status='running',commands=[],source_sha256=sources,negative_control=a.negative_control)
 def save():(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
 def run(cmd,label):
  start=time.monotonic();r=subprocess.run(list(map(str,cmd)),capture_output=True,text=True)
  (out/(label+'.log')).write_text(r.stdout+r.stderr)
  receipt['commands'].append(dict(command=list(map(str,cmd)),seconds=time.monotonic()-start,returncode=r.returncode));save()
  r.check_returncode();return r.stdout
 flags=['-march=rv32imc_zicsr_zifencei','-mabi=ilp32','-Os','-ffreestanding','-fno-builtin',
  '-ffunction-sections','-fdata-sections','-fstack-usage','-fno-common','-msmall-data-limit=0','-Wall','-Wextra','-Werror']
 flags+=['-I'+str(ROOT/d) for d in includes]
 if a.negative_control:flags+=['-DDH_BOOT_FAULT_'+a.negative_control]
 try:
  objects=[]
  for name in ('start.S','policy.c','platform.c','main.c','recovery.c'):
   obj=out/(pathlib.Path(name).stem+'.o');objects.append(obj)
   run(['riscv64-unknown-elf-gcc',*flags,'-c',SRC/name,'-o',obj],name)
  run(['riscv64-unknown-elf-gcc',*flags,'-nostdlib','-Wl,--no-relax','-Wl,--gc-sections',
   '-Wl,-Map,'+str(out/'rom.map'),'-Wl,-T,'+str(SRC/'rom.ld'),*objects,'-o',out/'rom.elf'],'link')
  run(['riscv64-unknown-elf-size','-A',out/'rom.elf'],'size')
  symbols=run(['riscv64-unknown-elf-nm','--defined-only',out/'rom.elf'],'symbols')
  run(['riscv64-unknown-elf-objcopy','-O','binary',out/'rom.elf',out/'rom.bin'],'binary')
  run(['riscv64-unknown-elf-objdump','-d',out/'rom.elf'],'disassembly')
  syms={x.split()[2]:int(x.split()[0],16) for x in symbols.splitlines() if len(x.split())==3}
  assert syms['_start']==0x80
  raw=bytes(128)+(out/'rom.bin').read_bytes();assert len(raw)<=65536
  receipt.update(rom_used_bytes=len(raw),rom_payload_bytes=len(raw)-128,fail_pc=syms['dh_fail'],
   globals_bytes=syms['__bss_end']-syms['__bss_start'])
  raw+=bytes(65536-len(raw));(out/'rom.hex').write_text(''.join(f'{int.from_bytes(raw[i:i+4],"little"):08x}\n' for i in range(0,len(raw),4)))
  assert all(sha(pathlib.Path(q))==h for q,h in sources.items())
  receipt['status']='built-negative-control' if a.negative_control else 'built'
 except Exception as e:receipt.update(status='failed',error=str(e));raise
 finally:
  receipt['artifact_sha256']={str(q.relative_to(out)):sha(q) for q in out.rglob('*') if q.is_file() and q.name!='result.json'};save()
 print(receipt['status'],receipt['rom_payload_bytes'],'measured firmware bytes; mapped area not yet measured')
if __name__=='__main__':main()

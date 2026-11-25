"""Actual lite watchdog and performance sleep firmware; no injected reset."""
from pathlib import Path
import subprocess,json,hashlib

def main():
    out=Path('build/plan05/hung-firmware');out.mkdir(parents=True,exist_ok=True);commands=[]
    for name,source,isa,abi,base in [('lite','lite_hung.S','rv32e_zicsr','ilp32e',0x30000000),('boot','hung_boot.S','rv32i_zicsr','ilp32',0x80)]:
        linker=out/(name+'.ld');linker.write_text(f'ENTRY(_start)\nSECTIONS {{ . = {base}; .text : {{ *(.start) }} }}\n')
        for command in [['riscv64-unknown-elf-gcc','-march='+isa,'-mabi='+abi,'-nostdlib','-Wl,--no-relax',
            '-Wl,-T,'+str(linker),'dv/soc/plan05/'+source,'-o',str(out/(name+'.elf'))],
            ['riscv64-unknown-elf-objcopy','-O','binary',str(out/(name+'.elf')),str(out/(name+'.bin'))]]:
            subprocess.run(command,check=True);commands.append(command)
        raw=(out/(name+'.bin')).read_bytes();assert len(raw)%4==0 and len(raw)<=1024
        if name=='boot':raw=bytes(128)+raw;raw+=bytes(65536-len(raw))
        (out/(name+'.hex')).write_text(''.join(f'{int.from_bytes(raw[i:i+4],"little"):08x}\n' for i in range(0,len(raw),4)))
    h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    (out/'result.json').write_text(json.dumps(dict(status='built_not_simulated',commands=commands,
        sources={str(p):h(p) for p in [Path(__file__),Path('dv/soc/plan05/lite_hung.S'),Path('dv/soc/plan05/hung_boot.S')]},
        artifacts={p.name:h(p) for p in out.glob('*') if p.is_file() and p.name!='result.json'}),indent=2)+'\n')
    print('PASS hung-watcher diagnostic built')
if __name__=='__main__':main()

"""Build the actual watchdog START/reboot fixture and wrong-key control."""
from pathlib import Path
import hashlib,json,subprocess

def main():
    source=Path(__file__).resolve().parent
    out=Path('build/t33/watchdog-phase-firmware');out.mkdir(parents=True,exist_ok=True)
    commands=[]
    for name,flags in (('boot',[]),('bad',['-DWRONG_START']),
            ('offered',['-DOFFERED','-DDELAY_NOPS=2990']),('early',['-DOFFERED','-DDELAY_NOPS=1536'])):
        linker=out/(name+'.ld');linker.write_text('ENTRY(_start)\nSECTIONS { . = 128; .text : { *(.start) } }\n')
        for cmd in (
            ['riscv64-unknown-elf-gcc','-march=rv32i_zicsr','-mabi=ilp32','-nostdlib','-Wl,--no-relax',*flags,
             '-Wl,-T,'+str(linker),str(source/'watchdog_phase.S'),'-o',str(out/(name+'.elf'))],
            ['riscv64-unknown-elf-objcopy','-O','binary',str(out/(name+'.elf')),str(out/(name+'.bin'))]):
            subprocess.run(cmd,check=True);commands.append(cmd)
        raw=bytes(128)+(out/(name+'.bin')).read_bytes();assert len(raw)%4==0 and len(raw)<=65536
        raw+=bytes(65536-len(raw))
        (out/(name+'.hex')).write_text(''.join(f'{int.from_bytes(raw[i:i+4],"little"):08x}\n' for i in range(0,len(raw),4)))
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    receipt=dict(status='built_not_simulated',commands=commands,
        sources={str(p):digest(p) for p in (source/'watchdog_phase.S',Path(__file__))},
        artifacts={p.name:digest(p) for p in out.iterdir() if p.is_file() and p.name!='result.json'})
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS watchdog phase firmware built; no simulation acceptance')
if __name__=='__main__':main()

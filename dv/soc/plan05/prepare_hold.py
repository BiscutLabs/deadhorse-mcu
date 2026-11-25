"""Production firmware for timer/DMA/USB deep-sleep inhibition."""
from pathlib import Path
import subprocess,hashlib,json

def main():
    out=Path('build/plan05/hold-firmware');out.mkdir(parents=True,exist_ok=True)
    linker=out/'boot.ld';linker.write_text('ENTRY(_start)\nSECTIONS { . = 0x80; .text : { *(.start) } }\n')
    commands=[]
    for kind in range(4):
        prefix=out/str(kind)
        for command in [['riscv64-unknown-elf-gcc','-march=rv32i_zicsr','-mabi=ilp32','-nostdlib','-Wl,--no-relax',
                '-DHOLD_KIND='+str(kind),'-Wl,-T,'+str(linker),'dv/soc/plan05/hold.S','-o',str(prefix)+'.elf'],
                ['riscv64-unknown-elf-objcopy','-O','binary',str(prefix)+'.elf',str(prefix)+'.bin']]:
            subprocess.run(command,check=True);commands.append(command)
        raw=bytes(128)+Path(str(prefix)+'.bin').read_bytes();assert len(raw)%4==0 and len(raw)<=65536
        raw+=bytes(65536-len(raw))
        Path(str(prefix)+'.hex').write_text(''.join(f'{int.from_bytes(raw[i:i+4],"little"):08x}\n' for i in range(0,len(raw),4)))
    h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    (out/'result.json').write_text(json.dumps(dict(status='built_not_simulated',commands=commands,
        sources={str(p):h(p) for p in (Path(__file__),Path('dv/soc/plan05/hold.S'))},
        artifacts={p.name:h(p) for p in out.glob('*.hex')}),indent=2)+'\n')
    print('PASS hold diagnostic firmware built')
if __name__=='__main__':main()

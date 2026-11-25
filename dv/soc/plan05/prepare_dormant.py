"""Build diagnostic production-top ROM with the measured watcher, not T36 ROM."""
import hashlib,json,subprocess
from pathlib import Path

def main():
    out=Path('build/plan05/dormant-firmware');out.mkdir(parents=True,exist_ok=True)
    watcher=Path('build/plan05/watcher-opt05');receipt=json.loads((watcher/'measurement.json').read_text())
    assert receipt['status']=='pass','Watcher measurement has not passed'
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    assert digest(watcher/'watcher.bin')==receipt['artifacts']['watcher.bin']
    for name,expected in receipt['sources'].items():
        if name.startswith('sw/lite/watcher/'):assert digest(Path(name))==expected,name
    linker=out/'boot.ld';linker.write_text('ENTRY(_start)\nSECTIONS { . = 0x80; .text : { *(.start) } }\n')
    commands=[['riscv64-unknown-elf-gcc','-march=rv32i_zicsr','-mabi=ilp32','-nostdlib','-Wl,--no-relax',
               '-Wl,-T,'+str(linker),'dv/soc/plan05/dormant.S','-o',str(out/'boot.elf')],
              ['riscv64-unknown-elf-objcopy','-O','binary',str(out/'boot.elf'),str(out/'boot.bin')]]
    for command in commands:subprocess.run(command,check=True)
    raw=bytes(128)+(out/'boot.bin').read_bytes();assert len(raw)%4==0 and len(raw)<=65536
    content=len(raw);raw+=bytes(65536-len(raw))
    (out/'boot.hex').write_text(''.join(f'{int.from_bytes(raw[i:i+4],"little"):08x}\n' for i in range(0,len(raw),4)))
    (out/'result.json').write_text(json.dumps(dict(status='built_not_simulated',commands=commands,rom_content_bytes=content,
        source_sha256={str(p):digest(p) for p in [Path(__file__),Path('dv/soc/plan05/dormant.S'),watcher/'watcher.bin',watcher/'measurement.json',*(Path(n) for n in receipt['sources'] if n.startswith('sw/lite/watcher/'))]},
        artifacts={p.name:digest(p) for p in out.glob('boot.*')}),indent=2)+'\n')
    print('PASS diagnostic dormant ROM built')
if __name__=='__main__':main()

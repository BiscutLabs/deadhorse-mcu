"""Build real client firmware without starting QSPI or the watchdog."""
from pathlib import Path
import hashlib,json,subprocess

def main():
    source=Path(__file__).resolve().parent
    out=Path('build/t33/client-firmware');out.mkdir(parents=True,exist_ok=True)
    commands=[]
    def run(command):
        subprocess.run(command,check=True);commands.append(list(map(str,command)))
    for name,filename,flags,isa,abi,base in (
            ('lite','client_lite.S',[],'rv32e_zicsr','ilp32e',0x30000000),
            ('boot-lite','client_perf.S',['-DLITE_CLIENT'],'rv32i_zicsr','ilp32',0x80),
            ('boot','client_perf.S',[],'rv32i_zicsr','ilp32',0x80)):
        linker=out/(name+'.ld');linker.write_text(f'ENTRY(_start)\nSECTIONS {{ . = {base}; .text : {{ *(.start) }} }}\n')
        run(['riscv64-unknown-elf-gcc','-march='+isa,'-mabi='+abi,'-nostdlib','-Wl,--no-relax',
            *flags,'-Wl,-T,'+str(linker),str(source/filename),'-o',str(out/(name+'.elf'))])
        run(['riscv64-unknown-elf-objcopy','-O','binary',str(out/(name+'.elf')),str(out/(name+'.bin'))])
        raw=(out/(name+'.bin')).read_bytes();assert len(raw)%4==0
        if name.startswith('boot'):
            raw=bytes(128)+raw;assert len(raw)<=65536;raw+=bytes(65536-len(raw))
        else:assert 0<len(raw)<=1024
        (out/(name+'.hex')).write_text(''.join(f'{int.from_bytes(raw[i:i+4],"little"):08x}\n' for i in range(0,len(raw),4)))
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    receipt=dict(status='built_not_simulated',commands=commands,
        sources={str(p):digest(p) for p in (source/'client_lite.S',source/'client_perf.S',Path(__file__))},
        artifacts={p.name:digest(p) for p in out.iterdir() if p.is_file() and p.name!='result.json'})
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS client firmware built; no behavioral acceptance')

if __name__=='__main__':main()

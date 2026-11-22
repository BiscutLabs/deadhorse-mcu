"""Exact target-arithmetic checksum reference from the pinned ISS, including FMA."""
import hashlib,json,sys
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'dv/core'))
from lockstep import qemu_trace,read_qemu_trace,architectural_effect
base=root/'build/plan03/production-performance04'
for name,floating in [('fixed',False),('hard-float',True)]:
    reference=base/name/'reference';out=base/name/'qemu-checks';assert out.is_dir()
    elf=reference/'program.elf';binary=(reference/'workload.bin').read_bytes()
    rows=read_qemu_trace(out/'qemu.trace',0x80000000,floating)
    writes=[];fma=0
    for row in rows:
        off=row['pc']-0x80000000
        if off<0 or off+2>len(binary):continue
        insn=int.from_bytes(binary[off:off+4],'little')
        if insn&127 in (0x43,0x47,0x4b,0x4f):fma+=1
        # Mode/check writes are ordinary SW in both exact linked listings.
        compressed=insn&3!=3
        if compressed:insn&=0xffff
        if not (insn&0x707f==0x2023 if not compressed else insn>>13==6 and insn&3 in (0,2)):continue
        rd,memory=architectural_effect(insn,row['regs'])
        write,address,size,value=memory
        if address in (0x10000000,0x10000004):writes.append(dict(pc=row['pc'],address=address,value=value,size=size))
    modes=[v['value'] for v in writes if v['address']==0x10000000]
    words=[v['value'] for v in writes if v['address']==0x10000004]
    assert modes==[0,1,2] and len(words)==6 and words[::2]==modes
    result=dict(status='pass_reference',expected=list(zip(words[::2],words[1::2])),writes=writes,
      executed_fused_fp_instructions=fma,iss='Pinned dv/core/iss.json; exact unchanged reference ELF arithmetic and checksums',
      limitations='This receipt does not compare every production architectural state or claim production ISS lockstep.',
      hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [elf,reference/'workload.bin',out/'qemu.trace',root/'dv/core/iss.json',Path(__file__)]})
    (out/'result02.json').write_text(json.dumps(result,indent=2)+'\n')
    print(name,result['expected'],'FMA instructions',fma,flush=True)

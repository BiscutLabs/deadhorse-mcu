"""Check every production floating result against the exact pinned target program."""
import copy,hashlib,json,sys
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'dv/core'))
from lockstep import read_qemu_trace,completion_window
from suites import flight_reentry
from float_compare import effect
base=root/'build/plan03/production-performance04'
label=sys.argv[1]
out=base/('hard-float/fp-reference-'+label);out.mkdir(exist_ok=False)
binary=(base/'hard-float/reference/workload.bin').read_bytes()
iss=read_qemu_trace(base/'hard-float/qemu-checks/qemu.trace',0x80000000,True)
iss,duplicates=flight_reentry(iss,binary,0x80000000,allow_compressed=True)
iss=completion_window(iss,binary,0x80000000,allow_compressed_store=True)
raw=base/label/'hard-float/rvfi.jsonl'
rows=[json.loads(s) for s in raw.read_text().splitlines()]
rows=[r for r in rows if 0x20000000<=r['pc_rdata']<0x20004000]
def check(candidate):
    assert len(candidate)+1==len(iss),('Retirement count',len(candidate),len(iss))
    writes=0;fma=0
    for i,(r,before,after) in enumerate(zip(candidate,iss,iss[1:])):
        assert r['pc_rdata']+0x60000000==before['pc'],('PC',i)
        assert r['pc_wdata']+0x60000000==after['pc'],('next PC',i)
        off=before['pc']-0x80000000;insn=int.from_bytes(binary[off:off+4],'little')
        if insn&3!=3:insn&=0xffff
        rd,fd,sources,access=effect(insn,before['regs'],before['fregs'])
        assert bool(r['frd_wen'])==(fd is not None),('FP destination enable',i)
        if fd is not None:
            assert r['frd_addr']==fd and r['frd_wdata']==after['fregs'][fd],('FP result',i,hex(r['pc_rdata']))
            writes+=1
        if insn&127 in (0x43,0x47,0x4b,0x4f):fma+=1
        assert r['ext_fs']==(after['mstatus']>>13)&3,('FS',i)
    return writes,fma
writes,fma=check(rows)
index=next(i for i,r in enumerate(rows) if r['frd_wen'])
bad=list(rows);bad[index]=dict(rows[index],frd_wdata=rows[index]['frd_wdata']^1)
try:check(bad)
except AssertionError as e:assert e.args[0][0]=='FP result'
else:raise AssertionError('Wrong floating result escaped')
receipt=dict(status='pass',workload_retirements=len(rows),floating_writes=writes,fused_instructions=fma,
    qemu_reentries=duplicates,negative_control='wrong floating result rejected',
    scope='Every workload PC/next-PC, floating destination/result and FS state compared to target ISS after constant code-address relocation. Not full integer/memory/FCSR lockstep.',
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [raw,base/'hard-float/qemu-checks/qemu.trace',base/'hard-float/reference/workload.bin',Path(__file__)]})
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('PASS',writes,'floating writes,',fma,'fused instructions, wrong-result fault rejected',flush=True)

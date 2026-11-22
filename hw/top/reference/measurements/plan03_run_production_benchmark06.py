"""Run the prepared workload through the complete production SoC and real boot path."""
import copy,hashlib,importlib.util,json,re,shutil,subprocess,sys,time
from pathlib import Path
root=Path.cwd();sys.path[:0]=[str(root/'dv/core'),str(root)]
spec=importlib.util.spec_from_file_location('metrics',root/'tools/spikes/s1_core/performance.py')
metrics=importlib.util.module_from_spec(spec);spec.loader.exec_module(metrics)
base=root/'build/plan03/production-performance04';prepared=json.loads((base/'prepared.json').read_text())
for name,item in prepared.items():
    golden=json.loads((base/name/'qemu-checks/result02.json').read_text())
    assert golden['status']=='pass_reference'
    item['host_uncontracted_expected']=item['expected'];item['expected']=golden['expected']
    if not item['floating']:assert item['expected']==item['host_uncontracted_expected']
    item['reference_receipt']=str(base/name/'qemu-checks/result02.json')
mhz=int(sys.argv[1]);out=base/f'sim-{mhz}c';out.mkdir(exist_ok=False)
def run(args,directory,name,timeout=600):
    started=time.monotonic()
    with (directory/(name+'.log')).open('w') as f:r=subprocess.run(list(map(str,args)),cwd=root,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
    assert r.returncode==0,(name,r.returncode)
    return time.monotonic()-started
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
for name,item in prepared.items():
    d=Path(item['out']);comparison=json.loads((d/'loop-comparison.json').read_text())
    a,b=comparison['production'],comparison['reference'];assert len(a)==len(b)
    relocations=[]
    for x,y in zip(a,b):
        assert x['pc']-0x20000000==y['pc']-0x80000000
        actual,old=int(x['instruction'],16),int(y['instruction'],16)
        if actual!=old:
            assert old&127==0x37 and 0x80000000<=old&0xfffff000<=0x80004000
            assert actual==old-0x60000000
            relocations.append(dict(pc=x['pc'],before=y['instruction'],after=x['instruction']))
    (d/'loop-identity.json').write_text(json.dumps(dict(status='pass',instructions=len(a),relocations=relocations,
      claim='Every instruction in complete main loop is identical except RAM-address LUI relocation; PCs differ by exactly RAM-base relocation'),indent=2)+'\n')
active=out/'active-rom.hex';shutil.copyfile(Path(prepared['fixed']['out'])/'rom.hex',active)
emitted=out/'emit'
run([sys.executable,'tools/sbt.py',f'set hw / Compile / unmanagedSources += file("{root}/scratch/EmitProductionBenchmark.scala")',
     f'hw/runMain deadhorse.top.EmitProductionBenchmark {emitted} {active} {mhz}'],out,'emit')
sources=sorted(emitted.glob('*.sv'))+sorted(emitted.glob('*.v'))
gate=root/'hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv'
run(['verilator','--cc','--exe','--build','--assert','-DENABLE_INITIAL_MEM_','-DENABLE_INITIAL_REG_','-j','4','-Wno-fatal',
     '--top-module','DeadhorseSoc','--Mdir',out/'obj',*sources,gate,root/'scratch/production_benchmark.cpp'],out,'compile')
receipt=dict(status='in-progress',frequency_mhz_assumed=mhz,usb_mhz_assumed=48,aon_mhz_assumed=1,workloads={},
   scope='Production map, all features and real USB; lite recovery-wire boot and performance ROM copy; markers use existing GPIO value/enable writes observed on RVFI, pin mux selects no GPIO outputs; peripherals idle except boot/marker accesses. No SRAM preload, fake memory responder or boot override. Pinned target-ISS checksum evidence, not full ISS lockstep. Native host without contraction differs for floating point; preserved diagnosis and separate per-result reference comparison.')
def check_trace(rows,item):
    selected=[r for r in rows if r['mem_wmask'] and r['mem_addr']==0x40012004]
    values=[r['mem_wdata'] for r in selected]
    assert values==[v for pair in item['expected'] for v in pair],'Target reference checksum mismatch'
    assert all(not r['trap'] and not r['intr'] for r in rows)
    assert rows[-1]['mem_addr']==0x40012000 and rows[-1]['mem_wdata']==0x5555
    if item['floating']:
        executed=[r for r in rows if r['frd_wen']]
        assert executed and all(r['ext_fs']!=0 for r in executed),'Hard-float/FS evidence missing'
    # Boot copy is in ROM and ignored only for the workload stack observation.
    writes=[(i,r) for i,r in enumerate(rows) if r['rd_addr']==2 and r['rd_wdata'] and r['pc_rdata']>=0x20000000]
    assert writes
    first_i,first=writes[0]
    if first['insn']&0xfff==0x117:
        second=rows[first_i+1];immediate=(second['insn']>>20)&0xfff
        if immediate&0x800:immediate-=0x1000
        assert second['insn']&0xfffff==0x10113 and second['rd_addr']==2
        assert second['rd_wdata']==(first['rd_wdata']+immediate)&0xffffffff==0x20004000
        writes=writes[1:]
    stack=[r['rd_wdata'] for _,r in writes]
    assert min(stack)>=0x20003800 and max(stack)<=0x20004000,'Stack escaped unchanged 2 KiB reservation'
    return dict(checksums=item['expected'],stack_min=min(stack),stack_max=max(stack),hard_float_writes=sum(bool(r['frd_wen']) for r in rows))
for name,item in prepared.items():
    d=out/name;d.mkdir();shutil.copyfile(Path(item['out'])/'rom.hex',active)
    # The actual existing lite image starts at +16; no retained-memory backdoor.
    lite=root/'build/t28/firmware/lite.hex'
    wall=run([out/'obj/VDeadhorseSoc',mhz,lite,d/'rvfi.jsonl',d/'cycles.txt'],d,'simulate')
    rows=[json.loads(s) for s in (d/'rvfi.jsonl').read_text().splitlines()]
    cycle_rows=metrics.historical.timed_rows(rows,(d/'cycles.txt').read_text())
    checks=check_trace(rows,item)
    mode_rows=[r for r in rows if r['mem_wmask'] and r['mem_addr']==0x40012000 and r['mem_wdata'] in (0,1,2)]
    assert [r['mem_wdata'] for r in mode_rows]==[0,1,2]
    mode_pcs={r['pc_rdata'] for r in mode_rows};assert len(mode_pcs)==1
    mode_pc=next(iter(mode_pcs));assert not item['bounds']['start']<=mode_pc<=item['bounds']['end']
    binary=(Path(item['out'])/'workload.bin').read_bytes();offset=mode_pc-0x20000000
    opcode=int.from_bytes(binary[offset:offset+4],'little');mask=0xffffffff if opcode&3==3 else 0xffff
    assert all(r['mem_wmask']==15 and r['insn']&mask==opcode&mask for r in mode_rows)
    mode_orders={r['order'] for r in mode_rows}
    metric_rows=[dict(r,mem_addr=0x10000000) if r['order'] in mode_orders else r for r in rows]
    checks['mode_marker_adapter']=dict(pc=mode_pc,actual_address=0x40012000,analysis_address=0x10000000,orders=sorted(mode_orders),scope='Only authenticated whole-word mode writes in a copied view; PCs, instructions, cycles and all other observations unchanged')
    loop=metrics.iteration_metrics(metric_rows,cycle_rows,item['bounds'],mhz);assert loop['iterations']==120
    bad=copy.deepcopy(rows);index=next(i for i,r in enumerate(bad) if r['mem_wmask'] and r['mem_addr']==0x40012004)
    bad[index]['mem_wdata']^=1
    try:check_trace(bad,item)
    except AssertionError as e:assert 'checksum' in str(e).lower()
    else:raise AssertionError('Checksum fault escaped')
    first=next(i for i,r in enumerate(rows) if r['pc_rdata']==item['bounds']['start'])
    last=next(i for i in range(first,len(rows)) if rows[i]['pc_rdata']==item['bounds']['end'])
    pruned=metric_rows[:first]+metric_rows[last+1:]
    try:
        missing=metrics.iteration_metrics(pruned,cycle_rows[:first]+cycle_rows[last+1:],item['bounds'],mhz)
        assert missing['iterations']==120,'Incomplete iteration inventory'
    except (AssertionError,ValueError) as error:assert 'Incomplete' in str(error)
    else:raise AssertionError('Omitted iteration escaped')
    receipt['workloads'][name]=dict(status='measured',loop=loop,checks=checks,wall_seconds=wall,
      negative_controls={'checksum':'rejected','omitted_iteration':'rejected'},sections=item['sections'],
      reference_receipt=item['reference_receipt'],raw_trace_sha256=digest(d/'rvfi.jsonl'),
      loop_identity_sha256=digest(Path(item['out'])/'loop-identity.json'))
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(mhz,name,'mean',loop['mean_cycles'],'worst',loop['worst_cycles'],'cycles',flush=True)
receipt['status']='pass_measured_production_workload'
receipt['sources']={str(p):digest(p) for p in [*sources,gate,root/'scratch/production_benchmark.cpp',root/'scratch/EmitProductionBenchmark.scala',Path(__file__)]}
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')

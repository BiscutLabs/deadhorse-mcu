"""Refresh unchanged USB proof bindings after PLAN05 build-source additions.

No solver runs. Reuse requires byte-identical HDL and exact canonical/selected
models, allowing only the emission-directory prefix in source attributes.
Focused traffic witnesses are rerun; original receipts remain immutable.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'hw/ip/usb/formal'),str(ROOT/'hw/ip/usb')]
import sampling
import sampling_witness
import sie_packet_contract
import evidence
from packet_partition import selected_model
from packet_receipt import checked_job

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,d):Path(p).write_text(json.dumps(d,indent=2)+'\n')

def relocate_src(value,before,after):
    if isinstance(value,dict):
        for key,item in value.items():
            if key=='attributes' and isinstance(item,dict) and 'src' in item:
                item['src']=item['src'].replace(before+'/',after+'/')
            relocate_src(item,before,after)
    elif isinstance(value,list):
        for item in value:relocate_src(item,before,after)

def replay(origin,destination,role):
    old=read(origin);assert old['status']=='safety-proved'
    assert digest(origin.parent/'runner.py')==old['source_sha256'][
        'hw/ip/usb/formal/'+('sie_packet_contract.py' if role=='sie' else 'sampling.py')]
    for p,h in old['emitted_sha256'].items():assert digest(p)==h,p
    canonical=read(origin.parent/'canonical.json')
    assert digest(origin.parent/'canonical.json')==old['canonical_sha256']
    jobs=[j['positive'] for j in old['jobs']] if role=='sie' else [old['positive']]
    used=[]
    def reuse(directory,model,top,keep,assumed=(),**kwargs):
        fresh=copy.deepcopy(model)
        relocate_src(fresh,str(destination.relative_to(ROOT)),str(origin.parent.relative_to(ROOT)))
        assert fresh==canonical,'Changed canonical model: '+role
        selected=selected_model(fresh,top,set(keep),set(assumed))
        matches=[j for j in jobs if checked_job(j,'proof')==selected]
        assert len(matches)==1 and matches[0] not in used,'Missing/ambiguous original proof partition'
        used.append(matches[0]);return copy.deepcopy(matches[0])
    module=sie_packet_contract if role=='sie' else sampling
    original=module.lemma_job;module.lemma_job=reuse
    try:
        fresh=module.run(destination) if role=='sie' else module.run(destination,ROOT/'build/t19/regmap/usb_regs.json',role)
    finally:module.lemma_job=original
    assert fresh['status']=='safety-proved' and len(used)==len(jobs),fresh.get('error')
    def hdl(row,base):return {Path(p).relative_to(base).as_posix():h for p,h in row['emitted_sha256'].items()}
    assert hdl(fresh,destination)==hdl(old,origin.parent),'Fresh HDL changed'
    metadata=dict(original=str(origin),original_sha256=digest(origin),fresh_receipt=str(destination/'result.json'),
        fresh_receipt_sha256=digest(destination/'result.json'),rebinder_sha256=digest(__file__),solver_runs=0,
        equality='Byte-identical HDL; exact canonical JSON and selected assertions/assumptions after only src emission-prefix relocation')
    bound=copy.deepcopy(old)
    runner='hw/ip/usb/formal/'+('sie_packet_contract.py' if role=='sie' else 'sampling.py')
    bound['source_sha256']={p:(old['source_sha256'][p] if p==runner else h) for p,h in fresh['source_sha256'].items()}
    bound['proof_reuse']=metadata
    target=origin.parent/(destination.parent.name+'-'+role+'-source-binding.json')
    assert not target.exists();write(target,bound)
    return target

def archive_sie(binding):
    row=read(binding);root=binding.parent/'simulation-archive';root.mkdir()
    files={};sources={}
    for name,h in row['simulation']['artifact_sha256'].items():
        p=Path(name);relative=p.relative_to(ROOT/'build/t19/sie-composition-simulation')
        q=root/relative;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
        assert digest(q)==h;files[str(q)]=dict(origin=str(p),sha256=h)
    for name,h in row['current_source_sha256'].items():
        p=ROOT/name;q=root/'source'/name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
        assert digest(q)==h;sources[str(q)]=h
    shutil.copyfile(binding.parent/'simulation.log',root/'simulation.log')
    target=binding.parent/'archive.json'
    write(target,dict(status='pass',origin_receipt_sha256=digest(binding),files=files,source_sha256=sources,
                     ci='not run; focused composition suite'))
    return target

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    args=parser.parse_args();out=(ROOT/args.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='running',solver_runs=0,commands=[],runner_sha256=digest(__file__))
    def save():write(out/'result.json',receipt)
    try:
        sampling_paths={}
        for role,name in [('lookahead','lookahead03'),('outputs','outputs01'),('spacing','spacing01')]:
            sampling_paths[role]=replay(ROOT/f'build/plan03/usb-closure/{name}/result.json',out/role,role)
            print('PASS exact proof replay '+role,flush=True)
        sie=replay(ROOT/'build/t19/sie-packet-contract-02/result.json',out/'sie','sie')
        print('PASS exact proof replay sie',flush=True)
        binding=out/'wrapper/result.json'
        result=sie_packet_contract.bind_wrapper(binding.parent,sie,ROOT/'build/t19/regmap/usb_regs.json',simulate=True)
        assert result['status']=='pass',result.get('error');archive=archive_sie(binding)
        witness=sampling_witness.prepare(out/'witness',sampling_paths)
        assert sampling_witness.simulate(out/'witness',witness)
        witness_archive=out/'witness-archive'
        evidence.archive_sampling(out/'witness/result.json',witness_archive)
        full=out/'full-size';full.mkdir();sources=evidence.simulation_sources();begin=time.monotonic()
        command=['python3','tools/sbt.py','testOnly deadhorse.usb.UsbThroughputSpec']
        with (full/'simulation.log').open('w') as stream:
            process=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        log=(full/'simulation.log').read_text()
        assert process.returncode==0 and 'Tests: succeeded 2, failed 0' in log and 'All tests passed.' in log
        assert evidence.simulation_sources()==sources
        write(full/'result.json',dict(status='pass',command=command,returncode=0,seconds=time.monotonic()-begin,
            source_sha256=sources,log_sha256=digest(full/'simulation.log'),
            qualification='Full16byte seeded production-wrapper simulation, including unchanged slow-service negative control; no proof claim'))
        packet=read(ROOT/'build/t32/usb-acceptance-inputs01/packet-manifest.json')
        packet.update(sie_proof=str(sie),sie_binding=str(binding),sie_archive=str(archive),full_size_simulation=str(full/'result.json'))
        write(out/'packet-manifest.json',packet)
        sample=read(ROOT/'build/t32/usb-acceptance-inputs01/sampling-manifest.json')
        sample.update(sie_proof=str(sie),sie_binding=str(binding),sie_archive=str(archive),
            witness=str(out/'witness/result.json'),witness_archive=str(witness_archive/'result.json'))
        write(out/'sampling-manifest.json',sample)
        audited=evidence.collect(out/'packet-manifest.json',out/'packet-audit');assert audited['status']=='pass',audited.get('error')
        for top,folder in [('Usb','usb'),('UsbEngine','engine'),('UsbControl','control')]:
            paths=sorted((out/'lookahead/emit'/folder).glob('*.sv'))+sorted((out/'lookahead/emit'/folder).glob('*.v'))
            evidence.sampling_evidence(out/'sampling-manifest.json',top,paths)
        receipt['status']='pass'
    except Exception as error:receipt.update(status='failed',error=str(error));raise
    finally:save()
if __name__=='__main__':main()

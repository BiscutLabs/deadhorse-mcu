"""Passive I0 request/grant diagnosis against a preserved measured execution."""
import argparse
import collections
import json
from pathlib import Path
import sys
from fixture import ROOT, compile_sim, digest, run


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--measurement',required=True); ap.add_argument('--output',required=True)
    args=ap.parse_args()
    measurement=(ROOT/args.measurement).resolve(); measurement.relative_to(ROOT/'build')
    out=(ROOT/args.output).resolve(); out.relative_to(ROOT/'build'); out.mkdir(parents=True,exist_ok=False)
    prior=json.loads((measurement/'result.json').read_text())
    if prior['status'] not in ('blocked_overhead','pass_measured_fixture'): raise ValueError('No qualified measurement')
    receipt=dict(status='running',measurement_receipt_sha256=digest(measurement/'result.json'),
                 scope='Passive public bus trace; original RVFI and cycles must match exactly')
    sources=[*sorted((ROOT/'hw/top/reference/src/main/scala').glob('**/*.scala')),
             Path(__file__),ROOT/'dv/soc/fixture.py',ROOT/'dv/soc/sim_main.cpp']
    receipt['source_sha256']={str(p.relative_to(ROOT)):digest(p) for p in sources}
    try:
        for name in ('fixed/simulate.log','fixed/cycles.txt'):
            if digest(measurement/name)!=prior['artifact_sha256'][name]: raise ValueError('Prior trace changed')
        images=measurement/'fixed/loaded-images'
        for p in images.iterdir():
            if p.is_file() and digest(p)!=prior['artifact_sha256'][str(p.relative_to(measurement))]:
                raise ValueError('Prior loaded image changed')
        sim=compile_sim(out/'sim',images)
        bus=out/'bus.txt'; cycles=out/'cycles.txt'
        result=run(['env',f'DEADHORSE_BUS_TRACE={bus}',f'DEADHORSE_CYCLE_TRACE={cycles}',sim,'flight'],out,'simulate')
        def rows(path): return [json.loads(line) for line in path.open() if line.startswith('{')]
        if rows(out/'simulate.log')!=rows(measurement/'fixed/simulate.log'): raise ValueError('Observation changed RVFI')
        if cycles.read_bytes()!=(measurement/'fixed/cycles.txt').read_bytes(): raise ValueError('Observation changed cycles')
        idle=0; gaps=collections.defaultdict(collections.Counter); waits=collections.Counter()
        pcs=(0x800001b4,0x800001dc,0x8000020c)
        for line in bus.open():
            cycle,req,gnt,address,valid,dreq,dgnt=map(int,line.split())
            if req:
                if idle and address in pcs: gaps[hex(address)][idle]+=1
                if not gnt: waits[hex(address)]+=1
                idle=0
            else: idle+=1
        receipt.update(status='pass_trace_matches',idle_before_checksum_request={pc:dict(v) for pc,v in gaps.items()},
                       checksum_request_wait_cycles={hex(pc):waits[hex(pc)] for pc in pcs})
        if any(digest(p)!=receipt['source_sha256'][str(p.relative_to(ROOT))] for p in sources):
            raise ValueError('Trace sources changed')
        print(json.dumps({k:receipt[k] for k in ('status','idle_before_checksum_request','checksum_request_wait_cycles')},indent=2))
    except Exception as error:
        receipt.update(status='failed',error=str(error)); raise
    finally:
        receipt['artifact_sha256']={str(p.relative_to(out)):digest(p) for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
        (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__': main()

"""Finish strict audits after evidence01's final control-directory typo.

No tests, proofs or measurements are rerun or relabelled. Original failure and
its producer are retained; every proof/simulation input is audited afresh.
"""
import argparse
import copy
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(Path(__file__).parent),str(ROOT/'hw/ip/usb')]
from plan05_usb_evidence import digest,read,write,relocate_src
import evidence

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    origin=(ROOT/a.input).resolve();origin.relative_to(ROOT/'build')
    out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    original=read(origin/'result.json')
    assert original['status']=='failed' and original['error']=='Timing HDL differs from proved sampling context'
    assert digest(origin/'runner.py')==original['runner_sha256']
    packet=read(origin/'packet-manifest.json');sample=read(origin/'sampling-manifest.json')
    witness=read(sample['witness'])
    for path in [packet['sie_proof'],*witness['proofs']]:
        proof=read(path);reuse=proof['proof_reuse']
        assert reuse['rebinder_sha256']==digest(origin/'runner.py') and reuse['solver_runs']==0
        old_path=Path(reuse['original']);fresh_path=Path(reuse['fresh_receipt'])
        assert digest(old_path)==reuse['original_sha256'] and digest(fresh_path)==reuse['fresh_receipt_sha256']
        old=read(old_path);fresh=read(fresh_path)
        model=copy.deepcopy(read(fresh_path.parent/'canonical.json'))
        relocate_src(model,str(fresh_path.parent.relative_to(ROOT)),str(old_path.parent.relative_to(ROOT)))
        assert model==read(old_path.parent/'canonical.json')
        before={Path(n).relative_to(old_path.parent).as_posix():h for n,h in old['emitted_sha256'].items()}
        after={Path(n).relative_to(fresh_path.parent).as_posix():h for n,h in fresh['emitted_sha256'].items()}
        assert before==after
        evidence.check_hashes(fresh['emitted_sha256'])
    write(out/'packet-manifest.json',packet);write(out/'sampling-manifest.json',sample)
    result=evidence.collect(out/'packet-manifest.json',out/'packet-audit')
    assert result['status']=='pass',result.get('error')
    roles={}
    for top,folder in [('Usb','usb'),('UsbEngine','engine'),('UsbControl','control')]:
        sources=sorted((origin/'lookahead/emit'/folder).glob('*.sv'))+sorted((origin/'lookahead/emit'/folder).glob('*.v'))
        roles[top]=evidence.sampling_evidence(out/'sampling-manifest.json',top,sources)
    write(out/'result.json',dict(status='pass',origin=str(origin/'result.json'),origin_sha256=digest(origin/'result.json'),
        runner_sha256=digest(__file__),original_runner_sha256=digest(origin/'runner.py'),
        solver_runs=0,simulation_runs=0,roles=roles,
        qualification='Strict current-source/model/proof/simulation audit; only final audit folder changed ep0 to actual control. Original failed receipt preserved.'))
    print('PASS strict USB proof/simulation finalization; no solver or simulation rerun')
if __name__=='__main__':main()

"""Derive USB historical bindings over the reviewed non-USB timing recipe delta.

This never measures/relabels old physical data or changes acceptance collectors.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from timing_iterations import ROOT,sha,write

sys.path.insert(0,str(ROOT/'hw/ip/usb'))
from physical_evidence import collect as physical
from evidence import collect as packet,sampling_evidence
from tools.timing import check as current


def local(path):return ROOT/str(path).removeprefix('/work/')
def read(path):return json.loads(Path(path).read_text())
def validate(values):
    for p,h in values.items():assert sha(local(p))==h,p


def main():
    old=ROOT/'build/t32/usb-verifier-rebind03'
    out=ROOT/'build/t32/timing-iterations/usb-evidence'
    out.mkdir(parents=True,exist_ok=False)
    result=dict(status='running',producer_sha256=sha(__file__),
        qualification='Historical USB measurements retained byte-for-byte; reviewed main-9mhz mapping recipe and optimization-target test delta only. No fresh physical measurement.')
    try:
        original=old/'bus-source-qualified01/result.json';bound=read(original)
        changes={p:dict(original=h,current=sha(local(p))) for p,h in bound['source_sha256'].items() if sha(local(p))!=h}
        assert set(changes)=={'tools/timing/check.py','tools/timing/test_timing.py'},changes
        for p,change in changes.items():
            raw=subprocess.check_output(['git','show','9b80375:'+p])
            options=[raw,raw.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')]
            matches=[r for r in options if hashlib.sha256(r).hexdigest()==change['original']]
            assert matches,p
            archive=out/'original'/p;archive.parent.mkdir(parents=True,exist_ok=True);archive.write_bytes(matches[0])
            change['archive']=str(archive)
        spec=importlib.util.spec_from_file_location('old_timing_check',out/'original/tools/timing/check.py')
        previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
        previous.ROOT=ROOT;previous.CONFIG=current.CONFIG
        for point in current.OPERATING_POINTS:
            left,right=previous.timing_config(point),current.timing_config(point)
            if point=='main-9mhz':
                left.pop('provenance');right.pop('provenance')
            assert left==right,point
            before=previous.mapping_target_ps(previous.timing_config(point),point)
            after=current.mapping_target_ps(current.timing_config(point),point)
            assert (before==62500 and after==50000) if point=='main-9mhz' else before==after
        for key in ('hdl_sha256','artifact_sha256','library_sha256'):validate(bound[key])
        now={p:sha(local(p)) for p in bound['source_sha256']}
        metadata=dict(original_binding=str(original),original_binding_sha256=sha(original),
                      deltas=changes,unchanged_source_count=len(now)-2,
                      qualification=result['qualification'],producer_sha256=sha(__file__))
        # Keep the original chain and measured values; derive only source binding.
        bound['source_sha256']=now;bound['mapping_only_rebinding']=metadata
        binding=out/'bus-source-qualified01/result.json';binding.parent.mkdir(parents=True);write(binding,bound)
        replaypath=old/'historical-replay-binding.json';replay=read(replaypath)
        for key in ('source_sha256','input_sha256'):validate(replay[key])
        for p,h in replay['artifact_sha256'].items():
            # The original replay's artifacts live at replay02, not this derived binding.
            assert sha(ROOT/'build/t32/replay02'/p)==h,p
        replay['production_source_sha256']=now;replay['mapping_only_rebinding']=metadata
        write(out/'historical-replay-binding.json',replay)
        for folder in ('bus-physical01','bus-hold01'):shutil.copytree(old/folder,out/folder)
        copied={str(p.relative_to(out)):sha(p) for folder in ('bus-physical01','bus-hold01') for p in (out/folder).rglob('*') if p.is_file()}
        assert all(sha(old/p)==h for p,h in copied.items())
        composition=read(out/'bus-physical01/composition.json');validate(composition['input_sha256'])
        keys=[p for p in composition['input_sha256'] if local(p)==original];assert len(keys)==1
        del composition['input_sha256'][keys[0]];composition['input_sha256'][str(binding)]=sha(binding)
        composition['mapping_only_rebinding']=metadata;write(out/'bus-physical01/composition.json',composition)
        hold=read(out/'bus-hold01/result.json');validate(hold['artifact_sha256'])
        assert hold['binding_sha256']==sha(original)
        hold['binding_sha256']=sha(binding);hold['mapping_only_rebinding']=metadata;write(out/'bus-hold01/result.json',hold)
        manifest=read(old/'physical-manifest.json');manifest.update(source=str(binding),hold=str(out/'bus-hold01/result.json'),bus=str(out/'bus-physical01'))
        write(out/'physical-manifest.json',manifest)
        acceptance=read(old/'acceptance-manifest.json');acceptance['physical']=str(out/'physical-manifest.json');write(out/'acceptance-manifest.json',acceptance)
        result.update(rebinding=metadata,copied_fixture_sha256=copied)
        for top,folder in [('UsbControl','control'),('UsbEngine','engine'),('Usb','usb')]:
            src=ROOT/'build/t32/usb-rebind02/lookahead/emit'/folder
            audit=sampling_evidence(local(acceptance['sampling']),top,sorted(src.glob('*.sv'))+sorted(src.glob('*.v')))
            write(out/('sampling-'+top+'.json'),audit);assert audit['status']=='pass'
            print('PASS sampling '+top,flush=True)
        audit=packet(local(acceptance['packet']),out/'packet-audit');assert audit['status']=='pass';print('PASS packet',flush=True)
        audit=physical(out/'physical-manifest.json',ROOT/'build/t32/usb-rebind02/lookahead/emit/usb',out/'physical-audit');assert audit['status']=='pass';print('PASS physical',flush=True)
        validate(now);result['status']='pass'
    except Exception as error:
        result.update(status='error',error=repr(error));raise
    finally:
        result['artifacts']={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
        write(out/'result.json',result);print(result['status'],flush=True)


if __name__=='__main__':main()

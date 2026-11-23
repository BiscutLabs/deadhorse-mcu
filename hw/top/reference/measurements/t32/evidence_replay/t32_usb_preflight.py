from pathlib import Path
import json,sys
sys.path.insert(0,'hw/ip/usb')
from evidence import archive_sampling,sampling_evidence,collect
from physical_evidence import collect as physical
root=Path('build/t32/usb-acceptance-inputs01');root.mkdir(exist_ok=False)
old=Path('build/plan03/usb-closure')
archive_sampling(Path('build/t32/usb-sampling-witness01/result.json'),root/'sampling-archive')
sampling=json.loads((old/'sampling-manifest.json').read_text())
sampling['witness']='build/t32/usb-sampling-witness01/result.json'
sampling['witness_archive']=str(root/'sampling-archive/result.json')
(root/'sampling-manifest.json').write_text(json.dumps(sampling,indent=2)+'\n')
for top,folder in [('UsbControl','control'),('UsbEngine','engine'),('Usb','usb')]:
    sources=sorted((old/'lookahead03/emit'/folder).glob('*.sv'))+sorted((old/'lookahead03/emit'/folder).glob('*.v'))
    result=sampling_evidence(root/'sampling-manifest.json',top,sources)
    (root/('sampling-'+top+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    print('sampling',top,result['status'],flush=True)
packet=json.loads((old/'packet-manifest01.json').read_text())
packet['full_size_simulation']='build/t32/usb-fullsize01/result.json'
(root/'packet-manifest.json').write_text(json.dumps(packet,indent=2)+'\n')
result=collect(root/'packet-manifest.json',root/'packet-audit')
print('packet',result['status'],result.get('error',''),flush=True)
assert result['status']=='pass'
result=physical(old/'physical-manifest03.json',old/'lookahead03/emit/usb',root/'physical-audit')
print('physical',result.get('status'),flush=True)
(root/'acceptance-manifest.json').write_text(json.dumps(dict(schema=1,
    packet=str(root/'packet-manifest.json'),sampling=str(root/'sampling-manifest.json'),
    physical=str(old/'physical-manifest03.json')),indent=2)+'\n')
print('PASS unchanged USB collectors; no solver run',flush=True)

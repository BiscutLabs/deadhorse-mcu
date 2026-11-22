"""Bind the proof metadata adapter to the exact audited physical transformation."""
import copy,hashlib,json,sys
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root))
from tools.timing.usb_enable_fanout import identities
base=root/'build/plan03/production-measure06'
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
for mhz in ([int(sys.argv[1])] if len(sys.argv)>1 else (8,9)):
    mapped=base/f'map-{mhz}';proof=base/f'certificate09-{mhz}'
    audit=json.loads((mapped/'transform-audit.json').read_text());assert audit['status']=='pass'
    assert all(digest(p)==h for p,h in audit['source_sha256'].items())
    m=json.loads((mapped/'canonical.json').read_text())['modules']['DeadhorseSoc']
    assert set(audit['inserted_buffers'])=={n for n in m['cells'] if n.startswith('soc_reset_')}
    for name in audit['inserted_buffers']:
        c=m['cells'][name]
        assert c['type']==audit['buffer_type'] and c['parameters']=={}
        assert c['port_directions']=={'I':'input','Z':'output'} and set(c['connections'])=={'I','Z'}
        assert all(len(bs)==1 for bs in c['connections'].values())
    assert len(identities(m))==audit['replicas']>0
    cert=json.loads((proof/'proof/result.json').read_text());assert cert['status']=='pass'
    assert len(cert['enable_replica_equivalence']['identities'])==audit['replicas']
    binding=json.loads((proof/'alias-binding.json').read_text());assert binding['status']=='pass'
    modules=json.loads((mapped/'bound-hier.json').read_text())['modules']
    island=modules[next(n for n in modules if n.split('$')[0]=='Usb')]
    translation={int(a):b for a,b in binding['translation'].items()}
    view=json.loads((proof/'identity-view.json').read_text())['modules']['Usb']
    # Every reconstructed public protocol alias must match its authenticated bit map.
    def validate_aliases(candidate):
        for name,v in island['netnames'].items():
            if name in binding['unrestored_partially_dead_aliases']:continue
            if '$' in name:continue
            # Numeric mapper aliases are intentionally private in the identity view.
            if name.startswith('_') and name.endswith('_') and name[1:-1].isdigit():continue
            expected=[translation[b] if isinstance(b,int) else b for b in v['bits']]
            assert candidate['netnames'][name]['bits']==expected,name
    validate_aliases(view)
    bad=copy.deepcopy(view);bad['netnames']['engine.cadence.count']['bits'][0]='0'
    try:validate_aliases(bad)
    except AssertionError:pass
    else:raise AssertionError('Wrong cadence alias escaped')
    paths=[mapped/'transform-audit.json',mapped/'canonical.json',proof/'identity-view.json',proof/'alias-binding.json',
      proof/'projection.json',proof/'composition.json',proof/'proof/result.json',
      root/'scratch/plan03_production_certificate09.py',root/'scratch/plan03_mapping_audit.py',Path(__file__)]
    (proof/'attestation.json').write_text(json.dumps(dict(status='pass',assumptions=[],
       buffer_inventory='Exact audited insertion list; scalar positive buffer pins and type checked',
       replicas=audit['replicas'],wrong_alias='rejected',source_sha256={str(p):digest(p) for p in paths},
       scope='Metadata adapter, whole-graph transformation and live pin identities; timing acceptance is separate'),indent=2)+'\n')
    print(mhz,'PASS exact transformation/certificate composition and wrong-alias control',flush=True)

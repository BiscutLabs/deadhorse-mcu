"""Reconstruct the full mapping transforms and reject actual connection faults."""
import ast,copy,hashlib,json,sys
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root))
from tools.timing.fanout import buffer_module,verify
from tools.timing.usb_enable_fanout import identities
base=root/'build/plan03/production-measure06'
for mhz in (8,9):
    out=base/f'map-{mhz}';old=json.loads((out/'unbuffered.json').read_text())['modules']['DeadhorseSoc']
    actual=json.loads((out/'mapped.json').read_text())['modules']['DeadhorseSoc']
    primary={b for p in old['ports'].values() if p['direction']=='input' for b in p['bits']}
    clocks={b for c in old['cells'].values() for b in c['connections'].get('CLK',[])}
    resets={b for c in old['cells'].values() for p,bs in c['connections'].items() if p in ('RN','SETN') for b in bs if isinstance(b,int)}-primary
    assert not resets & clocks
    reconstructed,inserted=buffer_module(old,'mainClock',source_bits=resets,prefix='soc_reset_')
    verify(old,reconstructed,inserted)
    for full,short in json.loads((out/'replica-renames.json').read_text()).items():
        c=reconstructed['cells'].pop(full);c['attributes']['usb_enable_original']='subsystem.usb.'+c['attributes']['usb_enable_original']
        reconstructed['cells'][short]=c
    assert reconstructed==actual,'Integrated transform not exactly reproducible'
    assert set(n for n in actual['cells'] if n.startswith('soc_reset_'))==set(inserted)
    count=len(identities(actual));assert count==json.loads((out/'island-preservation.json').read_text())['replicas']>0
    # Run only the pure island checker, not the synthesis script.
    syntax=ast.parse((root/'scratch/plan03_production_map06.py').read_text())
    checker=next(n for n in syntax.body if isinstance(n,ast.FunctionDef) and n.name=='verify_island')
    namespace={'copy':copy,'json':json};exec(compile(ast.Module(body=[checker],type_ignores=[]),'island-checker','exec'),namespace)
    modules=json.loads((out/'bound-hier.json').read_text())['modules'];island=modules[next(n for n in modules if n.split('$')[0]=='Usb')]
    probe=copy.deepcopy(old)
    candidates=[n for n,c in island['cells'].items() if 'D' in c['connections'] and c['connections']['D']!=['0']]
    name='subsystem.usb.'+candidates[0];probe['cells'][name]['connections']['D']=['0']
    try:namespace['verify_island'](island,probe,out/'must-not-exist')
    except AssertionError:pass
    else:raise AssertionError('Wrong island input escaped')
    (out/'transform-audit.json').write_text(json.dumps(dict(status='pass',inserted_buffers=inserted,
       buffer_type='gf180mcu_fd_sc_mcu7t5v0__buf_4',replicas=count,wrong_island_input='rejected',
       source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
         [out/'unbuffered.json',out/'mapped.json',out/'canonical.json',out/'bound-hier.json',out/'replica-renames.json',root/'scratch/plan03_mapping_audit.py']},
       scope='Exact whole-graph transform reconstruction; unchanged input pins recover through only the enumerated inserted buffers'),indent=2)+'\n')
    print(mhz,'PASS full transform reconstruction and wrong-pin fault;',count,'replicas',flush=True)

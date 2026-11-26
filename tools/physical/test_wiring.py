"""T37 functional-mode composition: unchanged children plus top wiring miter.

Re-imports the authenticated old/new emitted models with the same pinned Yosys.
All original child state/logic is structurally matched. Only the newly added
test-access output is fixed inactive, defining functional mode. No functional
child outputs are assumed: they are shared arbitrary miter inputs.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
# Measured binary from the already-pinned oss-cad-suite 2026-11-14 archive in
# tools/env/lock.json. This adds no tool or environment revision.
YOSYS_SHA256 = '7c3e3396b38c129dd7485be5a0a0f0da8e495a94c8fd486059e3bea043a588d6'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def children_equal(a, b):
    seen, renames = set(), []
    def check(x, y, path):
        if (x, y) in seen:
            return
        seen.add((x, y)); left, right = a[x], b[y]
        if left.keys() != right.keys() or left.get('attributes', {}).get('blackbox') != right.get('attributes', {}).get('blackbox'):
            raise ValueError('Changed module structure: ' + path)
        if left.get('attributes',{}).get('blackbox') and x!=y:
            raise ValueError('Changed blackbox identity: '+path)
        if set(left['ports']) != set(right['ports']):
            raise ValueError('Changed ports: ' + path)
        bindings, inverse = {}, {}
        def bits(xs, ys):
            if len(xs) != len(ys):
                raise ValueError('Changed width: ' + path)
            for v, w in zip(xs, ys):
                if isinstance(v, str) or isinstance(w, str):
                    if v != w: raise ValueError('Changed constant: ' + path)
                else:
                    if (v in bindings and bindings[v] != w) or (w in inverse and inverse[w] != v):
                        raise ValueError('Split/merged signal: ' + path)
                    bindings[v], inverse[w] = w, v
        for name, p in left['ports'].items():
            q = right['ports'][name]
            if {k:v for k,v in p.items() if k != 'bits'} != {k:v for k,v in q.items() if k != 'bits'}:
                raise ValueError('Changed port direction/range: ' + path)
            bits(p['bits'], q['bits'])
        rc = dict(right['cells'])
        # Yosys global auto counters shift when new modules precede an old one.
        # Permit only a unique match of the ENTIRE primitive and its pin graph.
        for name in set(left['cells']) - set(rc):
            c = left['cells'][name]
            candidates = [n for n,d in rc.items() if n not in left['cells'] and n.startswith('$auto$') and
                all(c[k] == d[k] for k in ('type', 'parameters', 'port_directions', 'connections'))]
            if not name.startswith('$auto$') or len(candidates) != 1:
                raise ValueError('Unexplained cell mismatch: ' + path + '.' + name)
            renames.append(dict(module=path, old=name, new=candidates[0]))
            rc[name] = rc.pop(candidates[0])
        if set(left['cells']) != set(rc):
            raise ValueError('Added/removed child logic: ' + path)
        for name, c in left['cells'].items():
            d = rc[name]
            if c['parameters'] != d['parameters'] or c['port_directions'] != d['port_directions'] or set(c['connections']) != set(d['connections']):
                raise ValueError('Changed cell semantics: ' + path + '.' + name)
            for pin, value in c['connections'].items(): bits(value, d['connections'][pin])
            if c['type'] in a and d['type'] in b: check(c['type'], d['type'], path + '.' + name)
            elif c['type'] != d['type']: raise ValueError('Changed primitive: ' + path)
        def initial_bits(module, mapping=None):
            result={}
            for net in module['netnames'].values():
                init=net.get('attributes',{}).get('init')
                if init is None: continue
                if len(init)!=len(net['bits']):raise ValueError('Bad initialization width')
                for bit,value in zip(net['bits'],reversed(init)):
                    if mapping is not None:
                        if bit not in mapping:raise ValueError('Unmapped initialized state')
                        bit=mapping[bit]
                    if bit in result and result[bit]!=value:raise ValueError('Conflicting initialization')
                    result[bit]=value
            return result
        if initial_bits(left,bindings)!=initial_bits(right):raise ValueError('Changed initial state: '+path)
        for field in set(left)-{'attributes','ports','cells','netnames'}:
            if left[field]!=right[field]:raise ValueError('Changed module metadata/state field: '+field)
    for name, cell in a['DeadhorseSoc']['cells'].items():
        if not cell['type'].startswith('$'):
            check(cell['type'], b['DeadhorseSoc']['cells'][name]['type'], name)
    return dict(module_pairs=sorted(seen), auto_renames=renames)


def fragment(modules, original_names, candidate=False):
    top = copy.deepcopy(modules['DeadhorseSoc'])
    # Physical supplies are audited as literal top-level connections, not
    # analog quantities in a Boolean SAT miter.
    power = {n:p for n,p in top['ports'].items() if p['direction'] == 'inout'}
    if set(power) != {'vdd', 'vss'}: raise ValueError('Unexpected analog boundary')
    supplies = {}
    for name in original_names:
        cell = top['cells'].pop(name)
        for pin, direction in cell['port_directions'].items():
            bits = cell['connections'][pin]
            if direction == 'inout':
                matches = [n for n,p in power.items() if p['bits'] == bits]
                if len(matches) != 1: raise ValueError('Changed analog supply binding')
                supplies[name + '.' + pin] = matches[0]
            else:
                top['ports']['child_' + name + '__' + pin] = dict(
                    direction='input' if direction == 'output' else 'output', bits=bits)
    for name in power: del top['ports'][name]
    extra = {}
    if candidate:
        replacement = {}
        for name, expected in (('testAccess', {'testMode': 1}), ('scanHooks', {'out': 7})):
            c = top['cells'].pop(name)
            outs = {p:len(v) for p,v in c['connections'].items() if c['port_directions'][p] == 'output'}
            if outs != expected: raise ValueError('Unexpected test-only output')
            for p in expected:
                for bit in c['connections'][p]: replacement[bit] = '0'
        for p in top['ports'].values(): p['bits'] = [replacement.get(v,v) for v in p['bits']]
        for c in top['cells'].values():
            for p,v in c['connections'].items(): c['connections'][p] = [replacement.get(b,b) for b in v]
        kind = top['cells']['testPads']['type']
        extra[kind] = copy.deepcopy(modules[kind])
        if any(c['type'] in modules for c in extra[kind]['cells'].values()):
            raise ValueError('Pad adapter has unexpected child state')
    # Original netnames contain now-unused power aliases and trace names; the
    # circuit is entirely specified by ports, cells and their connections.
    top['netnames'] = {}
    top['attributes'] = {}
    if any(c['type'].startswith(('$dff','$adff','$aldff','$dlatch','$mem')) for c in top['cells'].values()):
        raise ValueError('Top wiring fragment contains unexpected state')
    return top, extra, supplies


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--before',default='build/t43/new02/map')
    p.add_argument('--after',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();r=dict(status='running',commands=[],inputs={},assumptions=['Functional mode: testAccess.testMode=0.'],
        scope='All original hierarchical state/logic and top functional wiring before scan insertion; not post-insertion equivalence or test-mode correctness.')
    executable=Path(shutil.which('yosys') or '/missing-yosys').resolve()
    def run(lines,label):
        script=out/(label+'.ys');script.write_text('\n'.join(lines)+'\n')
        command=[str(executable),'-Q','-T','-s',str(script)];start=time.monotonic()
        with (out/(label+'.log')).open('w') as log:
            try: code=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=120).returncode
            except subprocess.TimeoutExpired:code=124
        r['commands'].append(dict(command=command,seconds=time.monotonic()-start,returncode=code))
        return code
    try:
        lock=ROOT/'tools/env/lock.json'
        if Path('/opt/deadhorse-env/lock.json').read_bytes()!=lock.read_bytes() or sha(executable)!=YOSYS_SHA256:
            raise ValueError('Use authenticated pinned repository environment/Yosys')
        r['tool']=dict(executable=str(executable),sha256=sha(executable),environment_lock_sha256=sha(lock))
        designs=[]
        for label,directory in (('before',ROOT/a.before),('after',ROOT/a.after)):
            receipt=json.loads((directory/'result.json').read_text())
            if receipt['status']!='mapped':raise ValueError('Mapping not complete')
            for name,digest in receipt['input_sha256'].items():
                if sha(ROOT/name)!=digest:raise ValueError('Changed mapping input: '+name)
                r['inputs'][name]=digest
            r['inputs'][str((directory/'result.json').relative_to(ROOT))]=sha(directory/'result.json')
            r['inputs'][str((directory/'analog-interfaces.json').relative_to(ROOT))]=sha(directory/'analog-interfaces.json')
            # Reconstruct the accepted production import, rather than executing
            # arbitrary commands from an unauthenticated generated script.
            lines=(directory/'import.ys').read_text().splitlines()
            cfg=json.loads((ROOT/'phys/gf180-ws-1x1/block-timing.json').read_text())
            if not receipt.get('implemented_rom') or not receipt.get('sram_liberties'):
                raise ValueError('Not the complete production memory configuration')
            expected=[f'read_liberty -lib {ROOT/cfg["liberty"]}']
            expected += [f'read_liberty -lib {ROOT/n}' for n in receipt['sram_liberties']]
            expected += [f'read_json {directory}/analog-interfaces.json',
                'read_slang --keep-hierarchy -DSYNTHESIS -DENABLE_INITIAL_MEM_ --top DeadhorseSoc '+
                    ' '.join(str(ROOT/n) for n in receipt['emitted_sha256']),
                'hierarchy -check -top DeadhorseSoc','proc','chformal -remove','memory_collect',
                f'write_json {directory}/hier.json']
            if lines!=expected:raise ValueError('Import recipe differs from authenticated mapper contract')
            lines[-1]='write_json '+str(out/(label+'.json'))
            r['inputs'][str((directory/'import.ys').relative_to(ROOT))]=sha(directory/'import.ys')
            if run(lines,'import-'+label):raise RuntimeError('Import failed: '+label)
            designs.append(json.loads((out/(label+'.json')).read_text())['modules'])
        old,new=designs
        r['state_correspondence']=children_equal(old,new)
        names=[n for n,c in old['DeadhorseSoc']['cells'].items() if not c['type'].startswith('$')]
        gold,extra_a,pg_a=fragment(old,names)
        gate,extra_b,pg_b=fragment(new,names,True)
        if pg_a!=pg_b:raise ValueError('Changed supply boundary')
        if set(gold['ports'])!=set(gate['ports']):raise ValueError('Changed top observation set')
        base={'modules':dict(gold=gold,gate=gate,**extra_a,**extra_b)}
        r['observed_ports']=sorted(gold['ports']);r['supply_bindings']=pg_a
        for label in ('correct','fault'):
            design=copy.deepcopy(base)
            if label=='fault':
                pin=design['modules']['gate']['ports']['child_digital__coldReset_n']
                pin['bits']=['1']*len(pin['bits'])
            path=out/(label+'.json');path.write_text(json.dumps(design))
            code=run([f'read_json {path}','flatten gold gate','opt_clean',
                'equiv_make gold gate equiv','hierarchy -top equiv','equiv_simple','equiv_status -assert'],label)
            log=(out/(label+'.log')).read_text()
            if label=='correct':
                if code or 'Equivalence successfully proven!' not in log:raise RuntimeError('Wiring equivalence did not close')
            elif code==0 or 'Unproven $equiv' not in log:raise RuntimeError('Wrong reset wiring not rejected')
        # Actual changed functional child D input must also fail state mapping.
        mutated=copy.deepcopy(new)
        victim=next((n,k) for n,m in mutated.items() for k,c in m['cells'].items()
            if c['type'] in ('$adff','$aldff','$dff') and 'D' in c['connections'] and '.digital.' in n)
        c=mutated[victim[0]]['cells'][victim[1]];c['connections']['D']=['1']*len(c['connections']['D'])
        try:children_equal(old,mutated)
        except ValueError as error:r['state_fault']=dict(module=victim[0],cell=victim[1],error=str(error))
        else:raise RuntimeError('Changed child D accepted')
        r['status']='pass'
    except Exception as error:r.update(status='failed',error=repr(error))
    r['seconds']=time.monotonic()-started
    r['script_sha256']=sha(__file__)
    r['artifacts']={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(r,indent=2)+'\n')
    print(r['status'].upper(),r.get('error',''));return 0 if r['status']=='pass' else 1


if __name__=='__main__':
    raise SystemExit(main())

"""D52 same-function sizing of weak USB data/reset buffer branches."""
import copy
import json
from pathlib import Path
import re
import subprocess

LIB = 'gf180mcu_fd_sc_mcu7t5v0__'


def size(module, liberty, output, *, replacements=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    loads = {}
    clocks = set()
    for cell in module['cells'].values():
        clocks.update(cell['connections'].get('CLK', []))
        for pin, direction in cell['port_directions'].items():
            if direction == 'input':
                for bit in cell['connections'][pin]:
                    loads[bit] = loads.get(bit, 0) + 1
    # Exclude the entire positive-buffer ancestry of every actual clock pin.
    while True:
        previous = set(clocks)
        for cell in module['cells'].values():
            if cell['type'].startswith((LIB+'buf_', LIB+'clkbuf_')):
                if any(b in clocks for b in cell['connections'].get('Z', [])):
                    clocks.update(cell['connections']['I'])
        if previous == clocks:
            break
    result = copy.deepcopy(module)
    changed = {}
    library_cells = set(re.findall(r'\bcell\s*\(\s*"?([^\s"()]+)', Path(liberty).read_text()))
    if replacements is not None and (not replacements or not set(replacements)<=set(module['cells'])):
        raise ValueError('Missing explicit sizing cell')
    for name, cell in result['cells'].items():
        family = cell['type'].removeprefix(LIB)
        buffer = family in ('buf_1','clkbuf_1')
        gate = re.fullmatch(r'(?:and[234]|nand[234]|or[234]|nor[234]|aoi(?:21|22|211|221|222)|oai(?:21|22|211|221|222)|mux[24]|inv)_1',family)
        replacement = LIB+'buf_4' if buffer else cell['type'][:-1]+'2'
        if replacements is not None:
            if name not in replacements:continue
            replacement=replacements[name]
            if (not re.fullmatch(r'(?:buf|clkbuf|inv|(?:x?nor|x?or|nand|and)[234]|mux[24]|aoi\d+|oai\d+)_[1248]',family)
                or replacement.rsplit('_',1)[0]!=cell['type'].rsplit('_',1)[0]
                or replacement==cell['type'] or replacement not in library_cells):
                raise ValueError('Explicit sizing must select a characterized same-family combinational cell')
        elif not (buffer or gate) or replacement not in library_cells:continue
        if any(len(bits) != 1 for bits in cell['connections'].values()):
            raise ValueError('Non-scalar USB sizing cell')
        outputs = [p for p,d in cell['port_directions'].items() if d=='output']
        if len(outputs)!=1 or cell.get('parameters'):
            raise ValueError('Unexpected USB combinational sizing cell')
        q = cell['connections'][outputs[0]][0]
        if any(b in clocks for bs in cell['connections'].values() for b in bs):
            if replacements is not None:raise ValueError('Explicit sizing touches clock topology')
            continue
        if replacements is not None or loads.get(q, 0) >= (3 if buffer else 2):
            changed[name] = cell['type']
            cell['type'] = replacement
    recovered = copy.deepcopy(result)
    for name, old in changed.items():
        recovered['cells'][name]['type'] = old
    if recovered != module:
        raise ValueError('USB sizing changed connectivity or state')
    for old in set(changed.values()):
        if len({result['cells'][n]['type'] for n,t in changed.items() if t==old})!=1:
            raise ValueError('One proof per original type requires a unique replacement type')
    proofs = {}
    for old in sorted(set(changed.values())):
        representative = next(n for n,t in changed.items() if t==old)
        template = module['cells'][representative]
        inputs = sorted(p for p,d in template['port_directions'].items() if d=='input')
        out = next(p for p,d in template['port_directions'].items() if d=='output')
        pins = {p:[i+2] for i,p in enumerate(inputs)}
        first, second, equal, fault_bit = range(len(inputs)+2,len(inputs)+6)
        model = {'attributes': {}, 'netnames': {}, 'ports': {
            **{p:{'direction':'input','bits':bits} for p,bits in pins.items()},
            'equal': {'direction': 'output', 'bits': [equal]}}, 'cells': {}}
        for name, kind, q in [('before', old, first), ('after', result['cells'][representative]['type'], second)]:
            model['cells'][name] = {'type': kind, 'parameters': {}, 'attributes': {},
                'port_directions': template['port_directions'],
                'connections': {**pins,out:[q]}}
        model['cells']['eq'] = {'type': '$eq', 'parameters': {
            'A_WIDTH': '1', 'B_WIDTH': '1', 'Y_WIDTH': '1', 'A_SIGNED': '0', 'B_SIGNED': '0'},
            'attributes': {}, 'port_directions': {'A': 'input', 'B': 'input', 'Y': 'output'},
            'connections': {'A': [first], 'B': [second], 'Y': [equal]}}
        for fault in (False, True):
            m = copy.deepcopy(model)
            label = old.removeprefix(LIB) + ('-wrong-polarity' if fault else '-correct')
            if fault:
                m['cells']['after']['connections'][out]=[fault_bit]
                m['cells']['wrong_polarity']={'type':LIB+'inv_1','parameters':{},'attributes':{},
                    'port_directions':{'I':'input','ZN':'output'},'connections':{'I':[fault_bit],'ZN':[second]}}
            source = output/(label+'.json')
            source.write_text(json.dumps({'modules': {'BufferPair': m}}))
            script = output/(label+'.ys')
            script.write_text('\n'.join([f'read_liberty -ignore_miss_func {liberty}',
                f'read_json {source}', 'hierarchy -check -top BufferPair', 'flatten', 'proc',
                'opt_clean', 'check -assert', 'techmap', 'opt',
                'sat -set-def-inputs -prove equal 1 -verify'])+'\n')
            run = subprocess.run(['yosys', '-Q', '-T', '-s', str(script)],
                                 capture_output=True, text=True, timeout=120)
            log = run.stdout+run.stderr
            (output/(label+'.log')).write_text(log)
            valid = (run.returncode == 1 and 'proof did fail' in log) if fault else (run.returncode == 0 and 'SUCCESS!' in log)
            if not valid:
                raise ValueError('USB buffer equivalence/control failed: '+label)
            proofs[label] = 'fault_rejected' if fault else 'proved'
    receipt = dict(cells={n:{'from':old,'to':result['cells'][n]['type']} for n,old in changed.items()}, jobs=proofs,
        policy=('Explicit measured-path cell choices' if replacements is not None else 'Weak positive buffer branches with >=3 loads use buf_4; listed combinational size-1 gates with >=2 loads use same-family size-2'),
        proof='Actual Liberty functions equal for every input; restoring types exactly recovers the input netlist',
        scope=('Explicit T20 mapping experiment' if replacements is not None else 'USB only')+'; actual clock trees excluded; all state, connections and asynchronous reset topology unchanged; pre-layout only')
    (output/'result.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return result, receipt

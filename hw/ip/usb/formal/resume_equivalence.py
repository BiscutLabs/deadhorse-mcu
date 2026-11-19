"""Exact all-state next-transition equivalence for latency-preserving resume edits."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

BASELINE = 'acf8edb090f9ec9cda0c413d3bbbd54da4c6dccf'
BASELINE_EMISSION = {
    'CdcSync.sv':'995560d0c5de442f3789afc7174a2e94bd1a3010805124f1f2d32ae3fef43ae6',
    'UsbResume.sv':'f89a880e2df9af35afd7d4c416beac5db5641a1eb5be15d3536e1402a683ac7c'}


def run(before, after, output):
    root = Path(__file__).resolve().parents[4]
    output = output.resolve(); output.relative_to(root/'build')
    after = after.resolve(); after.relative_to(root/'build')
    if before is not None:
        before = before.resolve(); before.relative_to(root/'build')
    output.mkdir(parents=True, exist_ok=False)
    if before is None:
        source = output/'reference-src'/'UsbResume.scala'
        source.parent.mkdir()
        source.write_bytes(subprocess.check_output(['git','show',BASELINE+':hw/ip/usb/src/main/scala/deadhorse/usb/UsbResume.scala']))
        setting = ('set hw / Compile / unmanagedSources := (hw / Compile / unmanagedSources).value'
                   '.filterNot(_.getName == "UsbResume.scala") :+ file("'+str(source.resolve())+'")')
        with (output/'reference-emit.log').open('w') as log:
            subprocess.run([sys.executable,'tools/sbt.py',setting,
                f'runMain deadhorse.usb.EmitUsb {output}/reference-emit'],
                stdout=log,stderr=subprocess.STDOUT,timeout=600,check=True)
        before = output/'reference-emit'/'resume'
    sources = {label: sorted(directory.glob('*.sv')) for label, directory in [('before', before), ('after', after)]}
    if not all(sources.values()):
        raise ValueError('Both complete emissions are required')
    if {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources['before']} != BASELINE_EMISSION:
        raise ValueError('Resume reference is not the pinned D51 baseline')
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for files in sources.values() for p in files}
    def yosys(name, commands, negative=False):
        script = output/(name+'.ys')
        script.write_text('\n'.join(commands)+'\n')
        result = subprocess.run(['yosys', '-Q', '-T', '-s', str(script)], capture_output=True, text=True, timeout=120)
        log = result.stdout+result.stderr
        (output/(name+'.log')).write_text(log)
        valid = (result.returncode == 1 and 'proof did fail' in log) if negative else result.returncode == 0
        if not valid:
            raise ValueError('Resume equivalence failed: '+name)
        return log
    modules = {}
    registers = {}
    for label, files in sources.items():
        yosys(label, ['read_slang --top UsbResume -DSYNTHESIS '+' '.join(map(str, files)),
            'hierarchy -check -top UsbResume', 'proc', 'flatten', 'opt_clean',
            f'write_json {output}/{label}.json'])
        module = json.loads((output/(label+'.json')).read_text())['modules']['UsbResume']
        modules[label] = module
        regs = {}
        for name, cell in module['cells'].items():
            if 'dff' not in cell['type']:
                continue
            if cell['type'] not in ('$adff', '$aldff', '$dff'):
                raise ValueError('Unexpected resume register '+cell['type'])
            aliases = {n for n, net in module['netnames'].items() if net['bits'] == cell['connections']['Q']}
            regs[name] = (cell, aliases)
        registers[label] = regs
    pairs = []
    remaining = set(registers['after'])
    for name, (cell, aliases) in registers['before'].items():
        matches = [n for n in remaining if aliases & registers['after'][n][1]]
        if len(matches) != 1:
            raise ValueError('Missing/ambiguous resume state binding '+name)
        other = matches[0]
        remaining.remove(other)
        new = registers['after'][other][0]
        if cell['type'] != new['type'] or cell['parameters'] != new['parameters']:
            raise ValueError('Resume clock/reset/state shape changed')
        pairs.append((name, other, sorted(aliases & registers['after'][other][1])))
    if remaining:
        raise ValueError('Additional resume state')
    # Expose every Q as an arbitrary shared input. Compare D and clock/reset
    # functions for every state element, plus all original outputs. No temporal
    # assumption on running, reset or pin synchronizer values is introduced.
    def extract(original, side):
        module = copy.deepcopy(original)
        for index, pair in enumerate(pairs):
            cell = module['cells'].pop(pair[side])
            module['ports']['state_'+str(index)] = dict(direction='input', bits=cell['connections']['Q'])
            for pin, bits in cell['connections'].items():
                if pin != 'Q':
                    module['ports']['next_'+str(index)+'_'+pin] = dict(direction='output', bits=bits)
        return module
    for side, label in enumerate(('before', 'after')):
        (output/(label+'-cut.json')).write_text(json.dumps({'modules': {label: extract(modules[label],side)}}))
    commands = [f'read_json {output}/before-cut.json', f'read_json {output}/after-cut.json',
        'miter -equiv -flatten before after ResumeMiter', 'hierarchy -check -top ResumeMiter',
        'check -assert', 'techmap', 'opt', 'sat -set-def-inputs -prove trigger 0 -verify']
    log = yosys('equivalence', commands)
    if 'SUCCESS!' not in log:
        raise ValueError('Missing completed equivalence proof')
    # Plant an actual next-state fault, not a broken checker: force one carry D
    # high, which must disagree for non-running samples and other count values.
    fault = copy.deepcopy(modules['after'])
    carry = [i for i, p in enumerate(pairs) if 'carries_3' in p[2]]
    if len(carry) != 1:
        raise ValueError('Missing carry fault identity')
    fault['cells'][pairs[carry[0]][1]]['connections']['D'] = ['1']
    (output/'fault-source.json').write_text(json.dumps({'modules': {'UsbResume': fault}}))
    (output/'fault-cut.json').write_text(json.dumps({'modules': {'after': extract(fault,1)}}))
    yosys('wrong-carry', [c.replace('after-cut.json', 'fault-cut.json') for c in commands], negative=True)
    if hashes != {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for files in sources.values() for p in files}:
        raise ValueError('Emission changed during proof')
    receipt = dict(status='pass', source_sha256=hashes, state_bindings=pairs, baseline_commit=BASELINE,
        checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        proof='All-state combinational next-transition equivalence; identical register types, clock polarity and reset values; every clock/reset input function compared',
        jobs={'equivalence': 'proved', 'wrong-carry': 'fault_rejected'})
    (output/'result.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print('PASS resume all-state transition equivalence and carry fault', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, help='Optional pinned D51 emission; otherwise reproduce it from the pinned Git source')
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.before, args.after, args.output)

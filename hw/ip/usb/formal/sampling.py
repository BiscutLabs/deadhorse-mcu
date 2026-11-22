"""Production-engine temporal sampling proofs; no input or traffic assumptions added."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys

from packet_decompose import ROOT, digest, execute, save
from packet_partition import lemma_job

PORTS = {
    'clock': 'clk', 'reset_n': 'control.reset_n', 'ce': 'cadence.enable',
    'busReset': 'control.busReset', 'state': 'control.state',
    'cursor': 'control.cursor', 'total': 'control.total', 'requested': 'control.requested',
    'zlpSent': 'control.zlpSent', 'response': 'control.response', 'configured': 'control.configuredQ',
    **{n: 'control.' + n for n in ('inReady', 'inRequest', 'inAck', 'setup', 'outReady',
       'outValid', 'outError', 'setupCount', 'nextCursor', 'dataRemaining', 'terminalZlp',
       'readComplete', 'inData', 'inValid', 'inZlp', 'stall', 'descriptorLength')},
    'sieReset': 'sie.rstn', 'sieEndpoint': 'sie.endp_q', 'sieState': 'sie.phy_state_q',
    'sieRxReady': 'sie.rx_ready', 'sieTxReady': 'sie.tx_ready', 'sieRxError': 'sie.rx_err',
    'sieInReady': 'sie.in_ready', 'headerType': 'control.header_3',
    'decodeQ': ['control.decodeValueQ', 'control.decodePendingQ', 'control.decodeLengthQ',
                'control.decodeReplyQ', 'control.decodeValidQ'],
    'decodeNow': ['control.decodedValue', 'control.decodedPending', 'control.decodedLength',
                  'control.decodedReply', 'control.decodedValid'],
}
COUNTS = {'lookahead': 4, 'outputs': 4, 'spacing': 3}


def attach(base, monitor, prefix='sampling.'):
    """Append an input-only observer; deletion must recover the exact DUT graph."""
    result = copy.deepcopy(base)
    target = result['modules']['UsbEngine']; observer = monitor['modules']['UsbSampling']
    if set(observer['ports']) != set(PORTS):
        raise ValueError('Unexpected monitor ports')
    if any(c['type'] == '$assume' or
           (c['type'] == '$check' and c['parameters'].get('FLAVOR') not in ('assert', 'cover'))
           for c in observer['cells'].values()):
        raise ValueError('Observer contains assumptions')
    used = {b for n in target['netnames'].values() for b in n['bits'] if isinstance(b, int)}
    used |= {b for c in target['cells'].values() for bs in c['connections'].values() for b in bs if isinstance(b, int)}
    used |= {b for p in target['ports'].values() for b in p['bits'] if isinstance(b, int)}
    next_bit = max(used) + 1; mapping = {}; bindings = {}
    for name, nets in PORTS.items():
        nets = [nets] if isinstance(nets, str) else nets
        bits = [b for n in nets for b in target['netnames'][n]['bits']]
        port = observer['ports'][name]
        if port['direction'] != 'input' or len(port['bits']) != len(bits):
            raise ValueError('Wrong observer binding width/direction: ' + name)
        bindings[name] = dict(nets=nets, bits=bits)
        for a, b in zip(port['bits'], bits):
            if not isinstance(a, int) or (a in mapping and mapping[a] != b):
                raise ValueError('Ambiguous observer binding: ' + name)
            mapping[a] = b
    input_bits = set(mapping); driven = set()
    for cell in observer['cells'].values():
        for pin, bits in cell['connections'].items():
            if cell['port_directions'][pin] != 'output':
                continue
            if any(not isinstance(b, int) or b in input_bits or b in driven for b in bits):
                raise ValueError('Observer drives input or duplicate driver')
            driven.update(bits)
    def translate(bits):
        nonlocal next_bit
        values = []
        for bit in bits:
            if isinstance(bit, int):
                if bit not in mapping:
                    mapping[bit] = next_bit; next_bit += 1
                bit = mapping[bit]
            values.append(bit)
        return values
    added_names = set()
    for name, cell in observer['cells'].items():
        key = prefix + name
        if key in target['cells']:
            raise ValueError('Observer collision')
        added = copy.deepcopy(cell)
        added['connections'] = {p: translate(bs) for p, bs in cell['connections'].items()}
        target['cells'][key] = added
        added_names.add(key)
    projected = copy.deepcopy(result)
    projected['modules']['UsbEngine']['cells'] = {n: c for n, c in target['cells'].items() if n not in added_names}
    if projected != base:
        raise ValueError('Observer changed production transition system')
    return result, bindings


def run(output, regmap, role, portfolio=False):
    output = output.resolve(); output.relative_to(ROOT/'build'); output.mkdir(parents=True, exist_ok=False)
    regmap = regmap.resolve(); regmap.relative_to(ROOT/'build')
    paths = [ROOT/'build.sbt', ROOT/'tools/sbt.py', ROOT/'tools/env/lock.json', regmap,
             Path(__file__), Path(__file__).with_name('UsbSampling.scala'),
             Path(__file__).with_name('packet_partition.py'), Path(__file__).with_name('packet_decompose.py'), ROOT/'tools/formal.py']
    for folder in ('hw/ip/usb/src/main', 'hw/lib/src/main', 'hw/vendor/usb'):
        paths += [p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    bound = {str(p.relative_to(ROOT)): digest(p) for p in paths}
    receipt = dict(status='running', role=role, source_sha256=bound,
                   assumptions=['Initial root reset; all subsequent reset/VBUS/pad/application inputs arbitrary'],
                   cutpoints=[], commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip())
    (output/'runner.py').write_bytes(Path(__file__).read_bytes())
    save(output/'result.json', receipt)
    try:
        command = [sys.executable, 'tools/sbt.py',
                   f'runMain deadhorse.usb.EmitUsb {output}/emit {regmap}',
                   f'runMain deadhorse.usb.EmitUsbSampling {output}/monitor {role}']
        execute(command, output/'emit.log', 600).check_returncode(); receipt['emission_command'] = command
        files = sorted((output/'emit/engine').glob('*.sv')) + sorted((output/'emit/engine').glob('*.v'))
        monfiles = sorted((output/'monitor').glob('*.sv'))
        receipt['emitted_sha256'] = {str(p): digest(p) for p in files + monfiles}
        def prepare(label, top, hdl):
            script = output/(label+'.ys'); model = output/(label+'.json')
            script.write_text('\n'.join(['read_slang --top '+top+' '+' '.join(map(str, hdl)),
                f'prep -top {top} -flatten', f'write_json {model}'])+'\n')
            execute(['yosys', '-Q', '-T', '-s', script], output/(label+'.log')).check_returncode()
            return json.loads(model.read_text())
        base = prepare('production', 'UsbEngine', files)
        if any(c['type'] in ('$assert', '$assume') for c in base['modules']['UsbEngine']['cells'].values()):
            raise ValueError('Unexpected production properties')
        monitor = prepare('observer', 'UsbSampling', monfiles)
        combined, receipt['bindings'] = attach(base, monitor)
        save(output/'combined.json', combined)
        script = output/'canonical.ys'
        script.write_text('\n'.join([f'read_json {output}/combined.json', 'hierarchy -check -top UsbEngine',
            "fminit -seq reset_n 0,'z", 'async2sync', 'chformal -lower', 'opt_clean', 'check -assert',
            f'select -assert-count {COUNTS[role]} t:$assert',
            f'write_json {output}/canonical.json'])+'\n')
        execute(['yosys', '-Q', '-T', '-s', script], output/'canonical.log').check_returncode()
        model = json.loads((output/'canonical.json').read_text())
        receipt['canonical_sha256'] = digest(output/'canonical.json')
        assertions = {n for n, c in model['modules']['UsbEngine']['cells'].items() if c['type'] == '$assert'}
        receipt['positive'] = lemma_job(output/'positive', model, 'UsbEngine', assertions,
                                       engine='abc pdr\nsmtbmc z3' if portfolio else 'smtbmc z3')
        receipt['status'] = 'safety-proved' if receipt['positive']['result'] == 'proved' else 'unresolved'
        # Covers and real DUT faults are separate required qualification, never
        # inferred from successful safety. A safety receipt cannot close the gate.
        receipt['qualification_pending'] = ['Reachable real-traffic covers', 'Real DUT negative controls', 'Independent review']
    except Exception as error:
        receipt.update(status='failed', error=str(error))
    finally:
        if any(digest(ROOT/p) != h for p, h in bound.items()):
            receipt.update(status='failed', error='Sources changed during proof')
        save(output/'result.json', receipt)
    print(receipt['status'].upper()+' USB '+role+' sampling', flush=True)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--regmap', required=True, type=Path)
    parser.add_argument('--role', required=True, choices=COUNTS)
    parser.add_argument('--portfolio', action='store_true', help='One triage portfolio rung; same claims, depth and cap')
    args = parser.parse_args()
    result = run(args.output, args.regmap, args.role, args.portfolio)
    sys.exit(0 if result['status'] == 'safety-proved' else 1)

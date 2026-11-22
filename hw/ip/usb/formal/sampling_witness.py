"""Real-wire witnesses for the exact production-bound sampling predicates.

This emits a simulation-only netlist from the proved graph. Assertion predicates
become observed violation pulses, with their original clock and enable retained.
Neither passing simulation nor rejected faults replaces an unbounded proof.
"""
import argparse
import copy
import json
from pathlib import Path
import re
import sys
import time

from packet_decompose import ROOT, digest, execute, save
from packet_partition import selected_model, lemma_job
from packet_receipt import checked_job
from sampling import attach, COUNTS


def audit(proof, role, output):
    receipt = json.loads(proof.read_text())
    if receipt['status'] != 'safety-proved' or receipt['role'] != role:
        raise ValueError('Missing safety proof')
    for path, expected in receipt['source_sha256'].items():
        source = ROOT / path
        if source.name == 'sampling.py':
            source = proof.parent / 'runner.py'
        if digest(source) != expected:
            raise ValueError('Changed proof source: ' + path)
    for path, expected in receipt['emitted_sha256'].items():
        if digest(path) != expected:
            raise ValueError('Changed emission: ' + path)
    canonical = proof.parent / 'canonical.json'
    if digest(canonical) != receipt['canonical_sha256']:
        raise ValueError('Changed canonical model')
    model = json.loads(canonical.read_text())
    assertions = {n for n, c in model['modules']['UsbEngine']['cells'].items() if c['type'] == '$assert'}
    if len(assertions) != COUNTS[receipt['role']]:
        raise ValueError('Wrong property inventory')
    if checked_job(receipt['positive'], 'proof') != selected_model(model, 'UsbEngine', assertions, set()):
        raise ValueError('Solver model does not match canonical predicates')
    # Never trust unauthenticated intermediate production/observer JSON. Replay
    # imports from authenticated HDL and reproduce the proved canonical graph.
    output.mkdir()
    prepared = {}
    for label, top, part in (('production', 'UsbEngine', '/emit/engine/'),
                             ('observer', 'UsbSampling', '/monitor/')):
        hdl = sorted(Path(p) for p in receipt['emitted_sha256'] if part in p and p.endswith('.sv'))
        hdl += sorted(Path(p) for p in receipt['emitted_sha256'] if part in p and p.endswith('.v'))
        script = output / (label + '.ys')
        script.write_text('read_slang --top ' + top + ' ' + ' '.join(map(str, hdl)) +
            f'\nprep -top {top} -flatten\nwrite_json {output}/{label}.json\n')
        execute(['yosys', '-Q', '-T', '-s', script], output / (label + '.log')).check_returncode()
        prepared[label] = json.loads((output / (label + '.json')).read_text())
    if any(c['type'] in ('$assert', '$assume', '$check')
           for c in prepared['production']['modules']['UsbEngine']['cells'].values()):
        raise ValueError('Unexpected production formal property')
    combined, bindings = attach(prepared['production'], prepared['observer'])
    if bindings != receipt['bindings']:
        raise ValueError('Changed production observer binding')
    save(output / 'combined.json', combined)
    script = output / 'canonical.ys'
    script.write_text(f'read_json {output}/combined.json\nhierarchy -check -top UsbEngine\n'
        "fminit -seq reset_n 0,'z\nasync2sync\nchformal -lower\nopt_clean\ncheck -assert\n"
        f'select -assert-count {COUNTS[role]} t:$assert\nwrite_json {output}/canonical.json\n')
    execute(['yosys', '-Q', '-T', '-s', script], output / 'canonical.log').check_returncode()
    if json.loads((output / 'canonical.json').read_text()) != model:
        raise ValueError('Authenticated HDL does not reproduce proved transition system')
    return receipt, prepared


def instrument(model):
    """Expose the same edge predicates, never substitute a simulation oracle."""
    result = copy.deepcopy(model); module = result['modules']['UsbEngine']
    cells = module['cells']; clock = module['ports']['clk']['bits']
    next_bit = max(b for c in cells.values() for bs in c['connections'].values()
                   for b in bs if isinstance(b, int)) + 1
    outputs = {'violations': [], 'coverage': []}; inventory = {}
    for name, cell in list(cells.items()):
        if cell['type'] != '$check':
            continue
        params = cell['parameters']; pins = cell['connections']
        if (params['FLAVOR'] not in ('assert', 'cover') or pins['TRG'] != clock or
                int(params['TRG_ENABLE'], 2) != 1 or int(params['TRG_POLARITY'], 2) != 1 or
                len(pins['A']) != 1 or len(pins['EN']) != 1):
            raise ValueError('Unsupported clocked predicate: ' + name)
        kind = 'violations' if params['FLAVOR'] == 'assert' else 'coverage'
        a = pins['A']
        if kind == 'violations':
            cells[name + '.not'] = dict(type='$not', hide_name=0, attributes={},
                parameters={'A_SIGNED': 0, 'A_WIDTH': 1, 'Y_WIDTH': 1},
                port_directions={'A': 'input', 'Y': 'output'}, connections={'A': a, 'Y': [next_bit]})
            a = [next_bit]; next_bit += 1
        pulse = next_bit; next_bit += 1
        cells[name + '.pulse'] = dict(type='$and', hide_name=0, attributes={},
            parameters={'A_SIGNED': 0, 'B_SIGNED': 0, 'A_WIDTH': 1, 'B_WIDTH': 1, 'Y_WIDTH': 1},
            port_directions={'A': 'input', 'B': 'input', 'Y': 'output'},
            connections={'A': a, 'B': pins['EN'], 'Y': [pulse]})
        inventory[name] = dict(output=kind, bit=len(outputs[kind]), original=cell)
        outputs[kind].append(pulse); del cells[name]
    if len(outputs['violations']) != 11 or len(outputs['coverage']) != 7:
        raise ValueError('Incomplete predicate inventory')
    for name, bits in outputs.items():
        module['ports'][name] = dict(direction='output', bits=bits)
        module['netnames'][name] = dict(hide_name=0, bits=bits, attributes={})
    # Avoid the Verilog primitive keyword in Chisel's external-module instance.
    # Only the observer fixture port name changes; its bits remain identical.
    module['ports']['pullupOut'] = module['ports'].pop('pullup_0')
    return result, inventory


def mutate(model, fault):
    result = copy.deepcopy(model); module = result['modules']['UsbEngine']
    # A real capture fault: force each pipeline to sample its reset value.
    # Reference predicates and every consumer remain unchanged.
    net = {'lookahead': 'control.nextCursor', 'outputs': 'control.inData',
           'spacing': 'control.decodeLengthQ', 'outputs-phase': 'control.inData',
           'spacing-phase': 'control.decodeLengthQ'}[fault]
    bits = module['netnames'][net]['bits']
    drivers = [(n, c) for n, c in module['cells'].items() if c['connections'].get('Q') == bits]
    if len(drivers) != 1 or drivers[0][1]['type'] != '$aldff':
        raise ValueError('Ambiguous DUT capture fault')
    name, cell = drivers[0]; old = copy.deepcopy(cell)
    if fault.endswith('-phase'):
        first = max(b for c in module['cells'].values() for bs in c['connections'].values()
                    for b in bs if isinstance(b, int)) + 1
        def logic(label, kind, inputs, width=1):
            nonlocal first
            output = list(range(first, first + width)); first += width
            parameters = ({'A_SIGNED':0,'A_WIDTH':1,'Y_WIDTH':1} if kind=='$not' else
                          {'WIDTH':width} if kind=='$mux' else
                          {'A_SIGNED':0,'B_SIGNED':0,'A_WIDTH':1,'B_WIDTH':1,'Y_WIDTH':1})
            module['cells']['fault.'+label] = dict(type=kind,hide_name=0,attributes={},parameters=parameters,
                port_directions={**{n:'input' for n in inputs},'Y':'output'},connections={**inputs,'Y':output})
            return output
        nets=module['netnames']; ready=nets['sie.in_ready' if fault=='outputs-phase' else 'control.outReady']['bits']
        enable=logic('captureEnable','$and',{'A':nets['cadence.enable']['bits'],'B':ready})
        if fault=='outputs-phase':
            enable=logic('byteAccepted','$and',{'A':enable,'B':nets['sie.tx_ready']['bits']})
        if fault=='spacing-phase':
            not_valid=logic('endOfPacket','$not',{'A':nets['control.outValid']['bits']})
            enable=logic('admitPhase','$and',{'A':enable,'B':not_valid})
        cell['connections']['D']=logic('lateCapture','$mux',{'A':old['connections']['Q'],
            'B':old['connections']['D'],'S':enable},len(bits))
    else:
        cell['connections']['D'] = cell['connections']['AD'][:]
    extras=set(module['cells'])-set(model['modules']['UsbEngine']['cells'])
    restored=copy.deepcopy(result);restored['modules']['UsbEngine']['cells'][name]=old
    for added in extras:del restored['modules']['UsbEngine']['cells'][added]
    if restored!=model or {p for p in cell['connections'] if cell['connections'][p]!=old['connections'][p]}!={'D'}:
        raise ValueError('Fault changed anything beyond selected DUT D input')
    return result, dict(register=net, cell=name, before=old, after=cell,
                        added_cells={n:module['cells'][n] for n in sorted(extras)})


def prepare(output, proofs):
    output = output.resolve(); output.relative_to(ROOT / 'build'); output.mkdir(parents=True, exist_ok=False)
    audited = {role: audit(proof, role, output / ('audit-' + role)) for role, proof in proofs.items()}
    receipts = {role: value[0] for role, value in audited.items()}
    paths={p for r in receipts.values() for p in r['source_sha256']}
    paths.update({'hw/ip/usb/formal/sampling_witness.py','hw/ip/usb/formal/packet_receipt.py',
        'hw/ip/usb/src/test/scala/deadhorse/usb/UsbSamplingSpec.scala',
        'hw/ip/usb/src/test/scala/deadhorse/usb/UsbWireHost.scala'})
    sources={p:digest(ROOT/p) for p in paths}
    # Source path attributes vary between emissions; actual production emission
    # must be byte-identical before reusing any monitor binding.
    emissions = [{Path(p).name: h for p, h in r['emitted_sha256'].items() if '/emit/engine/' in p}
                 for r in receipts.values()]
    if any(e != emissions[0] for e in emissions[1:]):
        raise ValueError('Different production emissions')
    model = next(iter(audited.values()))[1]['production']
    for role, proof in proofs.items():
        model, _ = attach(model, audited[role][1]['observer'], role + '.')
    command = [sys.executable, 'tools/sbt.py', f'runMain deadhorse.usb.EmitUsbSampling {output}/covers covers']
    execute(command, output / 'cover-emit.log', 600).check_returncode()
    hdl = sorted((output / 'covers').glob('*.sv'))
    script = output / 'cover.ys'
    script.write_text('read_slang --top UsbSampling ' + ' '.join(map(str, hdl)) +
                      f'\nprep -top UsbSampling -flatten\nwrite_json {output}/covers.json\n')
    execute(['yosys', '-Q', '-T', '-s', script], output / 'cover-model.log').check_returncode()
    model, _ = attach(model, json.loads((output / 'covers.json').read_text()), 'covers.')
    observed, inventory = instrument(model)
    receipt = dict(status='prepared', proofs={str(p): digest(p) for p in proofs.values()},
                   current_source_sha256=sources, configuration=dict(vid=0,pid=0,bulk_packet_bytes=16),
                   predicates=inventory, scenarios={}, qualification='Simulation witnesses, not additional proof')
    for scenario in ('positive', 'lookahead', 'outputs', 'spacing', 'outputs-phase', 'spacing-phase'):
        case = output / scenario; case.mkdir()
        design, mutation = (observed, None) if scenario == 'positive' else mutate(observed, scenario)
        save(case / 'model.json', design)
        script = case / 'emit.ys'
        script.write_text(f'read_json {case}/model.json\nhierarchy -check -top UsbEngine\n'
                          f'techmap\nopt_clean\ncheck -assert\nrename UsbEngine UsbSamplingEngine\n'
                          f'write_verilog -noattr {case}/UsbSamplingEngine.v\n')
        execute(['yosys', '-Q', '-T', '-s', script], case / 'emit.log').check_returncode()
        receipt['scenarios'][scenario] = dict(mutation=mutation, model_sha256=digest(case / 'model.json'),
            hdl=str(case / 'UsbSamplingEngine.v'), hdl_sha256=digest(case / 'UsbSamplingEngine.v'))
    if any(digest(ROOT/p)!=h for p,h in sources.items()):raise ValueError('Sources changed during witness preparation')
    receipt['artifact_sha256']={str(p):digest(p) for p in output.rglob('*') if p.is_file()}
    save(output / 'result.json', receipt)
    save(ROOT / 'build/plan03/usb-sampling-active.json', dict(directory=str(output)))
    (ROOT / 'build/plan03/usb-sampling-active.txt').write_text(str(output))
    return receipt


def simulate(output, receipt):
    command=[sys.executable,'tools/sbt.py','testOnly deadhorse.usb.UsbSamplingSpec']
    before=time.monotonic()
    process=execute(command,output/'simulation.log',600)
    log=(output/'simulation.log').read_text()
    expected={'lookahead':15,'outputs':240,'spacing':1792,'outputs-phase':240,'spacing-phase':1792}
    faults={n:int(v) for n,v in re.findall(r'USB_SAMPLING_FAULT ([\w-]+) violations=(\d+)',log)}
    covers=re.findall(r'USB_SAMPLING_COVER before_reset=(\d+) after_reset=(\d+) reset_release_after_traffic=1',log)
    valid=(process.returncode==0 and 'Tests: succeeded 6, failed 0' in log and 'All tests passed.' in log and
        set(faults)==set(expected) and all(faults[n]&mask for n,mask in expected.items()) and
        len(covers)==1 and int(covers[0][0])&63==63 and int(covers[0][1])&63==63 and
        'USB_SAMPLING_ROOT_RESET after_traffic=1 release=1' in log)
    if any(digest(ROOT/p)!=h for p,h in receipt['current_source_sha256'].items()):valid=False
    if any(digest(p)!=h for p,h in receipt['artifact_sha256'].items()):valid=False
    if (ROOT/'build/plan03/usb-sampling-active.txt').read_text()!=str(output):valid=False
    receipt['simulation']=dict(command=command,returncode=process.returncode,seconds=time.monotonic()-before,
        log_sha256=digest(output/'simulation.log'),faults=faults,cover_masks=covers)
    receipt.update(status='witnesses-pass' if valid else 'failed',
        diagnostic_cover=dict(index=6,status='unresolved',
            meaning='New optional partial-header/new-SETUP coincidence; no safety predicate depends on this conjunction'),
        pending=['Production wrapper binding','Timing exception qualification','Independent final review'])
    save(output/'result.json',receipt)
    print(receipt['status'].upper(),flush=True)
    return valid


def diagnose_abort(output, witness):
    """One bounded-cost attempt to establish whether cover seven is impossible.

    This is a new diagnostic lemma, not a replacement for any sampling assertion.
    The physical engine and all inputs remain real and unrestricted after reset.
    """
    output=output.resolve();output.relative_to(ROOT/'build');output.mkdir(parents=True,exist_ok=False)
    source=witness/'covers.json';base=witness/'audit-lookahead/production.json'
    observer=json.loads(source.read_text());module=observer['modules']['UsbSampling']
    cells=module['cells'];target='cover__cover_6';check=copy.deepcopy(cells[target])
    if check['type']!='$check' or check['parameters']['FLAVOR']!='cover':raise ValueError('Wrong cover')
    for name in list(cells):
        if cells[name]['type']=='$check':del cells[name]
    bit=max(b for c in cells.values() for bs in c['connections'].values() for b in bs if isinstance(b,int))+1
    cells['impossiblePredicate']=dict(type='$not',hide_name=0,attributes={},
        parameters={'A_SIGNED':0,'A_WIDTH':1,'Y_WIDTH':1},port_directions={'A':'input','Y':'output'},
        connections={'A':check['connections']['A'],'Y':[bit]})
    check['parameters']['FLAVOR']='assert';check['connections']['A']=[bit];cells['abortImpossible']=check
    combined,_=attach(json.loads(base.read_text()),observer)
    save(output/'combined.json',combined)
    script=output/'prepare.ys';script.write_text(f'read_json {output}/combined.json\nhierarchy -check -top UsbEngine\n'
        "fminit -seq reset_n 0,'z\nasync2sync\nchformal -lower\nopt_clean\ncheck -assert\n"
        f'select -assert-count 1 t:$assert\nwrite_json {output}/canonical.json\n')
    execute(['yosys','-Q','-T','-s',script],output/'prepare.log').check_returncode()
    model=json.loads((output/'canonical.json').read_text())
    assertions={n for n,c in model['modules']['UsbEngine']['cells'].items() if c['type']=='$assert'}
    row=lemma_job(output/'positive',model,'UsbEngine',assertions,engine='abc pdr\nsmtbmc z3')
    save(output/'result.json',dict(status='diagnostic-only',positive=row,inputs={str(p):digest(p) for p in (source,base,Path(__file__))},
        meaning='Negation of seventh cover on real engine; does not qualify coverage or waive an assertion'))
    print('ABORT COVER DIAGNOSTIC',row['solver_status'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnose-abort',type=Path)
    parser.add_argument('--simulate',action='store_true')
    for role in COUNTS: parser.add_argument('--' + role, type=Path)
    args = parser.parse_args()
    if args.diagnose_abort:
        diagnose_abort(args.output,args.diagnose_abort.resolve())
    else:
        if any(getattr(args,role) is None for role in COUNTS):parser.error('All three proofs are required')
        result=prepare(args.output, {role: getattr(args, role).resolve() for role in COUNTS})
        print('PREPARED exact sampling predicates and real capture faults')
        if args.simulate:sys.exit(0 if simulate(args.output.resolve(),result) else 1)

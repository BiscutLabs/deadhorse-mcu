"""Read-only composition of reviewed D77 digital physical evidence.

The standalone internal timing and separately routed bus-boundary fixture have
distinct placement scopes. This collector never grants chip/analog signoff.
"""
import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'tools/physical'))
sys.path.insert(0, str(ROOT))
from tools.timing import usb_async
from usb_validate import PVTS, RCS, require_complete


def local(value):
    p = Path(value).resolve()
    p.relative_to(ROOT)
    return p


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    with Path(path).open() as stream:
        return list(csv.DictReader(stream, delimiter='\t'))


def finite_nonnegative(value):
    return math.isfinite(float(value)) and float(value) >= 0


def hold_inventory(actual, original, measured):
    expected={(r['check'],r['end']) for r in original if r['check'].startswith('hold/')}
    observed=[(r['check'],r['end']) for r in actual]
    if not expected or len(observed)!=len(set(observed)) or set(observed)!=expected:
        raise ValueError('Incomplete/duplicate contracted hold endpoint inventory')
    if any(not math.isfinite(float(r['slack_ns'])) for r in actual):
        raise ValueError('Nonfinite contracted hold')
    bus=[dict(r,slack_ns=float(r['slack_ns'])) for r in actual if r['start'].startswith('bus_')]
    if not bus or min(bus,key=lambda r:r['slack_ns'])!=measured:
        raise ValueError('Hold table disagrees with measured receipt')


def exact_input_bindings(actual, expected):
    if actual!=expected:
        raise ValueError('Evidence uses a different physical/source input')


def corner_library(bindings,text,name):
    libraries=[local(p) for p in bindings if p.endswith('.lib')]
    if len(libraries)!=1 or libraries[0].name!='gf180mcu_fd_sc_mcu7t5v0__'+name.rsplit('-',1)[0]+'.lib':
        raise ValueError('Wrong or ambiguous asynchronous PVT corner')
    declared=re.findall(r'set liberty \{([^}]+)\}',text)
    if len(declared)!=1 or local(declared[0])!=libraries[0]:
        raise ValueError('Asynchronous driver uses another library')
    return libraries[0]


def hold_driver_inputs(text, physical, name):
    values={key:local(re.search(r'set '+key+r' \{([^}]+)\}',text)[1]) for key in ('netlist','spef')}
    sdc=[local(p) for p in re.findall(r'read_sdc \{([^}]+)\}',text)]
    if len(sdc)!=2:raise ValueError('Wrong hold SDC inventory')
    values.update(base_sdc=sdc[0],boundary_sdc=sdc[1])
    expected=dict(netlist=physical/'routed.v',spef=physical/('extract-'+name.rsplit('-',1)[1])/'routed.spef',
                  base_sdc=physical/'validation'/name/'base.sdc',boundary_sdc=physical/'timing'/name/'boundary.sdc')
    exact_input_bindings(values,expected)
    return values


def collect(manifest_path, emission, output):
    manifest_path = local(manifest_path)
    output = local(output)
    output.relative_to(ROOT/'build')
    output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(manifest_path.read_text())
    if set(manifest) != {'schema', 'physical', 'seal', 'async', 'source', 'hold', 'hold_driver', 'bus'} or manifest['schema'] != 1:
        raise ValueError('Incomplete physical evidence manifest')
    paths = {k: local(v) for k, v in manifest.items() if k != 'schema'}
    for key,p in paths.items():
        p.relative_to(ROOT/'scratch' if key=='hold_driver' else ROOT/'build')
    closure = {str(manifest_path): sha(manifest_path),str(Path(__file__)):sha(Path(__file__))}
    def bind(path):
        path = local(path)
        closure[str(path)] = sha(path)
        return json.loads(path.read_text())
    def hashes(values):
        if not values:
            raise ValueError('Missing evidence hash inventory')
        for name, expected in values.items():
            path = local(name)
            if sha(path) != expected:
                raise ValueError('Stale physical evidence: ' + name)
            closure[str(path)] = expected

    seal = bind(paths['seal'])
    hashes(seal['file_sha256'])
    physical = paths['physical']
    sealed={str(local(p)) for p in seal['file_sha256']}
    required={str(physical/p) for p in ('routed.json','routed.v','inputs.json')}
    if not required<=sealed:raise ValueError('Seal belongs to another/incomplete candidate')
    inputs = bind(physical/'inputs.json')
    actual = {p.name: sha(p) for p in Path(emission).glob('*') if p.suffix in ('.sv', '.v')}
    if actual != inputs['emission_equality']['files']:
        raise ValueError('Routed model differs from fresh production emission')
    for p in Path(emission).glob('*'):
        if p.suffix in ('.sv', '.v'):
            closure[str(p.resolve())] = sha(p)
    if seal['period_setup_violations'] or seal['internal_hold_reset_violations']:
        raise ValueError('Ordinary internal timing fails')
    expected_cases = {p+'-'+r for p in PVTS for r in RCS}
    if len(seal['corners']) != 15 or {c['corner'] for c in seal['corners']} != expected_cases:
        raise ValueError('Incomplete physical corners')
    if any(c['setup_class_failures'] or c['output_violations'] or 'VIOLATED' in c['electrical_report'] for c in seal['corners']):
        raise ValueError('Physical class/output/electrical failure')

    source = bind(paths['source'])
    if source['status'] != 'source-bound-hold-model' or len(source['ports']) != 73:
        raise ValueError('Missing actual production source binding')
    for key in ('source_sha256', 'hdl_sha256', 'artifact_sha256', 'library_sha256'):
        hashes(source[key])
    hold = bind(paths['hold'])
    if hold['status'] != 'hold-only-pass' or hold['binding_sha256'] != sha(paths['source']):
        raise ValueError('Unqualified bus hold contract')
    hashes(hold['artifact_sha256'])
    hashes({str(paths['hold_driver']):hold['source_sha256']})
    hold_cases = {c['corner']: c for c in hold['cases']}
    if len(hold['cases']) != 15 or set(hold_cases) != expected_cases:
        raise ValueError('Missing source hold corner')
    module = json.loads((physical/'routed.json').read_text())['modules']['Usb']
    model_hash = hashlib.sha256(json.dumps(module, sort_keys=True).encode()).hexdigest()
    summaries = []
    for case in seal['corners']:
        name = case['corner']
        raw=physical/'timing'/name/'short_reset_checks.tsv'
        required={str(raw),str(physical/'validation'/name/'corrected-paths.json'),
                  str(physical/'timing'/name/'run.tcl')}
        if not required<=sealed:raise ValueError('Unsealed raw physical timing table')
        result = bind(paths['async']/name/'async-boundary/result.json')
        hashes(result['source_sha256'])
        hashes(result['artifact_sha256'])
        if result['status'] != 'pass' or result['model_sha256'] != model_hash or result['failures']:
            raise ValueError('Unqualified D77 candidate')
        async_text=(paths['async']/name/'timing.tcl').read_text()
        async_inputs=hold_driver_inputs(async_text,physical,name)
        if not {str(p) for p in async_inputs.values()}<=sealed:
            raise ValueError('Unsealed asynchronous timing input')
        liberty = corner_library(result['source_sha256'],async_text,name)
        functions = usb_async.logic_functions(liberty)
        bound = usb_async.inventory(module, 'Usb', functions)
        if bound != result['inventory']:
            raise ValueError('Changed asynchronous pin inventory')
        if usb_async.negative_controls(module, 'Usb', bound, functions) != result['negative_controls']:
            raise ValueError('Missing D77 fault control')
        checks = rows(paths['async']/name/'async-boundary/checks.tsv')
        usb_async.audit_checks(checks, usb_async.expected_checks(bound))
        if any(not finite_nonnegative(r['slack_ns']) for r in checks):
            raise ValueError('D77 downstream/interstage timing fails')
        retained, diagnostics = usb_async.split_violations(case['negative_safety_rows'], result)
        if any(not r['check'].startswith('hold/') or r['start'] not in source['ports'] for r in retained):
            raise ValueError('Non-exempt physical violation remains')
        h = hold_cases[name]
        hold_text=(paths['hold'].parent/name/'timing.tcl').read_text()
        required=hold_driver_inputs(hold_text,physical,name)
        if local(re.search(r'set liberty \{([^}]+)\}',hold_text)[1])!=liberty:
            raise ValueError('Wrong hold PVT corner')
        if not {str(p) for p in required.values()}<=sealed:
            raise ValueError('Unsealed hold timing input')
        pvt = name.rsplit('-', 1)[0]
        expected_min = {p: source['corners'][pvt][r['type']]['min_ns'] for p, r in source['ports'].items()}
        if h['estimated_input_min_ns'] != expected_min or h['status'] != 'pass':
            raise ValueError('Changed source CLK-to-Q contract')
        actual_hold = rows(paths['hold'].parent/name/'hold.tsv')
        require_complete((paths['hold'].parent/name/'run.log').read_text(), 'USB_BUS_HOLD_COMPLETE')
        hold_inventory(actual_hold,rows(raw),h['worst'])
        negatives = [r for r in actual_hold if float(r['slack_ns']) < 0]
        if usb_async.split_violations(negatives, result)[0]:
            raise ValueError('Ordinary contracted hold fails')
        summaries.append(dict(corner=name, status='pass', async_diagnostics=diagnostics,
                              rechecked_bus_boundary=retained, checks=len(checks)))

    # The bus auditor validates every query, actual graph, electrical/annotation
    # and hashes. Its distinct placement scope is retained verbatim.
    with (output/'bus-audit.log').open('w') as log:
        subprocess.run([sys.executable, 'tools/physical/usb_bus_audit.py', '--physical', str(paths['bus']),
                        '--output', str(output/'bus-audit')], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
    bus = bind(paths['bus']/'boundary-result.json')
    for key in ('source_sha256', 'artifact_sha256'):
        hashes(bus[key])
    composition = bind(paths['bus']/'composition.json')
    hashes(composition['input_sha256'])
    composed_inputs={str(local(p)):h for p,h in composition['input_sha256'].items()}
    original=[local(p) for p in inputs['input_sha256'] if p.endswith('/timing/usb/mapped.json')]
    slot=[local(p) for p in source['artifact_sha256'] if p.endswith('/mapped.json')]
    if len(original)!=1 or len(slot)!=1:raise ValueError('Ambiguous production graph inputs')
    expected={str(p):sha(p) for p in [original[0],slot[0],paths['source'],ROOT/'tools/physical/usb_bus_fixture.py']}
    exact_input_bindings(composed_inputs,expected)
    audit = bind(output/'bus-audit/result.json')
    hashes(audit['sha256'])
    if audit['status'] != 'pass':
        raise ValueError('Bus boundary audit failed')
    hashes(dict(closure))
    result = dict(status='pass', corners=summaries, input_sha256=closure,
                  bus_scope=bus['scope'], qualification_limits=[
                      'Standalone USB internal physical timing and separate two-way bus fixture; no combined-placement internal or whole-chip signoff',
                      'Pad/board electrical, analog metastability, reset pulse/glitch characterization and upstream source-control sequencing remain tape-out obligations'],
                  qualification='D77 digital boundary composition only; raw STA negatives retained')
    (output/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'emission', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    collect(args.manifest, args.emission, args.output)
    print('PASS scoped D77 physical evidence; tape-out limits retained')

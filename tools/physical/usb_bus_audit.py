"""Fail-closed audit of the two-way routed USB bus boundary measurement."""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from usb_graph import drivers
from usb_validate import annotation, require_complete, PVTS, RCS

MODES = ('max_rise', 'max_fall', 'min_rise', 'min_fall')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_rows(queries, paths, launches, targets, clocks):
    expected = {(direction, mode, launch) for direction, pins in launches.items()
                for launch in pins for mode in MODES}
    keys = [(q['direction'], q['mode'], q['query']) for q in queries]
    if set(keys) != expected or len(keys) != len(expected):
        raise ValueError('Missing, duplicate or unexpected query')
    grouped = {k: [] for k in expected}
    seen = set()
    for row in paths:
        key = tuple(row[k] for k in ('direction', 'mode', 'query'))
        if key not in expected or row['start'] != row['query']:
            raise ValueError('Wrong launch or query identity')
        if row['end'] not in targets[key[0]] or clocks[row['end']] != 'appClock':
            raise ValueError('Wrong capture direction/domain')
        pair = (*key, row['end'])
        if pair in seen:
            raise ValueError('Duplicate capture endpoint')
        seen.add(pair)
        for name in ('delay_ns', 'slack_ns'):
            if not math.isfinite(float(row[name])):
                raise ValueError('Nonfinite timing result')
        if float(row['slack_ns']) < 0:
            raise ValueError('Boundary setup/hold failure')
        if key[1].startswith('max') and not 0 <= float(row['delay_ns']) <= 24.96:
            raise ValueError('Boundary class delay failure')
        grouped[key].append(row['end'])
    accounts = []
    for query in queries:
        key = tuple(query[k] for k in ('direction', 'mode', 'query'))
        actual = grouped[key]
        if int(query['count']) != len(actual):
            raise ValueError('Query count disagrees with path inventory')
        # The actual Tcl query enumerates every target endpoint, with a cap
        # strictly larger than the complete target set. Record all absences,
        # including inactive/static paths and asynchronous clock-group pairs.
        ordered = targets[key[0]]
        present = set(actual)
        missing = sum(1 << i for i, pin in enumerate(ordered) if pin not in present)
        accounts.append(dict(direction=key[0], mode=key[1], launch=key[2],
                             timed_captures=sorted(present), no_path_bitmap_hex=hex(missing)))
    if any(not any(p['direction'] == d for p in paths) for d in launches):
        raise ValueError('Empty boundary direction')
    return accounts


def target_inventory(model):
    driven = drivers(model)
    def root(bit, seen=()):
        if bit in seen or bit not in driven:
            raise ValueError('Invalid clock tree')
        row = driven[bit]
        if row[0] == 'port':
            return row[1]
        cell = model['cells'][row[1]]
        if not re.fullmatch(r'gf180mcu_fd_sc_mcu7t5v0__(?:clkbuf|buf)_\d+', cell['type']):
            raise ValueError('Unqualified clock tree cell')
        return root(cell['connections']['I'][0], (*seen, bit))
    targets = dict(request=[], response=[])
    clocks = {}
    for name, cell in model['cells'].items():
        if '__dff' not in cell['type']:
            continue
        if set(cell['connections']) not in ({'D', 'Q', 'CLK'}, {'D', 'Q', 'CLK', 'RN'}, {'D', 'Q', 'CLK', 'SETN'}):
            raise ValueError('Unknown sequential cell pins')
        pin = name + '/D'
        targets['response' if name.startswith('source_slot_') else 'request'].append(pin)
        clocks[pin] = root(cell['connections']['CLK'][0])
    return {k: sorted(v) for k, v in targets.items()}, clocks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--physical', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    physical = args.physical.resolve()
    receipt = json.loads((physical/'boundary-result.json').read_text())
    for group in ('source_sha256', 'artifact_sha256'):
        for path, expected in receipt[group].items():
            if sha(path) != expected:
                raise ValueError('Changed measurement input: ' + path)
    if receipt['status'] != 'boundary-pass':
        raise ValueError('Boundary measurement failed')
    model = json.loads((physical/'routed.json').read_text())['modules']['Usb']
    targets, clocks = target_inventory(model)
    launches = json.loads((physical/'graph-audit.json').read_text())['queries']
    if set(launches) != {'request', 'response'} or len(launches['request']) != 73:
        raise ValueError('Wrong launch inventory')
    if any(len(v) != len(set(v)) for v in launches.values()):
        raise ValueError('Duplicate launch')
    for pins in launches.values():
        if any(clocks[p.removesuffix('/Q')+'/D'] != 'appClock' for p in pins):
            raise ValueError('Wrong source clock')
    expected_cases = {c+'-'+r for c in PVTS for r in RCS}
    if {p.name for p in (physical/'boundary-timing').iterdir()} != expected_cases:
        raise ValueError('Missing/extra PVT/RC case')
    if len(receipt['cases']) != 15 or {r['case'] for r in receipt['cases']} != expected_cases:
        raise ValueError('Incomplete measurement receipt')
    args.output.mkdir(parents=True, exist_ok=False)
    cases = []
    for name in sorted(expected_cases):
        case = physical/'boundary-timing'/name
        log = (case/'run.log').read_text()
        require_complete(log, 'USB_BUS_TIMING_COMPLETE')
        if 'VIOLATED' in log:
            raise ValueError('Electrical violation')
        annotated = annotation(log, model)
        # Bind the query shape to its complete, untruncated endpoint inventory.
        script = (case/'run.tcl').read_text()
        exact = 'find_timing_paths -from [get_pins $name] -to [dict get $targets $direction] -path_delay $mode -group_path_count 20000 -endpoint_path_count 1'
        if script.count(exact) != 1 or max(map(len, targets.values())) >= 20000:
            raise ValueError('Incomplete endpoint query shape/cap')
        if 'report_check_types -max_slew -max_capacitance -violators -digits 6' not in script:
            raise ValueError('Missing electrical checks')
        def rows(file):
            with (case/file).open() as stream:
                return list(csv.DictReader(stream, delimiter='\t'))
        accounts = audit_rows(rows('queries.tsv'), rows('paths.tsv'), launches, targets, clocks)
        (args.output/(name+'.json')).write_text(json.dumps(accounts, indent=2)+'\n')
        cases.append(dict(case=name, status='pass', queries=len(accounts), annotation=annotated))
    result = dict(status='pass', scope=receipt['scope'], targets=targets, cases=cases,
                  no_path_encoding='Bit i set means target[i] absent in exhaustive fixed-launch query; includes inactive and asynchronous-group pairs.',
                  sha256={str(p): sha(p) for p in [physical/'boundary-result.json', Path(__file__),
                           *[p for p in args.output.iterdir() if p.is_file()]]})
    (args.output/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS complete two-way bus queries, electrical and connected parasitic coverage')


if __name__ == '__main__':
    main()

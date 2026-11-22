"""Fail-closed logical qualification of explicitly listed drive-strength changes."""
import hashlib
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'timing'))
from usb_boundary import groups

FAMILIES = {'dffrnq', 'nor2', 'nor3', 'oai21', 'oai22', 'oai211',
            'aoi21', 'aoi22', 'aoi211', 'aoi221', 'and3', 'and4', 'or2', 'or3', 'clkinv'}


def family(name):
    match = re.fullmatch(r'gf180mcu_fd_sc_mcu7t5v0__(\w+)_([1248]|16)', name)
    if not match or match[1] not in FAMILIES:
        raise ValueError('Unsupported cell family: ' + name)
    return match[1]


def signature(body):
    for unsupported in ('latch', 'latch_bank', 'ff_bank', 'statetable', 'bus', 'bundle'):
        if list(groups(body, unsupported)):
            raise ValueError('Unsupported cell logic: ' + unsupported)
    if re.search(r'\b(?:is_clock_gating_cell|clock_gating_integrated_cell)\s*:', body):
        raise ValueError('Clock-gating replacements are not permitted')
    pins = {}
    for name, pin in groups(body, 'pin'):
        if name in pins or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name):
            raise ValueError('Duplicate/non-scalar cell pin')
        values = {}
        for attribute in ('direction', 'function', 'three_state', 'clock', 'signal_type'):
            found = re.findall(r'\b' + attribute + r'\s*:\s*("[^"]*"|[^;]+);', pin)
            if len(found) > 1:
                raise ValueError('Ambiguous pin semantics')
            values[attribute] = re.sub(r'\s+', '', found[0]).strip('"') if found else None
        if values['direction'] not in ('input', 'output'):
            raise ValueError('Unsupported pin direction')
        if values['direction'] == 'output' and values['function'] is None:
            raise ValueError('Output function missing')
        pins[name] = values
    ff = [(re.sub(r'\s+', '', name), re.sub(r'\s+', '', value)) for name, value in groups(body, 'ff')]
    if not pins or len(ff) > 1 or ('CLK' in pins) != bool(ff):
        raise ValueError('Missing/ambiguous sequential semantics')
    return dict(pins=pins, ff=ff)


def qualify(before, after, replacements, libraries):
    """No manifest entry is inferred from the candidate being checked."""
    actual = {n for n, c in before['cells'].items()
              if n in after['cells'] and c['type'] != after['cells'][n]['type']}
    if actual != set(replacements) or not libraries:
        raise ValueError('Unauthorized or unused cell replacement')
    views = []
    for path in libraries:
        raw = Path(path).read_bytes(); cells = dict(groups(raw.decode(), 'cell'))
        views.append((str(path), hashlib.sha256(raw).hexdigest(), cells))
    result = {}
    for name, entry in replacements.items():
        old, new = entry['old'], entry['new']
        if (before['cells'][name]['type'] != old or after['cells'][name]['type'] != new or
                family(old) != family(new) or old == new):
            raise ValueError('Replacement identity/family mismatch')
        reference = None
        for path, checksum, cells in views:
            left, right = signature(cells[old]), signature(cells[new])
            if left != right or (reference is not None and left != reference):
                raise ValueError('Replacement changes logical/sequential semantics: ' + name)
            reference = left
        expected = {p: row['direction'] for p, row in reference['pins'].items()}
        for cell in (before['cells'][name], after['cells'][name]):
            if (cell['port_directions'] != expected or
                    set(cell['connections']) != set(expected) or
                    any(len(bits) != 1 for bits in cell['connections'].values())):
                raise ValueError('Mapped pin shape differs from Liberty')
        result[name] = dict(old=old, new=new, signature=reference,
                           libraries={path: checksum for path, checksum, _ in views})
    return result

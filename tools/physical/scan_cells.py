"""Qualify GF180 scan substitutions from authenticated Liberty state equations.

This is an exhaustive primitive transition-relation check, not scan coverage or
timing signoff. Callers must also preserve every functional net connection.
"""
import itertools
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'timing'))
from usb_boundary import groups

PREFIX = 'gf180mcu_fd_sc_mcu7t5v0__'


def without_test_cell(body):
    # test_cell describes functional mode to insertion tools. It is NOT the
    # physical FF equation: do not accidentally qualify against that duplicate.
    matches = list(re.finditer(r'\btest_cell\s*\(\s*\)\s*\{', body))
    if len(matches) > 1:
        raise ValueError('Multiple test_cell groups')
    if not matches:
        return body
    m = matches[0]
    depth, end = 1, m.end()
    while depth and end < len(body):
        depth += (body[end] == '{') - (body[end] == '}')
        end += 1
    if depth:
        raise ValueError('Truncated test_cell')
    return body[:m.start()] + body[end:]


def expression(text, values):
    """Small fail-closed Liberty Boolean interpreter; no Python eval."""
    tokens = re.findall(r'[A-Za-z_][A-Za-z_0-9]*|[01!&|()^]', text)
    if ''.join(tokens) != re.sub(r'\s+', '', text):
        raise ValueError('Unsupported Boolean syntax: ' + text)
    pos = 0
    def atom():
        nonlocal pos
        if pos == len(tokens):
            raise ValueError('Incomplete expression')
        t = tokens[pos]; pos += 1
        if t == '!':
            return not atom()
        if t == '(':
            v = parse(0)
            if pos == len(tokens) or tokens[pos] != ')':
                raise ValueError('Unclosed expression')
            pos += 1
            return v
        if t in ('0', '1'):
            return t == '1'
        if t not in values:
            raise ValueError('Unknown Boolean identifier: ' + t)
        return bool(values[t])
    def parse(level):
        nonlocal pos
        if level == 3:
            return atom()
        v = parse(level + 1)
        op = '|^&'[level]
        while pos < len(tokens) and tokens[pos] == op:
            pos += 1
            rhs = parse(level + 1)
            v = (v or rhs) if op == '|' else ((v != rhs) if op == '^' else (v and rhs))
        return v
    result = parse(0)
    if pos != len(tokens):
        raise ValueError('Trailing expression tokens')
    return result


def model(body):
    body = without_test_cell(body)
    for kind in ('latch', 'latch_bank', 'ff_bank', 'statetable', 'bus', 'bundle'):
        if list(groups(body, kind)):
            raise ValueError('Unsupported cell structure: ' + kind)
    ffs = list(groups(body, 'ff'))
    if len(ffs) != 1 or re.sub(r'\s+', '', ffs[0][0]) != 'IQ1,IQN1':
        raise ValueError('Unsupported state encoding')
    attrs = re.findall(r'\b(\w+)\s*:\s*"([^"]+)"\s*;', ffs[0][1])
    if len(attrs) != len(dict(attrs)):
        raise ValueError('Duplicate FF attribute')
    ff = dict(attrs)
    if set(ff) not in ({'clocked_on', 'next_state'},
                       {'clocked_on', 'next_state', 'clear'},
                       {'clocked_on', 'next_state', 'preset'}):
        raise ValueError('Unsupported asynchronous/state semantics')
    remainder = re.sub(r'\b\w+\s*:\s*"[^"]+"\s*;', '', ffs[0][1])
    if remainder.strip():
        raise ValueError('Unparsed FF attribute')
    pins = {}
    for name, pin in groups(body, 'pin'):
        if name in pins:
            raise ValueError('Duplicate pin')
        direction = re.findall(r'\bdirection\s*:\s*(\w+)\s*;', pin)
        function = re.findall(r'\bfunction\s*:\s*"?([^;"\n]+)"?\s*;', pin)
        if len(direction) != 1 or direction[0] not in ('input', 'output'):
            raise ValueError('Unsupported pin')
        if 'three_state' in pin or (direction[0] == 'output' and len(function) != 1):
            raise ValueError('Unsupported output')
        pins[name] = (direction[0], function[0].strip() if function else None)
    return ff, pins


def qualify(cells, old, new):
    old_short, new_short = old.removeprefix(PREFIX), new.removeprefix(PREFIX)
    m = re.fullmatch(r'(dffq|dffrnq|dffsnq|dffnrnq)_([1248])', old_short)
    if not m:
        raise ValueError('Unapproved original FF: ' + old)
    family = 'sdffrnq' if m[1] == 'dffnrnq' else 's' + m[1]
    if not re.fullmatch(family + r'_[1248]', new_short):
        raise ValueError('Different reset/clock family')
    a, ap = model(cells[old]); b, bp = model(cells[new])
    negative = m[1] == 'dffnrnq'
    renamed = {('CLK' if p == 'CLKN' else p): d for p, d in ap.items()}
    if {p: d for p, d in bp.items() if p not in ('SE', 'SI')} != renamed:
        raise ValueError('Changed functional pin semantics')
    if bp.get('SE') != ('input', None) or bp.get('SI') != ('input', None):
        raise ValueError('Missing scan pins')
    if {p for p, d in ap.items() if d[0] == 'output'} != {'Q'}:
        raise ValueError('Unsupported state output')
    rows = 0
    inputs = sorted(p for p, d in ap.items() if d[0] == 'input') + ['SI', 'IQ1']
    for bits in itertools.product((False, True), repeat=len(inputs)):
        left = dict(zip(inputs, bits)); left['IQN1'] = not left['IQ1']
        right = dict(left, SE=False)
        if negative:
            right['CLK'] = not left['CLKN']
        for attribute in ('clocked_on', 'next_state', 'clear', 'preset'):
            if expression(a.get(attribute, '0'), left) != expression(b.get(attribute, '0'), right):
                raise ValueError('Changed functional ' + attribute)
        if expression(ap['Q'][1], left) != expression(bp['Q'][1], right):
            raise ValueError('Changed state observation')
        right['SE'] = True
        if expression(b['next_state'], right) != left['SI']:
            raise ValueError('Scan mode does not load SI')
        rows += 1
    return dict(old=old, new=new, clock_inversion_required=negative,
                exhaustive_assignments=rows,
                proof='Identical clock-event, next-state, async clear/preset and Q functions with SE=0 and identical IQ state; induction over events preserves state/output. SE=1 loads SI when asynchronous control is inactive. Analog timing excluded.')

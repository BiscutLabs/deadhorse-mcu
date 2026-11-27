"""Reviewed T41 internal-name compatibility for historical USB physical HDL.

Every other byte hash remains exact. This is not a general HDL equivalence
checker: only these three pinned revisions may use the explicit bijections.
"""
import hashlib
from pathlib import Path
import re

PAIRS = {
    'CdcFifo.sv': ('5d236ed84ead587f7168992317e0cff3e5cc55dfb1cea8411839be8166d987d7',
                   '80cf49628b2cf911c36eea5f088939eaaaee7426a4b374c50309ca05050e6e06'),
    'CdcFifo_2.sv': ('72e4be679bbe868fc2a2f1d3c71a820b80bbdf72e56390c74617255386fa50af',
                     'b6156f73b94fd80e56fdc4c4d0ae3fb590dfb686d134f8832b25ec1c6544e930'),
    'RegBlock.sv': ('1fa1e6b5f9bc817db391158fc7cfd12dd6a5932909e19a148a8429a0f649eee6',
                    '0cef17f0760f7e1c4ac9365f878601cca0584ef5975544f70b6e76453e06cd9c'),
}
FIFO_NAMES = {'readReleased': '_rd_released', 'writeReleased': '_wr_released'}
REGISTER_NAMES = {
    'readFields_enable': 'readFields_hw_tx_data_value_we_REG',
    'readFields_value': 'readFields_hw_tx_data_value_wdata_REG',
    'readFields_pulse': 'readFields_hw_command_rx_pop_pulse_REG',
    'readFields_pulse_1': 'readFields_hw_command_wake_ack_pulse_REG',
}
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/|[A-Za-z_$][A-Za-z_0-9$]*|[0-9]+|[^\s]', re.S)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tokens(text):
    return TOKEN.findall(text)


def inverse_names(text, mapping):
    original = tokens(text)
    if len(set(mapping.values())) != len(mapping) or any(n in original for n in mapping.values()):
        raise ValueError('Emission rename collision')
    if any(n not in original for n in mapping):
        raise ValueError('Missing emission rename identity')
    return [mapping.get(token, token) for token in original]


def plain_release_declarations(sequence):
    """Move only two exact scalar, uninitialized declarations to the end."""
    result = list(sequence)
    for name in ('_rd_released', '_wr_released'):
        matches = [i for i in range(len(result)-2) if result[i:i+3] == ['wire', name, ';']]
        if len(matches) != 1:
            raise ValueError('Release declaration changed or ambiguous')
        i = matches[0]
        del result[i:i+3]
    return result + ['wire', '_rd_released', ';', 'wire', '_wr_released', ';']


def verify_text(name, old, current):
    before = tokens(old)
    after = inverse_names(current, FIFO_NAMES if name.startswith('CdcFifo') else REGISTER_NAMES)
    if name.startswith('CdcFifo'):
        before = plain_release_declarations(before)
        after = plain_release_declarations(after)
    if before != after:
        raise ValueError('Emission content changed beyond reviewed names')


def compatible(emission, historical, expected):
    actual = {p.name: digest(p) for p in emission.glob('*') if p.suffix in ('.sv', '.v')}
    if actual.keys() != expected.keys():
        raise ValueError('Physical emission file inventory changed')
    changed = []
    for name, old_hash in expected.items():
        if actual[name] == old_hash:
            continue
        if PAIRS.get(name) != (old_hash, actual[name]):
            raise ValueError('Unreviewed physical emission revision: ' + name)
        old = historical / name
        if digest(old) != old_hash:
            raise ValueError('Historical emission changed: ' + name)
        verify_text(name, old.read_text(), (emission / name).read_text())
        changed.append(dict(file=name, historical_sha256=old_hash, current_sha256=actual[name]))
    return dict(status='compatible', changed=changed,
                qualification='Pinned internal identifiers/declaration order only; no fresh physical measurement')

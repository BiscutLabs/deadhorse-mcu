"""Approved, hash-bound CSR/ID procedural-priority analysis normalization.

Only equivalence preparation uses this module. Production RTL, simulation,
timing and the original pinned source are never rewritten.
"""
import hashlib
from pathlib import Path

from common import VENDOR, adaptation_entry


def normalize_bytes(data, entry, expected_count=2):
    if hashlib.sha256(data).hexdigest() != entry['source_sha256']:
        raise ValueError('CSR priority input hash mismatch')
    lines = data.splitlines(keepends=True)
    original_lines = list(lines)
    edits = entry['edits']
    if expected_count not in (1,2) or len(edits) != expected_count or len({e['line'] for e in edits}) != expected_count:
        raise ValueError('Priority normalization has incorrect edit locations/count')
    for edit in edits:
        index = edit['line'] - 1
        if index < 0 or index >= len(lines) or lines[index] != edit['before'].encode():
            raise ValueError('CSR priority exact location mismatch')
        if edit['before'].replace('unique ', '', 1) != edit['after']:
            raise ValueError('CSR priority edit exceeds qualifier removal')
        lines[index] = edit['after'].encode()
    result = b''.join(lines)
    if hashlib.sha256(result).hexdigest() != entry['normalized_sha256']:
        raise ValueError('CSR priority normalized hash mismatch')
    for edit in edits:
        lines[edit['line'] - 1] = edit['before'].encode()
    if lines != original_lines or b''.join(lines) != data:
        raise ValueError('CSR priority reversal mismatch')
    return result


def analysis_sources(sources, output, label, module):
    """Normalize the pinned reference or its byte-identical harness copy only."""
    result, receipts = list(sources), []
    for key, count, scopes in (
            ('csr_priority',2,('ibex_cs_registers','ibex_core','ibex_top')),
            ('id_priority',1,('ibex_id_stage','ibex_core','ibex_top'))):
        if module not in scopes:
            continue
        entry = adaptation_entry(key)
        for index, name in enumerate(sources):
            path = Path(name)
            if path.name != Path(entry['source']).name:
                continue
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            # A translated candidate is not an upstream source and must not be
            # transformed. A changed pinned source fails closed rather than skipping.
            if path.resolve() != (VENDOR / entry['source']).resolve() and digest != entry['source_sha256']:
                continue
            normalized = normalize_bytes(data, entry, count)
            target = output/'adapted'/label/path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(normalized)
            result[index] = str(target)
            receipts.append(dict(entry, input=str(path), generated=str(target),
                reversed_sha256=hashlib.sha256(data).hexdigest(),
                scope='equivalence analysis only; procedural priority, unrestricted inputs'))
    return result, receipts

"""Strict format-only Liberty rebinding; never rewrite a historical proof receipt."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
COMPARATOR = ROOT / 'phys/gf180-ws-1x1/compare_pdk.py'
spec = importlib.util.spec_from_file_location('pdk_comparison', COMPARATOR)
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


def equal_content(old, new):
    if comparison.normalized(old) != comparison.normalized(new):
        raise ValueError('Liberty tokens changed; no format-only rebind permitted')
    cells = comparison.bodies(old)
    if not cells or cells != comparison.bodies(new):
        raise ValueError('Liberty cell bodies changed or missing')
    return len(cells)


def reference_library(reference, selected):
    reference, selected = Path(reference), Path(selected)
    certificate = reference / 'certificate/result.json'
    cert = json.loads(certificate.read_text())
    timing = reference / 'timing.tcl'
    match = re.findall(r'^set liberty \{([^{}]+)\}$', timing.read_text(), re.M)
    if len(match) != 1:
        raise ValueError('Missing/ambiguous historical Liberty')
    old = Path(match[0]).resolve()
    old.relative_to(ROOT / 'build')
    selected.resolve().relative_to(ROOT / 'build')
    sha = comparison.sha
    if sha(old) != cert['library_sha256']:
        raise ValueError('Historical certificate Liberty hash mismatch')
    from tools.pdk import liberty
    if selected.resolve() != liberty().resolve():
        raise ValueError('Rebind target is not the authenticated active corner')
    if sha(reference / 'mapped.json') != cert['mapped_sha256']:
        raise ValueError('Historical certified map changed')
    count = equal_content(old.read_text(), selected.read_text())
    inputs = [old, selected, certificate, timing, reference / 'mapped.json',
              Path(__file__), COMPARATOR, ROOT / 'tools/timing/usb_boundary.py',
              ROOT / 'tools/pdk.py', ROOT / 'phys/gf180-ws-1x1/pdk-lock.json']
    return dict(status='authenticated_format_only_library_rebind', cells=count,
                original_library_sha256=sha(old), selected_library_sha256=sha(selected),
                input_sha256={str(p.relative_to(ROOT)): sha(p) for p in inputs},
                scope='Original proof/map identities retained; full-library token and cell-body identity only. Current production source binding and fresh STA remain mandatory.')

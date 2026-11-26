"""Normalize the approved common VDD/DVDD and VSS/DVSS physical aliases.

The template logical header ties the rails. OpenDB may choose the IO alias as
the surviving net name; its global-connect stage expects VDD/VSS instead.
Only typed supply terminals and the four named supply boundaries may move.
"""
import argparse
import hashlib
import json
from pathlib import Path
import odb

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--state', required=True)
p.add_argument('--output', required=True)
a = p.parse_args()
state_path, out = [(ROOT / v).resolve() for v in (a.state, a.output)]
out.relative_to(ROOT / 'build')
out.mkdir(parents=True, exist_ok=False)
state = json.loads(state_path.read_text())
source = Path(state['odb'])
db = odb.dbDatabase.create()
odb.read_db(db, str(source))
b = db.getChip().getBlock()


def signals():
    return {(i.getName(), t.getMTerm().getName()): t.getNet().getName() if t.getNet() else None
            for i in b.getInsts() for t in i.getITerms()
            if str(t.getMTerm().getSigType()) not in ('POWER', 'GROUND')}


def validate(net, names, kind):
    assert not net.getSWires() and net.getWire() is None, 'Supply alias already routed'
    assert all(str(t.getMTerm().getSigType()) == kind for t in net.getITerms()), 'Signal consumer on supply'
    assert all(t.getName() in names for t in net.getBTerms()), 'Unknown supply boundary'


before = signals()
rows = []
for names, kind in [(('VDD', 'DVDD'), 'POWER'), (('VSS', 'DVSS'), 'GROUND')]:
    candidates = [b.findNet(n) for n in names if b.findNet(n)]
    assert candidates, names
    for net in candidates:
        validate(net, names, kind)
    fault = b.findInst('i_chip_core.soc.lf').findITerm('clock')
    saved = fault.getNet()
    fault.connect(candidates[0])
    try:
        validate(candidates[0], names, kind)
    except AssertionError:
        pass
    else:
        raise AssertionError('Wrong signal-pin mutation accepted')
    fault.connect(saved)
    target = b.findNet(names[0]) or odb.dbNet.create(b, names[0])
    target.setSigType(kind)
    target.setSpecial()
    moved = []
    for net in candidates:
        if net.getName() == target.getName():
            continue
        for t in list(net.getITerms()):
            moved.append(t.getInst().getName() + '/' + t.getMTerm().getName())
            t.disconnect()
            t.connect(target)
        for t in list(net.getBTerms()):
            t.setSigType(kind)
            t.disconnect()
            t.connect(target)
        assert not net.getITerms() and not net.getBTerms()
        odb.dbNet.destroy(net)
    rows.append(dict(net=names[0], moved=moved))
assert signals() == before, 'Signal graph changed during PG alias normalization'
odb.write_db(db, str(out / 'chip_top.odb'))
odb.write_def(b, str(out / 'chip_top.def'))
state.update(odb=str(out / 'chip_top.odb'), **{'def': str(out / 'chip_top.def')})
(out / 'state.json').write_text(json.dumps(state, indent=2) + '\n')
sha = lambda q: hashlib.sha256(q.read_bytes()).hexdigest()
(out / 'result.json').write_text(json.dumps(dict(status='pass', aliases=rows,
    input_sha256={str(q.relative_to(ROOT)): sha(q) for q in [Path(__file__), state_path, source]},
    artifact_sha256={q.name: sha(q) for q in out.iterdir()},
    negative_controls=['power-signal-pin', 'ground-signal-pin']), indent=2) + '\n')
print('PASS common supply aliases; signal graph unchanged; both signal-pin faults rejected')

"""Exact emission/model witness for the T41 CDC spelling change in packet proofs.

This runs emission and preparation only, never a solver. Historical receipts,
assertions, assumptions, jobs and cover evidence remain immutable. The packet
auditor still checks every original job after validating this witness.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
CDC = 'hw/lib/src/main/scala/deadhorse/lib/Cdc.scala'
OLD_CDC = '536785b7d23d27d493966563980db6bd7933e6f2b706310d7694bb661a03fb3c'
NEW_CDC = '49b8b9c41af7f4aa027e2e83fc51ceb3d060da5cb45dc9a0c5b7e8766a4c8715'
TOP = 'UsbPacketEpochFormal'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def local(path):
    path = Path(path)
    path = (path if path.is_absolute() else ROOT / path).resolve()
    path.relative_to(ROOT)
    return path


def tree(path):
    return {p.relative_to(path).as_posix(): digest(p) for p in sorted(path.rglob('*'))
            if p.suffix in ('.sv', '.v')}


def relocate(value, before, after):
    """Only source-location attributes may have their emission prefix changed."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key == 'attributes' and isinstance(item, dict) and 'src' in item:
                item['src'] = item['src'].replace(str(before) + '/', str(after) + '/')
            relocate(item, before, after)
    elif isinstance(value, list):
        for item in value:
            relocate(item, before, after)


def same_model(fresh, old, before, after):
    candidate = copy.deepcopy(fresh)
    relocate(candidate, before, after)
    relocate(candidate, Path(before).relative_to(ROOT), Path(after).relative_to(ROOT))
    if candidate != old:
        raise ValueError('Packet transition system changed')


def emission_family(row):
    return {Path(p).name: h for p, h in row['emitted_sha256'].items() if '/emit/correct/' in p}


def sources():
    paths = [ROOT / CDC, ROOT / 'build.sbt', ROOT / 'tools/sbt.py',
             ROOT / 'tools/env/lock.json', Path(__file__)]
    for folder, pattern in [('hw/ip/usb', '*.scala'), ('hw/lib', '*.scala'),
                            ('hw/ip/usb/formal', '*.py'), ('project', '*')]:
        paths += [p for p in (ROOT / folder).rglob(pattern)
                  if p.is_file() and 'target' not in p.parts and '__pycache__' not in p.parts]
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(set(paths))}


def compose(base, directory, row):
    from packet_epoch import bind_upper, bind_occupancy
    from packet_remaining import bind_position_monitor
    if not row.get('sparse') or row['role'] != 'out':
        return base
    monitor = read(directory / 'position/canonical.json')
    aliased = copy.deepcopy(base)
    for name in monitor['modules']['UsbOutPositionLemma']['ports']:
        aliased['modules'][TOP]['netnames'][name] = base['modules'][TOP]['netnames']['subject.' + name]
    result = bind_position_monitor(aliased, TOP, monitor)
    result['modules'][TOP]['netnames'] = copy.deepcopy(base['modules'][TOP]['netnames'])
    if row.get('upper'):
        result = bind_upper(result, TOP, read(directory / 'upper/canonical.json'))
    if row.get('occupancy'):
        result = bind_occupancy(result, TOP, read(directory / 'occupancy/canonical.json'))
    return result


def validate(binding, paths, anchors):
    """Fail closed on every dependency, exact model, and receipt-set identity."""
    witness = read(binding)
    if witness['status'] != 'pass' or witness['solver_runs'] != 0:
        raise ValueError('Unqualified CDC binding')
    if witness['source_sha256'] != sources():
        raise ValueError('CDC binding source/compiler inventory changed')
    for p, h in witness['artifact_sha256'].items():
        if digest(local(p)) != h:
            raise ValueError('CDC binding artifact changed: ' + p)
    expected = {str(p.resolve()): digest(p) for p in set(paths + anchors)}
    if witness['receipts'] != expected or set(witness['anchors']) != {str(p.resolve()) for p in anchors}:
        raise ValueError('CDC binding receipt/anchor inventory differs')
    if digest(ROOT / CDC) != NEW_CDC:
        raise ValueError('Unreviewed CDC revision')
    for path in set(paths + anchors):
        row = read(path)
        if row['source_sha256'][CDC] != OLD_CDC:
            raise ValueError('Unreviewed historical CDC revision')
        positive = emission_family(row)
        if not positive:
            raise ValueError('Missing historical positive emission')
        matches = []
        for anchor in anchors:
            candidate = read(anchor)
            if (candidate['role'], candidate['packet_bytes']) != (row['role'], row['packet_bytes']):
                continue
            for part in ('/emit/correct/', '/real-emit/correct/'):
                matches.append({Path(p).name: h for p, h in candidate['emitted_sha256'].items() if part in p})
        if positive not in matches:
            raise ValueError('Receipt has no freshly verified emission family')
    for name, record in witness['anchors'].items():
        old = local(name).parent
        fresh = local(record['directory'])
        row = read(name)
        if digest(old / 'source' / CDC) != OLD_CDC:
            raise ValueError('Historical CDC bytes not authenticated')
        for folder in ('emit', 'real-emit') if row.get('sparse') else ('emit',):
            if not tree(fresh / folder) or tree(fresh / folder) != tree(old / folder):
                raise ValueError('Packet HDL/cover inventory changed')
        for filename, field in [('canonical.json', 'canonical_sha256'), ('real.json', 'real_sha256')]:
            if field not in row:
                continue
            if digest(old / filename) != row[field]:
                raise ValueError('Historical canonical model changed')
            same_model(read(fresh / filename), read(old / filename), fresh, old)
    return {str(binding.resolve()): digest(binding), **witness['artifact_sha256'],
            **{str(ROOT / p): h for p, h in witness['source_sha256'].items()}}


def build(manifest, out):
    from packet_remaining import prepare
    out.mkdir(parents=True, exist_ok=False)
    original = read(manifest)
    paths = [local(p) for p in original['receipts']]
    anchors = [local(p) for p in original['anchors']]
    result = dict(status='running', solver_runs=0, commands=[], source_sha256=sources(),
                  receipts={str(p): digest(p) for p in set(paths + anchors)}, anchors={})
    start = time.monotonic()

    def run(command, log):
        begin = time.monotonic()
        with log.open('w') as stream:
            process = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=600)
        result['commands'].append(dict(command=command, returncode=process.returncode,
                                       seconds=time.monotonic()-begin))
        if process.returncode:
            raise ValueError('Packet emission/preparation failed: ' + str(log))

    try:
        if digest(ROOT / CDC) != NEW_CDC:
            raise ValueError('Unreviewed CDC revision')
        for anchor in anchors:
            old, row = anchor.parent, read(anchor)
            fresh = out / old.name
            fresh.mkdir()
            commands = []
            for folder, kind in [('emit', 'sparse' if row.get('sparse') else 'real')]:
                commands.append(f'runMain deadhorse.usb.EmitUsbPacketEpoch {fresh}/{folder} {row["role"]} {row["packet_bytes"]} {kind}')
            if row.get('sparse'):
                commands.append(f'runMain deadhorse.usb.EmitUsbPacketEpoch {fresh}/real-emit {row["role"]} {row["packet_bytes"]} real')
            monitors = []
            if row.get('sparse') and row['role'] == 'out':
                monitors.append(('position', 'UsbOutPositionLemma', 1))
                if row.get('upper'):
                    monitors.append(('upper', 'UsbEpochOwnership', 1))
                if row.get('occupancy'):
                    monitors.append(('occupancy', 'UsbOutOccupancyLemma', 2))
            for label, top, count in monitors:
                commands.append(f'runMain deadhorse.usb.Emit{top} {fresh}/{label}-emit')
            run([sys.executable, 'tools/sbt.py', *commands], fresh / 'emit.log')
            for label, top, count in monitors:
                if tree(fresh / (label + '-emit')) != tree(old / (label + '-emit')):
                    raise ValueError('Observer HDL changed')
                model, _ = prepare(fresh / label, sorted((fresh / (label + '-emit')).glob('*.sv')), top, count, False)
                same_model(model, read(old / label / 'canonical.json'), fresh, old)
            for source, filename, count in [('emit', 'canonical.json',
                    (29 if row['role'] == 'in' else 27) if row.get('sparse') else (20 if row['role'] == 'in' else 19)),
                    *([('real-emit', 'real.json', 20 if row['role'] == 'in' else 19)] if row.get('sparse') else [])]:
                hdl = sorted((fresh / source / 'correct').glob('*.sv'))
                script = fresh / (source + '.ys')
                script.write_text('\n'.join(['read_slang --top ' + TOP + ' ' + ' '.join(map(str, hdl)),
                    f'prep -top {TOP} -flatten', "fminit -seq reset_n 0,'z", 'async2sync', 'chformal -lower',
                    f'select -assert-count {count} t:$assert', f'write_json {fresh}/{filename}']) + '\n')
                run(['yosys', '-Q', '-T', '-s', str(script)], fresh / (source + '.log'))
                model = compose(read(fresh / filename), fresh, row)
                (fresh / filename).write_text(json.dumps(model) + '\n')
                same_model(model, read(old / filename), fresh, old)
            result['anchors'][str(anchor)] = dict(directory=str(fresh))
        if sources() != result['source_sha256']:
            raise ValueError('Sources changed during emission')
        result['artifact_sha256'] = {str(p): digest(p) for p in out.rglob('*') if p.is_file()}
        result['status'] = 'pass'
    except Exception as error:
        result.update(status='failed', error=str(error))
        raise
    finally:
        result['seconds'] = time.monotonic() - start
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    try:
        validate(out / 'result.json', paths, anchors)
    except Exception as error:
        result.update(status='failed', error=str(error))
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        raise
    print('PASS exact CDC packet binding; zero solver runs')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = local(args.output)
    output.relative_to(ROOT / 'build')
    build(local(args.manifest), output)

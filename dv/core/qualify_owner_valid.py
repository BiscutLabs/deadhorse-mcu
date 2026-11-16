"""Qualify capture ownership reachability and sensitivity without accepting ISA."""
import argparse
import copy
import json
from pathlib import Path
from common import local, output_dir, run
from jalr_invariant import TOP, digest, gate, next_bit, property_cell
from jalr_receipts import verify_hashes, combine_hashes
from check_jalr_ownership import ownership_witness, BINDINGS


def valid_witness(text, fault=False):
    names = {}; values = {}; scope = []; found = []; time = 0
    fields = ('capture', 'ownerValid')
    def sample():
        if not all(n in names and names[n] in values for n in fields): return
        raw = {n: values[names[n]] for n in fields}
        if any(set(v) - set('01') for v in raw.values()): return
        data = {n: int(v, 2) for n, v in raw.items()}
        if data['capture'] and data['ownerValid'] == (0 if fault else 1):
            found.append(dict(time=time, values=data))
    for line in text.splitlines():
        parts = line.split()
        if not parts: continue
        if parts[0] == '$scope': scope.append(parts[2])
        elif parts[0] == '$upscope': scope.pop()
        elif parts[0] == '$var':
            full = '.'.join(scope + [parts[4]])
            for field in fields:
                if full == TOP + '.__ownership_' + field: names[field] = parts[3]
        elif line.startswith('#'): sample(); time = int(line[1:])
        elif line[0] in 'bB' and len(parts) == 2: values[parts[1]] = parts[0][1:]
        elif line[0] in '01xXzZ': values[line[1:]] = line[0]
    sample()
    if not found: raise ValueError('No active owner-valid witness')
    return found[0]


def inject(module, bit, enable):
    drivers = [(n, p, i) for n, c in module['cells'].items()
        for p, d in c['port_directions'].items() if d == 'output'
        for i, b in enumerate(c['connections'][p]) if b == bit]
    if len(drivers) != 1: raise ValueError('Fault requires unique driver')
    n, p, i = drivers[0]; fresh = next_bit(module)
    module['cells'][n]['connections'][p][i] = fresh
    module['cells']['__qualified_fault'] = dict(type='$xor', attributes={},
        parameters=dict(A_WIDTH='1', B_WIDTH='1', Y_WIDTH='1', A_SIGNED='0', B_SIGNED='0'),
        port_directions=dict(A='input', B='input', Y='output'),
        connections=dict(A=[fresh], B=enable, Y=[bit]))
    return [n, p, i]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split', required=True)
    parser.add_argument('--owner', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    split = local(args.split); owner = local(args.owner); out = output_dir(args.output)
    receipt = dict(status='running', scope='capture-valid qualification and full ownership fault only; ISA unresolved', results={})
    protected = {}
    try:
        split_raw = split/'result.json'; owner_raw = owner/'result.json'
        prior = json.loads(split_raw.read_text()); original = json.loads(owner_raw.read_text())
        protected = combine_hashes(prior['input_sha256'], original['input_sha256'])
        for p in (split_raw, owner_raw, Path(__file__), Path(__file__).with_name('check_jalr_ownership.py'),
                  Path(__file__).with_name('jalr_invariant.py'), Path(__file__).with_name('jalr_receipts.py')):
            protected[str(p)] = digest(p)
        verify_hashes(protected)
        positive = prior['results']['owner-valid']
        status_path = split/'owner-valid/work/status'
        if (positive['status'], positive['returncode'], status_path.read_text().split()[0]) != ('PASS', 0, 'PASS'):
            raise ValueError('Capture-valid positive is not proved')
        protected[str(status_path)] = digest(status_path)
        receipt['positive'] = positive
        if (prior['timeout_seconds'], prior['depth']) != (120, 144): raise ValueError('Unexpected proof limits')
        receipt.update(timeout_seconds=120, depth=144, assumptions=prior['assumptions'])
        model = json.loads((split/'owner-valid/model.json').read_text())
        for role in ('cover', 'ghost-valid-fault', 'production-pc-fault'):
            production_fault = role == 'production-pc-fault'
            design = json.loads((owner/'ownership-prove/model.json').read_text()) if production_fault else copy.deepcopy(model)
            m = design['modules'][TOP]
            def net(n): return m['netnames']['__ownership_' + n]['bits']
            assertion = '__ownership_assert' if production_fault else '__ownership_part_owner-valid'
            if role == 'cover':
                m['cells'][assertion] = property_cell('cover', gate(m, '$and', net('capture'), net('ownerValid')))
            elif production_fault:
                receipt[role + '_driver'] = inject(m, m['netnames'][BINDINGS['idPc']]['bits'][2], net('capture'))
            else:
                receipt[role + '_driver'] = inject(m, net('ownerValid')[0], net('capture'))
            job = output_dir(out/role); path = job/'model.json'; path.write_text(json.dumps(design))
            config = job/'check.sby'
            mode = 'cover' if role == 'cover' else 'bmc'
            config.write_text(f'[options]\nmode {mode}\ndepth 144\nmulticlock on\ntimeout 120\n[engines]\nbtor btormc\n[script]\nread_json {path}\nopt_clean\n')
            protected.update({str(p): digest(p) for p in (path, config)})
            verify_hashes(protected)
            result = run(['sby', '-f', '-d', job/'work', config], job, 'check', allowed=(0, 2, 8, 16), timeout=150)
            status_path = job/'work/status'; status = status_path.read_text().split()[0]
            expected = ('PASS', 0) if role == 'cover' else ('FAIL', 2)
            receipt['results'][role] = dict(status=status, returncode=result.returncode, seconds=result.elapsed_seconds)
            if (status, result.returncode) != expected: raise ValueError(role + ': ' + status)
            witnesses = []
            for trace in (job/'work').glob('engine_*/trace*.vcd'):
                try:
                    event = ownership_witness(trace.read_text(), 'ownership-fault') if production_fault else valid_witness(trace.read_text(), role != 'cover')
                    witnesses.append(dict(path=str(trace), sha256=digest(trace), event=event))
                    protected[str(trace)] = digest(trace)
                except ValueError: continue
            if not witnesses: raise ValueError('Missing active witness: ' + role)
            receipt['results'][role]['witnesses'] = witnesses
            protected[str(status_path)] = digest(status_path)
            print(role + ': ' + status, flush=True)
        verify_hashes(protected)
        receipt['status'] = 'pass (capture-valid qualified; full ownership and ISA unresolved)'
    except BaseException as exc:
        receipt.update(status='unresolved', error=str(exc)); raise
    finally:
        receipt['input_sha256'] = protected
        (out/'result.json').write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__': main()

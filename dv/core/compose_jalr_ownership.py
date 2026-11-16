"""Compose authenticated ownership/phase guarantees by exact monitor induction.

All antecedents are explicit Boolean implications, not production assumptions.
The two-frame transition uses the emitted monitor D pins verbatim. Reset is
proved separately from the exact asynchronous reset values. This proves control
ownership only; it does not discharge JALR arithmetic or aggregate ISA checks.
"""
import argparse
import copy
import json
from pathlib import Path
from common import local, output_dir, run
from jalr_invariant import digest, gate
from jalr_receipts import verify_hashes, combine_hashes

MODULE = 'OwnershipComposition'


def conjunction(m, *xs):
    result = ['1']
    for x in xs:
        result = gate(m, '$and', result, x)
    return result


def implies(m, premise, conclusion):
    return gate(m, '$or', gate(m, '$not', premise), conclusion)


def jalr(m, tag):
    if len(tag) != 68:
        raise ValueError('Unexpected phase tag width')
    return conjunction(m, tag[3:4], tag[2:3], gate(m, '$not', tag[1:2]),
        gate(m, '$not', tag[0:1]),
        gate(m, '$eq', tag[36:43], list(reversed(format(0x67, '07b')))),
        gate(m, '$eq', tag[48:51], ['0'] * 3))


def invariant(m, p):
    same = conjunction(m,
        gate(m, '$eq', p['ownerJalr'], jalr(m, p['currentTag'])),
        gate(m, '$eq', p['ownerFirst'], p['idFirst']),
        gate(m, '$eq', p['ownerInstruction'], p['idInstruction']),
        gate(m, '$eq', p['ownerPc'], p['idPc']))
    return implies(m, p['ownerValid'], same)


def check_states(source):
    states = {}
    for name, cell in source['cells'].items():
        if cell['type'] == '$aldff':
            c = cell['connections']; params = cell['parameters']
            if (c['CLK'] != source['ports']['clock']['bits'] or
                c['ALOAD'] != source['ports']['reset']['bits'] or
                int(params['CLK_POLARITY'], 2) != 1 or
                int(params['ALOAD_POLARITY'], 2) != 1 or
                len(c['Q']) != int(params['WIDTH'], 2) or
                any(b not in ('0', '1') for b in c['AD'])):
                raise ValueError('Unrecognized monitor clock/reset semantics')
            for q, d, reset in zip(c['Q'], c['D'], c['AD']):
                if q in states:
                    raise ValueError('Multiple state drivers')
                states[q] = (d, reset)
        elif any(x in cell['type'].lower() for x in ('dff', 'latch', 'mem')):
            raise ValueError('Unsupported monitor state')
        elif cell['type'] in ('$assert', '$assume', '$cover', '$check'):
            raise ValueError('Unexpected property embedded in monitor')
    for port in ('ownerValid', 'ownerJalr', 'ownerFirst', 'ownerInstruction', 'ownerPc', 'previousTag'):
        if not all(q in states for q in source['ports'][port]['bits']):
            raise ValueError('Ownership output is not direct authenticated state: ' + port)
    if source['ports']['currentTag']['bits'] != sum((source['ports'][n]['bits'] for n in
            ('idDummy', 'idCompressed', 'idFirst', 'idValid', 'idPc', 'idInstruction')), []):
        raise ValueError('Phase tag encoding changed')
    return states


def frame(m, source, prefix, state_values=None):
    states = check_states(source)
    all_bits = {b for c in source['cells'].values() for bits in c['connections'].values()
                for b in bits if isinstance(b, int)}
    all_bits |= {b for p in source['ports'].values() for b in p['bits'] if isinstance(b, int)}
    fresh = max([0] + [b for p in m['ports'].values() for b in p['bits'] if isinstance(b, int)] +
                [b for c in m['cells'].values() for bs in c['connections'].values() for b in bs if isinstance(b, int)]) + 1
    mapping = {b: fresh+i for i, b in enumerate(sorted(all_bits))}
    if state_values is not None:
        if set(state_values) != set(states):
            raise ValueError('Incomplete state substitution')
        mapping.update(state_values)
    cv = lambda bits: [mapping.get(b, b) for b in bits]
    for name, p in source['ports'].items():
        if p['direction'] == 'input':
            m['ports'][prefix+name] = dict(direction='input', bits=cv(p['bits']))
    if state_values is None:
        for q in sorted(states):
            m['ports'][prefix+'state_'+str(q)] = dict(direction='input', bits=[mapping[q]])
    for name, c in source['cells'].items():
        if c['type'] == '$aldff':
            continue
        c = copy.deepcopy(c)
        c['connections'] = {p: cv(bits) for p, bits in c['connections'].items()}
        m['cells'][prefix+name] = c
    return {n: cv(p['bits']) for n, p in source['ports'].items()}, mapping


def build(source, role, negative=False):
    source = copy.deepcopy(source)
    states = check_states(source)
    m = dict(attributes={'top':'1'}, ports={}, cells={}, netnames={})
    if role == 'base':
        values = {q: reset for q, (_, reset) in states.items()}
        if negative:
            values[source['ports']['ownerValid']['bits'][0]] = '1'
        p, _ = frame(m, source, 'reset_', values)
        holds = invariant(m, p)
    else:
        p, mapping = frame(m, source, 'before_')
        inv = invariant(m, p)
        if role == 'step':
            values = {q: mapping.get(d, d) for q, (d, _) in states.items()}
            if negative:
                q = source['ports']['ownerJalr']['bits'][0]
                values[q] = gate(m, '$not', [values[q]])[0]
            nxt, _ = frame(m, source, 'after_', values)
            premise = conjunction(m, inv, gate(m, '$not', p['reset']),
                gate(m, '$not', nxt['reset']), p['retentionHolds'], nxt['stabilityHolds'])
            holds = implies(m, premise, invariant(m, nxt))
        elif role == 'final':
            valid = implies(m, p['capture'], p['ownerValid'])
            premise = conjunction(m, inv, valid)
            # Deliberately reverse the owner-JALR conclusion in the negative.
            conclusion = (implies(m, p['capture'], gate(m, '$not', p['ownerJalr']))
                          if negative else p['ownershipHolds'])
            holds = implies(m, premise, conclusion)
        else:
            raise ValueError('Unknown obligation')
    m['ports']['holds'] = dict(direction='output', bits=holds)
    m['netnames'] = {n: dict(bits=p['bits'], attributes={}) for n,p in m['ports'].items()}
    return dict(modules={MODULE:m})


def authenticate(phase, owner, valid, binding):
    paths = [phase/'result.json', phase/'audit.json', owner/'result.json',
             owner.parent/'jalr-ownership-control-audit/control-audit.json',
             valid/'result.json', binding/'result.json',
             valid.parent/'owner-valid-qualified/result.json']
    docs = [json.loads(p.read_text()) for p in paths]
    ph, audit, own, control, va, bound, qualified = docs
    if ph['status'] != 'pass (phase stability only; composition unresolved)' or audit['status'] != 'pass':
        raise ValueError('Unqualified phase premise')
    if audit['receipt_sha256'] != digest(paths[0]):
        raise ValueError('Phase audit mismatch')
    for role in ('write', 'clear', 'step'):
        if any(ph['results'][role+'-'+job]['status'] != status for job,status in
               (('prove','PASS'),('cover','PASS'),('fault','FAIL'))):
            raise ValueError('Phase premise status mismatch')
    if control['status'] != 'pass (control components only)':
        raise ValueError('Unqualified retention premise')
    for role,status in (('retention-prove','PASS'),('retention-cover','PASS'),('retention-fault','FAIL')):
        if own['results'][role]['status'] != status:
            raise ValueError('Retention premise status mismatch')
    if va['results']['owner-valid']['status'] != 'PASS':
        raise ValueError('Capture-valid premise unresolved')
    if qualified['status'] != 'pass (capture-valid qualified; full ownership and ISA unresolved)':
        raise ValueError('Capture-valid active qualification missing')
    if bound['monitor_binding']['status'] != 'proved' or bound['monitor_binding']['negative'] != 'rejected':
        raise ValueError('Inherited monitor binding unresolved')
    protected = combine_hashes(*(d['input_sha256'] for d in docs))
    protected.update({str(p):digest(p) for p in paths})
    # Protect actual proof statuses as well as their recorded claims.
    for directory, jobs in ((phase, ['write-prove','clear-prove','step-prove']),
                            (owner, ['retention-prove']), (valid, ['owner-valid'])):
        for job in jobs:
            jobpath = directory/job
            if directory == owner and own['results'][job].get('reused_from'):
                jobpath = local(own['results'][job]['reused_from'])
            status = jobpath/'work/status'
            if status.read_text().split()[0] != 'PASS':
                raise ValueError('Actual premise status differs')
            protected[str(status)] = digest(status)
    verify_hashes(protected)
    return protected, ph['assumptions']


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--phase', default='build/t13/phase-stability')
    ap.add_argument('--owner', default='build/t13/jalr-ownership-resumed')
    ap.add_argument('--valid', default='build/t13/jalr-ownership-split')
    ap.add_argument('--binding', default='build/t13/jalr-ownership-strengthened')
    ap.add_argument('--output', required=True)
    args = ap.parse_args(); out = output_dir(args.output)
    receipt = dict(status='running', scope='ownership identity composition only; arithmetic and ISA unresolved', results={})
    protected = {}
    try:
        phase,owner,valid,binding = [local(getattr(args,n)) for n in ('phase','owner','valid','binding')]
        protected, assumptions = authenticate(phase,owner,valid,binding)
        source_path = phase/'monitor.json'
        if str(source_path) not in protected:
            raise ValueError('Monitor is not authenticated')
        source = json.loads(source_path.read_text())['modules']['PhaseStabilityProperty']
        for p in (Path(__file__), Path(__file__).with_name('jalr_invariant.py'), Path(__file__).with_name('jalr_receipts.py')):
            protected[str(p)] = digest(p)
        receipt.update(assumptions=assumptions, timeout_seconds=120,
            invariant='ownerValid implies ownerJalr equals current first-phase JALR predicate, and ownerFirst/instruction/PC equal current ID fields',
            antecedents=['exact reset values establish invariant',
                'previous invariant and no reset and proved retention and next phase stability preserve invariant',
                'invariant and capture-implies-ownerValid imply exact ownershipHolds'],
            outstanding='independent review required')
        for role in ('base','step','final'):
            for negative in (False,True):
                name = role+('-negative' if negative else '')
                job = output_dir(out/name); model = job/'model.json'; script = job/'check.ys'
                model.write_text(json.dumps(build(source,role,negative)))
                witness = job/'counterexample.json'
                script.write_text(f'read_json {model}\nhierarchy -top {MODULE}\nopt_clean\ncheck -assert\n'+
                    'sat '+('' if negative else '-verify ')+f'-prove holds 1 -show-inputs -show-outputs -dump_json {witness}\n')
                protected.update({str(p):digest(p) for p in (model,script)})
                verify_hashes(protected)
                result = run(['yosys','-Q','-T','-s',script],job,'check',timeout=120)
                expected = 'SAT proof finished - model found: FAIL!' if negative else 'SAT proof finished - no model found: SUCCESS!'
                if expected not in result.stdout or negative and not witness.exists():
                    raise ValueError('Composition obligation failed: '+name)
                receipt['results'][name] = dict(status='rejected' if negative else 'proved', seconds=result.elapsed_seconds)
                if negative:
                    receipt['results'][name]['witness_sha256'] = digest(witness)
                print('PASS '+name,flush=True)
        verify_hashes(protected)
        receipt['status'] = 'composition proved with qualified premises; independent review pending'
    except BaseException as exc:
        receipt.update(status='unresolved',error=str(exc)); raise
    finally:
        receipt['input_sha256'] = protected
        (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__ == '__main__':
    main()

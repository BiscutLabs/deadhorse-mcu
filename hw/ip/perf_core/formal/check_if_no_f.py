"""Exact IF-stage named-state induction under its explicit no-F fetch condition.

The complete flattened embedded decoders remain in both designs. No child
output abstraction is used. All original outputs, next-state, clocks and reset
semantics are compared; actual decoder inputs are also proved equal without the
condition. This is local conditional equivalence, not core latency refinement.
"""
import argparse
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'dv/core'))
from common import local, output_dir, run
from candidate import parameters
from equiv import elaborate
from state_equiv import prepare, STATE, Mismatch
from jalr_invariant import gate, digest
from jalr_receipts import verify_hashes

MODULE = 'ibex_if_stage'


def no_float(module, instruction):
    if len(instruction) != 32: raise ValueError('Instruction width changed')
    def eq(bits, value): return gate(module, '$eq', bits, list(reversed(format(value, f'0{len(bits)}b'))))
    quadrant = gate(module, '$or', eq(instruction[:2], 0), eq(instruction[:2], 2))
    operation = gate(module, '$or', eq(instruction[13:16], 3), eq(instruction[13:16], 7))
    return gate(module, '$not', gate(module, '$and', quadrant, operation))


def expose(design):
    design = copy.deepcopy(design); m = design['modules'][MODULE]
    instruction = m['netnames']['compressed_decoder_i.instr_i']['bits']
    signals = {'__decoder_input': instruction, '__no_float': no_float(m, instruction),
               '__transfer': m['netnames']['newInstruction']['bits']}
    for name, bits in signals.items():
        if name in m['ports'] or name in m['netnames']: raise ValueError('Reserved name collision')
        m['ports'][name] = dict(direction='output', bits=bits)
        m['netnames'][name] = dict(bits=bits, attributes={})
    return design


def profile(full, baseline):
    full = copy.deepcopy(full); m = full['modules'][MODULE]; b = baseline['modules'][MODULE]
    zeros = {'icache_inval_i', 'dummy_instr_en_i', 'dummy_instr_mask_i',
        'ic_tag_rdata_i', 'pmp_err_if_i', 'icache_enable_i', 'pmp_err_if_plus2_i',
        'nt_branch_addr_i', 'ic_scr_key_valid_i', 'dummy_instr_seed_en_i',
        'dummy_instr_seed_i', 'ic_data_rdata_i', 'nt_branch_mispredict_i'}
    actual = {n for n,p in m['ports'].items() if n not in b['ports'] and p['direction']=='input'}
    if actual != zeros: raise ValueError('Unexpected disabled-feature input inventory')
    replacement = {bit:'0' for n in zeros for bit in m['ports'][n]['bits']}
    def remap(bits): return [replacement.get(bit,bit) for bit in bits]
    for c in m['cells'].values():
        c['connections'] = {n:remap(bits) for n,bits in c['connections'].items()}
    for entries in (m['ports'],m['netnames']):
        for entry in entries.values(): entry['bits'] = remap(entry['bits'])
    for n in zeros: del m['ports'][n]
    for n in list(set(m['ports'])-set(b['ports'])):
        if m['ports'][n]['direction']!='output' or set(m['ports'][n]['bits'])!={'0'}:
            raise ValueError('Extra standalone output is not constant zero: '+n)
        del m['ports'][n]
    for n,source in [('validNext_bore','instr_valid_id_d'),('newNext_bore','newInstruction')]:
        if n in m['ports'] or n not in b['ports']: raise ValueError('Boring output inventory changed')
        bits=m['netnames'][source]['bits']
        m['ports'][n]=dict(direction='output',bits=bits)
        m['netnames'][n]=dict(bits=bits,attributes={})
    if set(m['ports'])!=set(b['ports']): raise ValueError('Profile interface does not retain all baseline ports')
    return full


def mutate(design, role):
    design = copy.deepcopy(design); m = design['modules'][MODULE]
    if role == 'output-fault':
        bits = list(m['ports']['instr_rdata_id_o']['bits'])
        bits[0] = gate(m, '$not', bits[:1])[0]
        m['ports']['instr_rdata_id_o']['bits'] = bits
        m['netnames']['instr_rdata_id_o']['bits'] = bits
    elif role in ('transition-fault', 'reset-fault'):
        q = m['netnames']['instr_valid_id_o' if role == 'reset-fault' else 'instr_rdata_id_o']['bits']
        drivers = [c for c in m['cells'].values() if c['type'] in STATE and c['connections']['Q'] == q]
        if len(drivers) != 1: raise ValueError('Instruction register not unique')
        cell = drivers[0]
        if role == 'transition-fault': cell['connections']['D'][0] = gate(m, '$not', cell['connections']['D'][:1])[0]
        else:
            if cell['type'] != '$aldff': raise ValueError('Unexpected reset form')
            cell['connections']['AD'][0] = '1' if cell['connections']['AD'][0] == '0' else '0'
    else: raise ValueError(role)
    return design


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline', default='build/t13/tagged-baseline')
    ap.add_argument('--candidate', default='build/t13/exponent/candidate')
    ap.add_argument('--output', required=True)
    args = ap.parse_args(); out = output_dir(args.output)
    receipt = dict(status='running', scope='local IF no-F conditional equivalence only', results={})
    protected = {}
    try:
        for d in (args.baseline, args.candidate): parameters(d)
        raw = [elaborate(MODULE, d, out, role) for d, role in
               ((args.baseline, 'baseline'), (args.candidate, 'candidate'))]
        integrated = json.loads(raw[1].read_text())
        emit = output_dir(out/'standalone')
        run([sys.executable, 'tools/sbt.py',
             'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/perf_core/formal")',
             f'hw/runMain deadhorse.perf_core.formal.EmitIfNoF {emit}'], out, 'emit', timeout=120)
        emitted = sorted(emit.glob('*.sv'))
        if not emitted: raise ValueError('Standalone IF emission missing')
        standalone = out/'standalone.json'; emit_script = out/'standalone.ys'
        emit_script.write_text('read_slang --top '+MODULE+' '+' '.join(map(str,emitted))+'\n'+
            f'prep -top {MODULE} -flatten\nmemory_map\nopt_clean\ncheck -assert\nwrite_json {standalone}\n')
        run(['yosys','-Q','-T','-s',emit_script],out,'standalone',timeout=120)
        models = [json.loads(raw[0].read_text()), json.loads(standalone.read_text())]
        for p in [*emitted, emit_script, standalone, Path(__file__).with_name('EmitIfNoF.scala'),
                  *list((ROOT/'hw/ip/perf_core/src/main/scala').rglob('*.scala'))]:
            protected[str(p)] = digest(p)
        for p in raw:
            metadata = json.loads(p.with_suffix('.elaboration.json').read_text())
            if digest(p) != metadata['netlist_sha256']: raise ValueError('Elaboration hash mismatch')
            for name, value in metadata['source_sha256'].items():
                path = local(name)
                if digest(path) != value: raise ValueError('Source changed after elaboration')
                protected[str(path)] = value
            for path in (p, p.with_suffix('.elaboration.json'), p.with_suffix('.ys')):
                protected[str(path)] = digest(path)
        # The baseline IF emission is the one used by the existing tagged T11
        # whole-top equivalence receipt, not a separately guessed configuration.
        baseline_receipt = local('build/t13/baseline-equivalence/result.json')
        prior = json.loads(baseline_receipt.read_text())
        if prior['status'] != 'proved': raise ValueError('Tagged baseline equivalence unresolved')
        baseline_sources = json.loads(raw[0].with_suffix('.elaboration.json').read_text())['source_sha256']
        for name, value in baseline_sources.items():
            if name.startswith(str(local(args.baseline).relative_to(ROOT)) + '/'):
                if prior['elaborations']['gold']['source_sha256'].get(name) != value:
                    raise ValueError('Baseline source differs from tagged equivalence: ' + name)
        for p in (baseline_receipt, Path(__file__), ROOT/'dv/core/state_equiv.py', ROOT/'dv/core/equiv.py',
                  ROOT/'dv/core/jalr_invariant.py', ROOT/'dv/core/jalr_receipts.py',
                  local(args.baseline)/'candidate.json', local(args.candidate)/'candidate.json'):
            protected[str(p)] = digest(p)
        full_profile = out/'profile-raw.json'; full_profile.write_text(json.dumps(profile(models[1],models[0])))
        profiled = out/'profile.json'; profile_ys = out/'profile.ys'
        profile_ys.write_text(f'read_json {full_profile}\nprep -top {MODULE} -flatten\nopt_clean\ncheck -assert\nwrite_json {profiled}\n')
        run(['yosys','-Q','-T','-s',profile_ys],out,'profile',timeout=120)
        models[1]=json.loads(profiled.read_text())
        protected.update({str(p):digest(p) for p in (full_profile,profiled,profile_ys)})
        # First bind every surviving integrated output/state to the full
        # standalone emission. The one compiler-pruned output is retained in
        # the full conditional proof below; only this binding uses the actual
        # integrated interface. It is not a waiver of a baseline output.
        binding = output_dir(out/'integrated-binding')
        full = copy.deepcopy(models[1]); full_m = full['modules'][MODULE]
        actual_m = integrated['modules'][MODULE]
        if set(full_m['ports']) - set(actual_m['ports']) != {'instr_rdata_alu_id_o'}:
            raise ValueError('Unexpected integrated port pruning')
        if not set(actual_m['ports']) <= set(full_m['ports']): raise ValueError('Unexpected new integrated port')
        del full_m['ports']['instr_rdata_alu_id_o']
        raw_binding = binding/'full-raw.json'; raw_binding.write_text(json.dumps(full))
        cleaned = binding/'full.json'; clean_ys = binding/'clean.ys'
        clean_ys.write_text(f'read_json {raw_binding}\nprep -top {MODULE} -flatten\nopt_clean\ncheck -assert\nwrite_json {cleaned}\n')
        run(['yosys','-Q','-T','-s',clean_ys],binding,'clean',timeout=120)
        a,b,correspondence = prepare(cleaned,raw[1],MODULE,binding,{})
        bys = binding/'check.ys'
        bys.write_text(f'read_json {a}\nrename {MODULE} gold\nread_json {b}\nrename {MODULE} gate\n'+
            'miter -equiv -flatten gold gate miter\nhierarchy -top miter\nopt_expr\nopt_merge\nopt_clean\nsat -verify -prove trigger 0\n')
        bresult = run(['yosys','-Q','-T','-s',bys],binding,'check',timeout=120)
        if 'SAT proof finished - no model found: SUCCESS!' not in bresult.stdout: raise ValueError('Integrated binding failed')
        protected.update({str(p):digest(p) for p in (raw_binding,cleaned,clean_ys,a,b,bys)})
        receipt['results']['integrated-binding'] = dict(status='proved',seconds=bresult.elapsed_seconds,
            correspondence=correspondence,projection='Only compiler-pruned instr_rdata_alu_id_o omitted for integrated binding; retained in full baseline comparison')
        bad_binding = binding/'candidate-fault.json'
        mutated = json.loads(b.read_text()); bm=mutated['modules'][MODULE]
        old_bits=list(bm['ports']['instr_rdata_id_o']['bits'])
        old_bits[0]=gate(bm,'$not',old_bits[:1])[0]
        bm['ports']['instr_rdata_id_o']['bits']=old_bits
        bm['netnames']['instr_rdata_id_o']['bits']=old_bits
        bad_binding.write_text(json.dumps(mutated))
        bys_bad=binding/'negative.ys'; bwitness=binding/'negative.json'
        bys_bad.write_text(bys.read_text().replace(str(b),str(bad_binding)).replace(
            'sat -verify -prove trigger 0',f'sat -prove trigger 0 -show-inputs -show-outputs -dump_json {bwitness}'))
        bnegative=run(['yosys','-Q','-T','-s',bys_bad],binding,'negative',timeout=120)
        if 'SAT proof finished - model found: FAIL!' not in bnegative.stdout or not bwitness.is_file():
            raise ValueError('Integrated binding output fault escaped')
        protected.update({str(p):digest(p) for p in (bad_binding,bys_bad,bwitness)})
        receipt['results']['integrated-binding-negative']=dict(status='rejected',seconds=bnegative.elapsed_seconds,
            witness_sha256=digest(bwitness))
        receipt.update(timeout_seconds=120, hypotheses=[
            'Equal named IF state initially; identical reset values, clock and reset semantics checked',
            'At every sampled comparison, fetched decoder input is not a quadrant 0/2 funct3 3/7 encoding (C.FLW/C.FSW/C.FLWSP/C.FSWSP)',
            'All other IF inputs and state unrestricted; decoder input equality also proved unconditionally'],
            method='complete embedded decoder and IF logic; pinned disabled-feature ports specialized to zero and RVFI aliases exposed; no child abstraction or production assumption cells')
        for role in ('normal', 'output-fault', 'transition-fault', 'reset-fault'):
            job = output_dir(out/role)
            pair = [expose(models[0]), expose(models[1] if role == 'normal' else mutate(models[1], role))]
            files = [job/'gold.json', job/'candidate.json']
            for p, model in zip(files, pair): p.write_text(json.dumps(model))
            protected.update({str(p):digest(p) for p in files})
            try:
                gold, candidate, state = prepare(*files, MODULE, job, {})
            except Mismatch as exc:
                if role != 'reset-fault': raise
                receipt['results'][role] = dict(status='rejected', reason=str(exc))
                print('PASS reset-fault rejected by state/reset correspondence', flush=True)
                continue
            if state['multiply_operators'] != 0: raise ValueError('Unexpected IF multiplier cut')
            ys = job/'miter.ys'; miter = job/'miter.json'
            ys.write_text(f'read_json {gold}\nrename {MODULE} gold\nread_json {candidate}\nrename {MODULE} gate\n'
                'miter -equiv -make_outputs -make_outcmp -flatten gold gate miter\nhierarchy -top miter\n'
                f'opt_expr\nopt_merge\nopt_clean\nwrite_json {miter}\n')
            run(['yosys', '-Q', '-T', '-s', ys], job, 'miter', timeout=120)
            design = json.loads(miter.read_text()); m = design['modules']['miter']
            allowed = m['ports']['gold___no_float']['bits']
            conditional = gate(m, '$and', m['ports']['trigger']['bits'], allowed)
            m['ports']['conditional_trigger'] = dict(direction='output', bits=conditional)
            m['netnames']['conditional_trigger'] = dict(bits=conditional, attributes={})
            prepared = job/'conditional.json'; prepared.write_text(json.dumps(design))
            check = job/'check.ys'; witness = job/'counterexample.json'
            check.write_text(f'read_json {prepared}\ncheck -assert\nsat '+(' -verify' if role == 'normal' else '')+
                f' -prove conditional_trigger 0 -show-inputs -show-outputs -dump_json {witness}\n')
            protected.update({str(p):digest(p) for p in (gold,candidate,ys,miter,prepared,check)})
            verify_hashes(protected)
            result = run(['yosys', '-Q', '-T', '-s', check], job, 'check', timeout=120)
            expected = 'SAT proof finished - no model found: SUCCESS!' if role == 'normal' else 'SAT proof finished - model found: FAIL!'
            if expected not in result.stdout: raise ValueError('Conditional proof failed: '+role)
            receipt['results'][role] = dict(status='proved' if role == 'normal' else 'rejected', seconds=result.elapsed_seconds, correspondence=state)
            if role != 'normal':
                if not witness.is_file(): raise ValueError('Mutation witness missing')
                protected[str(witness)] = digest(witness)
            else:
                check2 = job/'input-equality.ys'
                check2.write_text(f'read_json {prepared}\ncheck -assert\nsat -verify -prove cmp___decoder_input 1\n')
                result2 = run(['yosys','-Q','-T','-s',check2],job,'input-equality',timeout=120)
                if 'SAT proof finished - no model found: SUCCESS!' not in result2.stdout: raise ValueError('Decoder input equality unresolved')
                cover = job/'cover.ys'; cover_witness = job/'cover.json'
                cover.write_text(f'read_json {prepared}\ncheck -assert\nsat -set gold___no_float 1 -set gold___transfer 1 '
                    f'-set trigger 0 -show-inputs -show-outputs -dump_json {cover_witness}\n')
                result3 = run(['yosys','-Q','-T','-s',cover],job,'cover',timeout=120)
                if 'SAT solving finished - model found:' not in result3.stdout or not cover_witness.is_file():
                    raise ValueError('No active non-F transfer cover')
                protected.update({str(p):digest(p) for p in (check2,cover,cover_witness)})
                receipt['results']['input-equality'] = dict(status='proved',seconds=result2.elapsed_seconds)
                receipt['results']['active-transfer-cover'] = dict(status='covered',seconds=result3.elapsed_seconds,witness_sha256=digest(cover_witness))
            print('PASS '+role,flush=True)
        verify_hashes(protected)
        receipt['status'] = 'proved (local conditional IF equivalence); independent review pending'
    except BaseException as exc:
        receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected
        (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__ == '__main__': main()

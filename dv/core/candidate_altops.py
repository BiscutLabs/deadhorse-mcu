"""Hash-bound candidate ALTOPS wiring contract; original sources stay intact."""
import hashlib
import json
import re
import sys

from common import ROOT,local,run
from altops import operations


def prepare(output,sources,original,candidate,capture_fault):
    metadata = json.loads((local(candidate)/'formal_adapter.json').read_text())
    if metadata.get('schema') != 1:
        raise ValueError('Unsupported candidate formal adapter schema')
    contract = metadata['multiply_altops']
    data = original.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != contract['source_sha256']:
        raise ValueError('Candidate ALTOPS source hash mismatch')
    signals = contract['signals']
    required = {'mult_en_internal','sva_mul_fsm_idle','mult_valid'}
    if set(signals) != required or any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$]*',v) for v in signals.values()):
        raise ValueError('Candidate ALTOPS requires explicit scalar capture/idle/valid signal names')
    # Tool elaboration checks that each named cutpoint really exists and is
    # scalar, before any generated wiring can create an implicit wire.
    from equiv import elaborate
    parsed = elaborate('ibex_multdiv_fast',candidate,output,'candidate-contract',optimize=False)
    module = json.loads(parsed.read_text())['modules']['ibex_multdiv_fast']
    for name in signals.values():
        if name not in module['netnames'] or len(module['netnames'][name]['bits']) != 1:
            raise ValueError(f'Candidate ALTOPS signal absent/not scalar: {name}')
    text = data.decode()
    matches = list(re.finditer(r'\bassign\s+multdiv_result_o\s*=\s*[^;]+;',text))
    if len(matches) != 1 or any(name in text for name in ('deadhorse_raw_result','deadhorse_alt')):
        raise ValueError('Candidate ALTOPS needs one continuous result driver and fresh adapter names')
    match = matches[0]
    old = match.group()
    ops = operations()
    (output/'operations.tsv').write_text(''.join(f'{name}\t{op}\t{mask:08x}\n' for name,op,mask in ops))
    mode = ' candidate'+(' capture-fault' if capture_fault else '')
    run([sys.executable,'tools/sbt.py','set hw / Compile / unmanagedSourceDirectories += file("/work/dv/core")',
         f'hw/runMain deadhorse.reference.EmitMultiplyAltop {output}{mode}'],output,'emit-altops')
    names = ['clk_i','rst_ni','mult_en_internal','sva_mul_fsm_idle','mult_sel_i',
             'mult_valid','multdiv_ready_id_i','op_a_i','op_b_i','operator_i','signed_mode_i','div_sel_i']
    connections = [f'.{name}({signals.get(name,name)})' for name in names]
    connections += ['.real_result_i(deadhorse_raw_result)','.result(multdiv_result_o)']
    # The original RHS is unchanged. All new selection/capture/assertion logic
    # is emitted Chisel; this generated text is declarations and wiring only.
    new = ('`ifdef RISCV_FORMAL_ALTOPS\nwire [31:0] deadhorse_raw_result;\n'+
           old.replace('multdiv_result_o','deadhorse_raw_result',1)+'\n'+
           'DeadhorseMultiplyAltop deadhorse_alt ('+', '.join(connections)+');\n'+
           '`else\n'+old+'\n`endif')
    changed = text[:match.start()]+new+text[match.end():]
    if changed.replace(new,old,1) != text:
        raise ValueError('Candidate ALTOPS reversal failed')
    target = output/'ibex_multdiv_fast.sv'
    target.write_text(changed)
    (output/'adaptation.json').write_text(json.dumps(dict(id='D44-candidate-multiply-altops',
        original_sha256=digest,adapted_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        removed=old,inserted=new,signals=signals,capture_fault=capture_fault,
        emitted_sha256=hashlib.sha256((output/'DeadhorseMultiplyAltop.sv').read_bytes()).hexdigest()),indent=2)+'\n')
    return [str(target) if str(p)==str(original) else str(p) for p in sources]+[str(output/'DeadhorseMultiplyAltop.sv')]

"""D44 generated-copy adapter; all new RTL logic is emitted from Chisel."""
import hashlib
import json
import re
import sys

from common import CONFIG, ROOT, VENDOR, output_dir, run

MULTIPLY = ('mul', 'mulh', 'mulhsu', 'mulhu')


def operations():
    result = []
    for name in MULTIPLY:
        data = (VENDOR / f'riscv-formal/insns/insn_{name}.v').read_text()
        section = data.split('`ifdef RISCV_FORMAL_ALTOPS\n')[1].split('`else')[0]
        mask = re.findall(r"altops_bitmask = 64'h([0-9a-f]+);", section)
        operator = re.findall(r'result = \(rvfi_rs1_rdata ([+-]) rvfi_rs2_rdata\) \^ altops_bitmask;', section)
        if len(mask) != 1 or len(operator) != 1:
            raise ValueError(f'Unsupported pinned ALTOPS model: {name}')
        result.append((name, operator[0], int(mask[0], 16) & 0xffffffff))
    return result


def prepare(output, sources, capture_fault=False):
    if str(CONFIG['parameters']['RV32M']) != '2':
        raise ValueError('D44 capture contract only supports RV32MFast')
    output = output_dir(output)
    adaptation = json.loads((ROOT/'dv/core/adaptations.json').read_text())['multiply_altops']
    original = VENDOR / adaptation['source']
    data = original.read_bytes()
    if hashlib.sha256(data).hexdigest() != adaptation['source_sha256']:
        raise ValueError('Multiply adaptation input hash mismatch')
    old = adaptation['replace'].encode()
    if data.count(old) != 1:
        raise ValueError('Multiply result assignment must match exactly once')
    ops = operations()
    (output/'operations.tsv').write_text(''.join(f'{name}\t{op}\t{mask:08x}\n' for name, op, mask in ops))
    mode = ' capture-fault' if capture_fault else ''
    run([sys.executable, 'tools/sbt.py', 'set hw / Compile / unmanagedSourceDirectories += file("/work/dv/core")',
         f'hw/runMain deadhorse.reference.EmitMultiplyAltop {output}{mode}'], output, 'emit-altops')
    # Generated instance wiring only; arithmetic/capture/assertion logic comes
    # exclusively from MultiplyAltop.scala. Reference control is not replaced.
    names = ['clk_i', 'rst_ni', 'mult_en_internal', 'sva_mul_fsm_idle', 'mult_sel_i',
             'mult_valid', 'multdiv_ready_id_i', 'op_a_i', 'op_b_i', 'operator_i', 'signed_mode_i']
    connections = [f'.{name}({name})' for name in names] + ['.result(deadhorse_alt_result)']
    wiring = '  wire [31:0] deadhorse_alt_result;\n  DeadhorseMultiplyAltop deadhorse_alt (' + ', '.join(connections) + ');\n'
    replaced = old.decode().replace('mac_res_d[31:0]', 'deadhorse_alt_result')
    replacement = ('`ifdef RISCV_FORMAL_ALTOPS\n' + wiring + replaced +
                   '`else\n' + old.decode() + '`endif\n').encode()
    changed = data.replace(old, replacement, 1)
    target = output/'ibex_multdiv_fast.sv'
    target.write_bytes(changed)
    (output/'adaptation.json').write_text(json.dumps(dict(id=adaptation['id'],
        original_sha256=adaptation['source_sha256'], adapted_sha256=hashlib.sha256(changed).hexdigest(),
        removed=old.decode(), inserted=replacement.decode(), operations=ops, capture_fault=capture_fault,
        emitted_sha256=hashlib.sha256((output/'DeadhorseMultiplyAltop.sv').read_bytes()).hexdigest()), indent=2)+'\n')
    return [str(target) if str(p) == str(original) else str(p) for p in sources] + [str(output/'DeadhorseMultiplyAltop.sv')]

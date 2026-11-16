"""Hash-bound D44 result abstraction for the registered multiplier only."""
import hashlib
import json
from pathlib import Path
import re
import sys

from common import local,run
from candidate import parameters,manifest
from altops import operations


def prepare(output,sources,candidate,capture_fault):
    parameters(candidate)
    data=manifest(candidate)
    if data.get('implementation')!='registered-execution-v1': raise ValueError('Not a registered candidate')
    original=local(candidate)/'IterativeMultiply.sv'
    digest=hashlib.sha256(original.read_bytes()).hexdigest()
    if digest!=data['extra_sources']['IterativeMultiply.sv']: raise ValueError('Registered multiply hash mismatch')
    if sum(Path(p)==original for p in sources)!=1: raise ValueError('Expected exactly one authenticated multiply source')
    parsed=output/'contract.json'; script=output/'contract.ys'
    script.write_text(f'read_slang --top IterativeMultiply {original}\nwrite_json {parsed}\n')
    run(['yosys','-Q','-T','-s',script],output,'contract')
    m=json.loads(parsed.read_text())['modules']['IterativeMultiply']
    widths=dict(clk_i=1,rst_ni=1,enable_i=1,ready_i=1,a_i=32,b_i=32,signed_mode_i=2,high_i=1,valid_o=1,result_o=32)
    for name,width in widths.items():
        port=m['ports'].get(name)
        direction='output' if name in ('valid_o','result_o') else 'input'
        if not port or port['direction']!=direction or len(port['bits'])!=width:
            raise ValueError('Registered ALTOPS missing/wrong port: '+name)
    idle=m['netnames'].get('sva_mul_fsm_idle')
    if not idle or len(idle['bits'])!=1: raise ValueError('Registered ALTOPS missing idle observation')
    text=original.read_text()
    matches=list(re.finditer(r'\bassign\s+result_o\s*=\s*[^;]+;',text))
    if len(matches)!=1 or 'deadhorse_alt' in text: raise ValueError('Expected one fresh result driver')
    ops=operations()
    (output/'operations.tsv').write_text(''.join(f'{name}\t{op}\t{mask:08x}\n' for name,op,mask in ops))
    mode='iterative'+(' capture-fault' if capture_fault else '')
    run([sys.executable,'tools/sbt.py','set hw / Compile / unmanagedSourceDirectories += file("/work/dv/core")',
         f'hw/runMain deadhorse.reference.EmitMultiplyAltop {output} {mode}'],output,'emit-altops')
    old=matches[0].group()
    connections=[f'.{n}({n})' for n in ('clk_i','rst_ni','enable_i','ready_i','a_i','b_i','signed_mode_i','high_i')]
    connections+=['.idle_i(sva_mul_fsm_idle)','.valid_i(valid_o)','.result(result_o)']
    new='`ifdef RISCV_FORMAL_ALTOPS\nDeadhorseIterativeAltop deadhorse_alt ('+', '.join(connections)+');\n`else\n'+old+'\n`endif'
    changed=text[:matches[0].start()]+new+text[matches[0].end():]
    if changed.replace(new,old,1)!=text: raise ValueError('Registered ALTOPS reversal failed')
    target=output/'IterativeMultiply.sv'; target.write_text(changed)
    emitted=[output/'DeadhorseIterativeAltop.sv',output/'DeadhorseMultiplyAltop.sv']
    (output/'adaptation.json').write_text(json.dumps(dict(id='D44-registered-multiply-altops',
        original_sha256=digest,adapted_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        removed=old,inserted=new,capture_fault=capture_fault,
        emitted_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in emitted}),indent=2)+'\n')
    return [str(target) if Path(p)==original else str(p) for p in sources]+list(map(str,emitted))

"""Exact selected-division equivalence after the approved multiply redesign."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'dv/core'))
from common import VENDOR, adapted_sources, inputs, output_dir, run
from equiv import compare, negatives, elaborate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',required=True)
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    out = output_dir(args.output)
    receipt = dict(status='running',scope='selected division only',
        boundary=['mult_en_i=0','mult_sel_i=0','div_sel_i=1','operator_i in DIV,REM'],
        assumptions=['normal reset initialization; multiply held disabled throughout comparison'],
        not_proved='mixed multiply/divide transaction composition')
    try:
        run([sys.executable,'tools/sbt.py',
            f'set hw / Compile / unmanagedSources += file("{ROOT}/hw/ip/perf_core/formal/DivisionComparison.scala")',
            f'hw/runMain deadhorse.perf_core.EmitDivisionComparison {out.relative_to(ROOT)}/emit'],out,'emit',timeout=600)
        lock = inputs()
        sources = adapted_sources(out,lock)
        # First elaborate the reference alone, then export its normalized
        # bitvector interface. This avoids enum/unpacked-array type coercions
        # at a Chisel BlackBox boundary; no vendor text is edited.
        leaf = elaborate('ibex_multdiv_fast',None,out,'reference-leaf')
        export = out/'export.ys'
        export.write_text(f'read_json {leaf}\nopt -full -nodffe -nosdff\n'+
            f'write_json {out}/reference-canonical.json\nwrite_verilog -noattr {out}/reference-leaf.sv\n')
        run(['yosys','-Q','-T','-s',export],out,'export')
        roundtrip = out/'roundtrip.ys'
        roundtrip.write_text(f'read_slang --top ibex_multdiv_fast {out}/reference-leaf.sv\n'+
            'prep -top ibex_multdiv_fast\nopt -full -nodffe -nosdff\n'+
            f'write_json {out}/reference-roundtrip.json\n')
        run(['yosys','-Q','-T','-s',roundtrip],out,'roundtrip')
        validation = out/'roundtrip-proof'; validation.mkdir(exist_ok=True)
        if compare('ibex_multdiv_fast',out/'reference-canonical.json',out/'reference-roundtrip.json',validation) != 'proved':
            raise RuntimeError('Reference normalization changed semantics')
        designs = []
        candidate = (ROOT/args.candidate).resolve()
        if not candidate.is_relative_to(ROOT/'build'):
            raise ValueError('Candidate must be repository build output')
        for name in ('gold','candidate'):
            selected = [str(out/'reference-leaf.sv')]
            if name == 'candidate':
                selected = [str(candidate/'ibex_multdiv_fast.sv')]
                selected.append(str(candidate/'IterativeMultiply.sv'))
            selected.append(str(out/'emit/DivisionComparison.sv'))
            script = out/(name+'.ys')
            script.write_text('read_slang --top DivisionComparison '+
                ' '.join('-D'+d for d in lock['defines'])+' '+
                ' '.join('-I'+str(VENDOR/p) for p in lock['include_dirs'])+' '+ ' '.join(selected)+'\n'+
                'prep -top DivisionComparison -flatten\nopt -full -nodffe -nosdff\ncheck -assert\n'+
                f'write_json {out}/{name}.json\n')
            run(['yosys','-Q','-T','-s',script],out,name)
            designs.append(out/(name+'.json'))
        proof = out/'proof'; proof.mkdir(exist_ok=True)
        if compare('DivisionComparison',*designs,proof) != 'proved':
            raise RuntimeError('Division equivalence failed')
        negatives('DivisionComparison',*designs,proof)
        bad = json.loads(designs[1].read_text())
        cell = next(c for c in bad['modules']['DivisionComparison']['cells'].values() if c['type']=='$adff')
        reset = cell['parameters']['ARST_VALUE']
        cell['parameters']['ARST_VALUE'] = reset[:-1]+('0' if reset[-1]=='1' else '1')
        fault = out/'reset-fault'; fault.mkdir(exist_ok=True)
        (fault/'candidate.json').write_text(json.dumps(bad))
        if compare('DivisionComparison',designs[0],fault/'candidate.json',fault) != 'failed':
            raise RuntimeError('Unrejected divider reset fault')
        receipt.update(status='proved', sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (candidate/'ibex_multdiv_fast.sv',candidate/'IterativeMultiply.sv',
                      out/'emit/DivisionComparison.sv',out/'reference-leaf.sv',out/'reference-canonical.json')})
        print('PASS selected division: exact state/output equivalence and negative controls',flush=True)
    except Exception as exc:
        receipt.update(status='failed',error=str(exc))
        raise
    finally:
        (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__': main()

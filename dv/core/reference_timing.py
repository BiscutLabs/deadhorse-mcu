"""Locked reference benchmark; never a production source or acceptance route."""
import argparse
import json
import sys

from common import ROOT,VENDOR,CONFIG,inputs,adapted_sources,output_dir,run,typed_parameter
sys.path.insert(0,str(ROOT))
from tools.timing.check import _measure


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    output=output_dir(args.output)
    (output/'result.json').write_text('{"status":"blocked"}\n')
    lock=inputs()
    sources=adapted_sources(output,lock)
    # Exactly the reference's abstract gate is replaced with the same qualified
    # ASIC wrapper as the candidate. No source text or CPU logic is modified.
    primitive=str(VENDOR/'dv/uvm/core_ibex/common/prim/prim_clock_gating.sv')
    if sources.count(primitive)!=1: raise ValueError('Missing unique locked clock primitive')
    run([sys.executable,'tools/sbt.py',
         f'set hw / Compile / unmanagedSourceDirectories += file("{ROOT}/dv/core")',
         f'hw/runMain deadhorse.reference.EmitReferencePhysicalGate {output}/gate'],output,'emit-gate')
    sources=[p for p in sources if p!=primitive]+[str(p) for p in sorted((output/'gate').glob('*.sv'))]
    options=[*['-D'+d for d in lock['defines'] if d!='RVFI'],
             *['-I'+str(VENDOR/p) for p in lock['include_dirs']],
             *[f'-G{k}={typed_parameter(k,v)}' for k,v in CONFIG['parameters'].items()]]
    result=_measure('ibex_top',sources,'clk_i',output/'measurement',reference_options=options)
    receipt=dict(status='measured',role='reference-benchmark-only',measurement_status=result['status'],
                 result='measurement/result.json',configuration=CONFIG,
                 differences=['RVFI observation disabled in both physical profiles',
                              'reference abstract gate bound to candidate GF180 ICG wrapper'],
                 not_production_acceptance=True)
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('MEASURED reference benchmark; strict timing result: '+result['status'],flush=True)
    return 0


if __name__=='__main__': sys.exit(main())

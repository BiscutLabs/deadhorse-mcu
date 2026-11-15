"""Reject a real faulted source-directory candidate through both consumers."""
import argparse
import hashlib
import json
import sys

from candidate import reference_copy
from common import output_dir,run
from lockstep import normalize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    output = output_dir(args.output)
    (output/'result.json').write_text('{"status":"running"}\n')
    candidate = output/'faulted-copy'
    reference_copy(candidate)
    path = candidate/'rtl/ibex_alu.sv'
    data = path.read_bytes()
    old = b'result_o = adder_result;'
    new = b"result_o = adder_result ^ 32'h1;"
    if data.count(old) != 1:
        raise ValueError('Fault injection must match exactly once')
    changed = data.replace(old,new,1)
    path.write_bytes(changed)
    (output/'fault.json').write_text(json.dumps(dict(source='rtl/ibex_alu.sv',
        original_sha256=hashlib.sha256(data).hexdigest(),faulted_sha256=hashlib.sha256(changed).hexdigest(),
        removed=old.decode(),inserted=new.decode()),indent=2)+'\n')
    rvf = output/'rvf'
    result = run([sys.executable,'dv/core/riscv_formal.py','--target','candidate',
                  '--candidate',candidate,'--output',rvf],output,'rvf-fault',allowed=(1,))
    receipt = json.loads((rvf/'result.json').read_text())
    failing = [p.parent for p in rvf.glob('*/bmc/work/status') if p.read_text().split()[0]=='FAIL']
    if receipt['status'] != 'failed' or not failing or not all(any(p.glob('engine_*/trace*')) for p in failing):
        raise ValueError('Candidate formal fault did not produce an assertion counterexample')
    lockstep = output/'lockstep'
    run([sys.executable,'dv/core/lockstep.py','--candidate',candidate,'--suite','arch',
         '--output',lockstep],output,'lockstep-fault',allowed=(1,))
    directory = lockstep/'arch/rv32ui-add'
    traces = [[json.loads(line) for line in (directory/f'{name}-run.log').read_text().splitlines()
               if line.startswith('{')] for name in ('reference','candidate')]
    mismatches = [(i,a,b) for i,(a,b) in enumerate(zip(*traces))
                  if a['pc_rdata']==b['pc_rdata'] and normalize(a)!=normalize(b)]
    if not mismatches:
        raise ValueError('Candidate lockstep fault lacked a concrete retirement mismatch')
    index,a,b = mismatches[0]
    (output/'result.json').write_text(json.dumps(dict(status='pass',
        formal_counterexamples=[str(p.relative_to(output)) for p in failing],
        lockstep_mismatch=dict(index=index,reference=a,candidate=b)),indent=2)+'\n')
    print('PASS candidate negative controls: real source fault gives formal counterexample and retirement mismatch')


if __name__=='__main__':
    try:
        main()
    except (OSError,ValueError,RuntimeError) as exc:
        print(f'FAIL candidate controls: {exc}',file=sys.stderr)
        sys.exit(1)

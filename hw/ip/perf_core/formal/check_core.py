"""Check the faithful Chisel core with all active translated children."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'dv/core'))
from common import local, output_dir
from equiv import elaborate, compare, negatives


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emitted', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    emitted, output = local(args.emitted), output_dir(args.output)
    children = ('ibex_if_stage', 'ibex_prefetch_buffer', 'ibex_fetch_fifo',
                'ibex_compressed_decoder', 'ibex_id_stage', 'ibex_decoder',
                'ibex_controller', 'ibex_ex_block', 'ibex_alu', 'ibex_multdiv_fast',
                'ibex_load_store_unit', 'ibex_wb_stage', 'ibex_cs_registers')
    gold = elaborate('ibex_core', None, output, 'gold',
                     reference_parameters={'DbgTriggerEn': '1'})
    candidate = elaborate('ibex_core', emitted/'ibex_core.sv', output, 'candidate',
                          replacements={name: emitted/(name+'.sv') for name in children})
    status = compare('ibex_core', gold, candidate, output)
    if status != 'proved':
        return 1
    faults = negatives('ibex_core', gold, candidate, output_dir(output/'negative'))
    path = output/'result.json'
    result = json.loads(path.read_text())
    result['negative_controls'] = faults
    path.write_text(json.dumps(result, indent=2)+'\n')
    print('PASS faithful translated core equivalence and negative controls')
    return 0


if __name__ == '__main__':
    sys.exit(main())

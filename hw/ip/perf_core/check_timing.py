"""Measure current production-profile T11 blocks, retaining every failure."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.timing.check import measure, local


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emitted',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--profile',choices=['production','pre-registered'],default='production')
    args = parser.parse_args()
    emitted, out = local(args.emitted), local(args.output)
    out.relative_to(ROOT/'build'); out.mkdir(parents=True,exist_ok=True)
    configs = {
        'csr':('ibex_csr','clk_i'), 'shadow':('ibex_csr','clk_i'),
        'counter':('ibex_counter','clk_i'), 'mcycle':('ibex_counter','clk_i'),
        'minstret':('ibex_counter','clk_i'), 'alu':('ibex_alu',None),
        'register_file':('ibex_register_file_ff','clk_i'),
        'compressed_decoder':('ibex_compressed_decoder',None),
        'fetch_fifo':('ibex_fetch_fifo','clk_i'),
        'prefetch_buffer':('ibex_prefetch_buffer','clk_i'),
        'iterative_multiply':('IterativeMultiply','clk_i')}
    # User-approved registered execution supersedes the earlier unregistered
    # integrated prototypes. Their diagnostic profile retains the same strict
    # limits and failure exit status; exact baseline equivalence stays in CI.
    configs.update({'clocked_execute':('ClockedExecute','clk_i')} if args.profile=='production' else {
        'multdiv_iterative':('ibex_multdiv_fast','clk_i'),
        'ex_iterative':('ibex_ex_block','clk_i')})
    if args.profile=='production':
        configs['decoder'] = ('ibex_decoder',None)
        configs['load_store_unit'] = ('ibex_load_store_unit','clk_i')
        configs['if_stage'] = ('ibex_if_stage','clk_i')
        configs['controller'] = ('ibex_controller','clk_i')
        configs['wb_stage'] = ('ibex_wb_stage',None)
        configs['cs_registers'] = ('ibex_cs_registers','clk_i')
        configs['id_stage'] = ('ibex_id_stage','clk_i')
    receipt = dict(status='running',profile=args.profile,scope='implemented blocks; not whole-core signoff',blocks={})
    try:
        for name,(top,clock) in configs.items():
            result = measure(top,[str(p) for p in sorted((emitted/name).glob('*.sv'))],clock,
                             out/name,combinational=clock is None)
            receipt['blocks'][name]=result
            (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
        receipt['status']='pass' if all(r['status']=='pass' for r in receipt['blocks'].values()) else 'failed'
        print(receipt['status'].upper()+' T11 implemented-block timing',flush=True)
        return int(receipt['status']!='pass')
    except Exception as exc:
        receipt.update(status='blocked',error=str(exc))
        raise
    finally:
        (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__': sys.exit(main())

"""Compare emitted parameterized Chisel leaves to the pinned Ibex reference."""
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
    parser.add_argument('--emitted', default='build/emit/perf_core_leaves')
    parser.add_argument('--output', default='build/t11/leaves/configurations')
    args = parser.parse_args()
    emitted, output = local(args.emitted), output_dir(args.output)
    configurations = {
        'csr': ('ibex_csr', {}),
        'counter': ('ibex_counter', {}),
        'mcycle': ('ibex_counter', {'CounterWidth': '64', 'ProvideValUpd': '0'}),
        'minstret': ('ibex_counter', {'CounterWidth': '64', 'ProvideValUpd': '1'}),
        'shadow': ('ibex_csr', {'Width': '8', 'ShadowCopy': '1', 'ResetValue': "8'ha5"}),
        'alu': ('ibex_alu', {}),
        'decoder': ('ibex_decoder', {}),
        'load_store_unit': ('ibex_load_store_unit', {}),
        'if_stage': ('ibex_if_stage', {}),
        'controller': ('ibex_controller', {}),
        'wb_stage': ('ibex_wb_stage', {}),
        'cs_registers': ('ibex_cs_registers', {'DbgTriggerEn': '1', 'MHPMCounterNum': '0'}),
        'id_stage': ('ibex_id_stage', {}),
        'register_file': ('ibex_register_file_ff', {}),
        'compressed_decoder': ('ibex_compressed_decoder', {}),
        'fetch_fifo': ('ibex_fetch_fifo', {}),
        'prefetch_buffer': ('ibex_prefetch_buffer', {}),
        'multdiv_fast': ('ibex_multdiv_fast', {}),
        'ex_block': ('ibex_ex_block', {}),
        'ex_repaired': ('ibex_ex_block', {}),
    }
    receipt = dict(status='running', configurations={})
    path = output/'result.json'
    path.write_text(json.dumps(receipt, indent=2)+'\n')
    for name, (module, parameters) in configurations.items():
        directory = output_dir(output/name)
        gold = elaborate(module, None, directory, 'gold', reference_parameters=parameters)
        replacements = {'ibex_fetch_fifo': emitted/name/'ibex_fetch_fifo.sv'} if name == 'prefetch_buffer' else None
        if name in ('ex_block','ex_repaired'):
            replacements = {child: emitted/name/(child+'.sv') for child in ('ibex_alu','ibex_multdiv_fast')}
        if name=='if_stage':
            replacements = {child: emitted/name/(child+'.sv') for child in
                ('ibex_prefetch_buffer','ibex_fetch_fifo','ibex_compressed_decoder')}
        if name=='id_stage':
            replacements = {child: emitted/name/(child+'.sv') for child in ('ibex_decoder','ibex_controller')}
        gate = elaborate(module, emitted/name/(module+'.sv'), directory, 'candidate', replacements=replacements)
        status = compare(module, gold, gate, directory)
        result = json.loads((directory/'result.json').read_text())
        result['parameters'] = parameters or 'reference module defaults'
        if status == 'proved':
            result['negative_controls'] = negatives(module, gold, gate, output_dir(directory/'negative'))
        (directory/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        receipt['configurations'][name] = result
        receipt['status'] = 'running' if status == 'proved' else 'failed'
        path.write_text(json.dumps(receipt, indent=2)+'\n')
        if status != 'proved':
            return 1
    receipt['status'] = 'proved'
    path.write_text(json.dumps(receipt, indent=2)+'\n')
    print('PASS configured leaf equivalence and negative controls')
    return 0


if __name__ == '__main__':
    sys.exit(main())

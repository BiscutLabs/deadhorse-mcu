"""Package emitted T11 baseline/views, without vendor CPU fallback sources."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'dv/core'))
from candidate import INACTIVE, parameters
from common import CONFIG, inputs, local, output_dir


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--top',required=True); parser.add_argument('--leaves',required=True)
    parser.add_argument('--core',required=True); parser.add_argument('--output',required=True)
    parser.add_argument('--registered',action='store_true')
    args=parser.parse_args(); top=local(args.top); leaves=local(args.leaves); core=local(args.core)
    output=output_dir(args.output); lock=inputs()
    data=dict(schema=2,kind='fixed',parameters=CONFIG['parameters'],source_sha256={},excluded=INACTIVE,
              extra_sources={},module_views={},implementation='faithful baseline; execution retiming remains separate')
    if args.registered: data['implementation']='registered-execution-v1'
    views={'ibex_csr':'csr','ibex_counter':'counter','ibex_register_file_ff':'register_file',
        'ibex_cs_registers':'cs_registers','ibex_ex_block':'ex_block',
        **{'ibex_'+n:n for n in ('alu','compressed_decoder','controller','decoder','wb_stage','id_stage',
          'if_stage','load_store_unit','multdiv_fast','prefetch_buffer','fetch_fifo')}}
    for source in lock['sources']:
        if not source.startswith('rtl/') or source.endswith('_pkg.sv') or source in INACTIVE: continue
        name=Path(source).name; module=Path(source).stem
        origin=top/name
        if not origin.exists(): origin=leaves/views[module]/name
        target=output/source; target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(origin,target)
        data['source_sha256'][source]=hashlib.sha256(target.read_bytes()).hexdigest()
        view_dir=core if module=='ibex_core' else leaves/views[module] if module in views else None
        if view_dir and not args.registered:
            view={}
            for path in view_dir.glob('ibex_*.sv'):
                dest=output/'modules'/module/path.name; dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(path,dest)
                view['rtl/'+path.name]=dict(path=str(dest.relative_to(output)).replace('\\','/'),
                                          sha256=hashlib.sha256(dest.read_bytes()).hexdigest())
            data['module_views'][module]=view
    shutil.copyfile(top/'ClockGate.sv',output/'ClockGate.sv')
    data['extra_sources']['ClockGate.sv']=hashlib.sha256((output/'ClockGate.sv').read_bytes()).hexdigest()
    if args.registered:
        for name in ('ClockedExecute.sv','IterativeMultiply.sv'):
            shutil.copyfile(top/name,output/name)
            data['extra_sources'][name]=hashlib.sha256((output/name).read_bytes()).hexdigest()
    (output/'candidate.json').write_text(json.dumps(data,indent=2)+'\n')
    if not args.registered:
        (output/'formal_adapter.json').write_text(json.dumps(dict(schema=1,
            multiply_altops=dict(source_sha256=data['source_sha256']['rtl/ibex_multdiv_fast.sv'],
                signals={name:name for name in ('mult_en_internal','sva_mul_fsm_idle','mult_valid')})),
            indent=2)+'\n')
    parameters(output)
    print('PASS packaged Chisel candidate: '+data['implementation']+'; inactive alternatives explicitly listed')


if __name__=='__main__': main()

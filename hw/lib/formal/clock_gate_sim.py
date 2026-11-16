"""Run the unchanged pinned GF180 UDP model with Icarus, not Verilator."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'dv/core'))
from common import local, output_dir, run, inputs


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emitted',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--binding',choices=('asic','model'),required=True)
    parser.add_argument('--negative',action='store_true')
    parser.add_argument('--faulted',action='store_true',help='Expect a DUT fault, without corrupting observations')
    args=parser.parse_args()
    emitted=local(args.emitted); output=output_dir(args.output)
    sources=[emitted/'ClockGate.sv']; hashes={}
    if args.binding=='asic':
        pdk=ROOT/'build/riscay-mcu/.tools/physical/pdk'
        for name,digest in {
            'gf180mcu_fd_sc_mcu7t5v0.v':'9a21c5f98200acfe77d8ba52067164e0802284dc1c1e117f0e64fb6ac42eb64b',
            'primitives.v':'ccc0f447f71ce35c635e08d49eb0ed77aa2ec91cf31d8e3e45a246114d3cae92'}.items():
            path=pdk/name
            if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                raise ValueError('Pinned PDK model differs: '+name)
            hashes[name]=digest; sources.append(path)
    else:
        inputs()
        sources.append(ROOT/'hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv')
    source=ROOT/'hw/lib/formal/clock_gate_vpi.cpp'
    # iverilog-vpi writes its object/plugin in cwd, always inside build.
    result=subprocess.run(['iverilog-vpi',str(source)],cwd=output,text=True,capture_output=True)
    (output/'vpi-build.log').write_text(result.stdout+result.stderr)
    if result.returncode: raise RuntimeError('Icarus VPI compilation failed')
    run(['iverilog','-g2012','-DFUNCTIONAL','-s','ClockGate','-o',output/'gate.vvp',*sources],output,'compile')
    command=['vvp','-M'+str(output),'-mclock_gate_vpi',str(output/'gate.vvp')]
    if args.negative: command.append('+corrupt')
    result=run(command,output,'simulation')
    expected='FAIL CLOCK_GATE_MODEL_MISMATCH' if args.negative or args.faulted else 'PASS CLOCK_GATE_PHASE_MODEL transitions=512'
    if expected not in result.stdout or (not (args.negative or args.faulted) and 'FAIL' in result.stdout):
        raise RuntimeError('Clock-gate phase checker did not produce required result')
    if args.faulted and ('expected=' not in result.stdout or 'unknown output' in result.stdout):
        raise RuntimeError('DUT fault must cause a concrete value mismatch after initialization')
    (output/'result.json').write_text(json.dumps(dict(status='pass',binding=args.binding,
        negative=args.negative,faulted=args.faulted,phase_samples=512 if not (args.negative or args.faulted) else None,
        model_sha256=hashes,emitted_sha256=hashlib.sha256(sources[0].read_bytes()).hexdigest()),indent=2)+'\n')
    print(expected)


if __name__=='__main__': main()

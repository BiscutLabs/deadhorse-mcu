"""Run the pinned upstream instruction checker on the fixed Ibex reference."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import shutil
import sys

from common import CONFIG, ROOT, VENDOR, adapted_sources, frontends, inputs, output_dir, run, typed_parameter

DEPTH = 40
CHECK_CYCLE = 12


def run_partitions(names, worker, collect):
    # Submit bounded batches. An executor with the whole ISA queued can start
    # another expensive job before the main thread observes a failed future.
    with ThreadPoolExecutor(max_workers=3) as pool:
        for offset in range(0, len(names), 3):
            batch = [pool.submit(worker, name) for name in names[offset:offset+3]]
            results = [job.result() for job in batch]
            for result in results:
                collect(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=['reference'], required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = output_dir(args.output)
    (output / 'result.json').write_text('{"status":"blocked"}\n')
    lock = inputs()
    frontends(output / 'frontend', 'slang')
    ports = json.loads((output / 'frontend/slang.json').read_text())['modules']['ibex_top']['ports']
    # Extra Ibex RVFI extensions are not part of the standard checker interface.
    standard = {'valid', 'order', 'insn', 'trap', 'halt', 'intr', 'mode', 'ixl', 'rs1_addr',
                'rs2_addr', 'rs1_rdata', 'rs2_rdata', 'rd_addr', 'rd_wdata', 'pc_rdata',
                'pc_wdata', 'mem_addr', 'mem_rmask', 'mem_wmask', 'mem_rdata', 'mem_wdata'}
    ports = {n: p for n, p in ports.items() if not n.startswith('rvfi_') or n[5:] in standard}
    # Unused outputs may be omitted from a BlackBox instance, including unpacked arrays.
    ports = {n: p for n, p in ports.items() if p['direction'] == 'input' or n.startswith('rvfi_')
             or n in ('instr_req_o', 'data_req_o')}
    (output / 'ports.tsv').write_text(''.join(f'{n}\t{len(p["bits"])}\t{p["direction"]}\n' for n, p in ports.items()))
    (output / 'parameters.tsv').write_text(''.join(f'{n}\t{typed_parameter(n,v)}\n' for n,v in CONFIG['parameters'].items()))
    run([sys.executable, 'tools/sbt.py', 'set hw / Compile / unmanagedSourceDirectories += file("/work/dv/core")',
         f'hw/runMain deadhorse.reference.EmitReferenceFormal {output}'], output, 'emit')
    rf = VENDOR / 'riscv-formal'
    insns = (rf / 'insns/isa_rv32imc.txt').read_text().split()
    sources = [*adapted_sources(output, lock), str(output / 'rvfi_wrapper.sv'),
               str(rf / 'checks/rvfi_macros.vh'), str(rf / 'checks/rvfi_insn_check.sv'),
               str(rf / 'checks/rvfi_testbench.sv'), str(rf / 'insns/isa_rv32imc.v'),
               *[str(rf / f'insns/insn_{n}.v') for n in insns]]
    defines = [*lock['defines'], 'YOSYS', 'RISCV_FORMAL', 'RISCV_FORMAL_NRET=1', 'RISCV_FORMAL_XLEN=32',
               'RISCV_FORMAL_ILEN=32', 'RISCV_FORMAL_COMPRESSED', 'RISCV_FORMAL_CHECKER=rvfi_insn_check',
               'RISCV_FORMAL_INSN_MODEL=rvfi_isa_rv32imc', 'RISCV_FORMAL_RESET_CYCLES=1',
               f'RISCV_FORMAL_CHECK_CYCLE={CHECK_CYCLE}']
    split = sources.index(str(rf / 'checks/rvfi_macros.vh'))
    script = ('read_slang --top rvfi_wrapper ' + ' '.join('-D'+d for d in lock['defines']) + ' ' +
              ' '.join('-I'+str(VENDOR/p) for p in lock['include_dirs']) + ' ' + ' '.join(sources[:split]) + '\n' +
              'read_verilog -formal -sv ' + ' '.join('-D'+d for d in defines) + ' ' + ' '.join(sources[split:]) + '\n' +
              'prep -top rvfi_testbench -flatten\nsetundef -undriven -anyseq\n' +
              'fminit -seq clock ' + ','.join(str(i % 2) for i in range(DEPTH)) + '\n')

    def check(name, mode, model, source=script):
        directory = output_dir(output / name)
        config = directory / 'check.sby'
        engine = 'abc bmc3' if mode == 'bmc' else 'btor btormc'
        config.write_text(f'[options]\nmode {mode}\ndepth {DEPTH}\nmulticlock on\ntimeout 600\n' +
                          f'[engines]\n{engine}\n[script]\n' + source.replace(
                              'RISCV_FORMAL_INSN_MODEL=rvfi_isa_rv32imc', f'RISCV_FORMAL_INSN_MODEL=rvfi_insn_{model}'))
        result = run(['sby', '-f', '-d', directory/'work', config], directory, mode, allowed=(0,2,16), timeout=630)
        status = (directory/'work/status').read_text().split()[0]
        if status not in ('PASS', 'FAIL') or result.returncode not in (0,2):
            raise RuntimeError(f'{name}: tool failure/timeout ({status}); no result claimed')
        return status

    fault = output_dir(output / 'fault-wrapper')
    for filename in ('parameters.tsv', 'ports.tsv'):
        shutil.copyfile(output / filename, fault / filename)
    run([sys.executable, 'tools/sbt.py', 'set hw / Compile / unmanagedSourceDirectories += file("/work/dv/core")',
         f'hw/runMain deadhorse.reference.EmitReferenceFormal {fault} fault'], output, 'emit-fault')
    fault_script = script.replace(str(output/'rvfi_wrapper.sv'), str(fault/'rvfi_wrapper.sv'))
    results = {}
    def instruction(name):
        bounded = check(name + '/bmc', 'bmc', name)
        if bounded != 'PASS':
            raise RuntimeError(f'riscv-formal reference assertion failed: {name}; inspect counterexample')
        covered = check(name + '/cover', 'cover', name)
        negative = check(name + '/negative', 'bmc', name, fault_script) if covered == 'PASS' else None
        if covered == 'PASS' and negative != 'FAIL':
            raise RuntimeError(f'{name}: formal result-bit fault escaped checker')
        result = dict(status='bounded' if covered == 'PASS' else 'unsupported',
                      depth=DEPTH, check_cycle=CHECK_CYCLE, cover=covered, negative_control=negative,
                      reason=None if covered == 'PASS' else 'Checked retirement not reached within bound')
        print(f'{name}: {result["status"]}, depth {DEPTH}, cover {covered}', flush=True)
        return name, result

    # Partitioning the same upstream ISA property avoids a monolithic divider
    # miter. Every instruction in the pinned ISA list remains a required job.
    def collect(item):
        name, result = item
        results[name] = result
        (output/'result.json').write_text(json.dumps(dict(status='running', checks=results), indent=2)+'\n')
    try:
        run_partitions(insns, instruction, collect)
    except Exception as exc:
        (output/'result.json').write_text(json.dumps(dict(status='failed', error=str(exc), checks=results), indent=2)+'\n')
        raise
    (output/'result.json').write_text(json.dumps(dict(status='pass', depth=DEPTH, check_cycle=CHECK_CYCLE,
        checks=results, negative_control='rejected', limitations=['bounded startup window only',
        'CSR, interrupts, debug, liveness, memory causality, and unbounded ISA proof unsupported']), indent=2)+'\n')
    print(f'PASS riscv-formal: bounded/covered classifications recorded at depth {DEPTH}; fault rejected; no unbounded proof')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'FAIL riscv-formal: {exc}', file=sys.stderr)
        sys.exit(1)

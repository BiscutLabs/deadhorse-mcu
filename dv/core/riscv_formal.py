"""Run the pinned upstream instruction checker on the fixed Ibex reference."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import shutil
import sys
import time

from common import CONFIG, ROOT, VENDOR, adapted_sources, frontends, inputs, output_dir, run, typed_parameter
from altops import MULTIPLY, prepare as prepare_altops

DEPTH = 40
CHECK_CYCLE = 12


class ArithmeticTimeout(RuntimeError):
    """SBY explicitly timed out without a counterexample."""


def sby_status(work, returncode):
    status = (work/'status').read_text().split()[0]
    if status == 'TIMEOUT' and returncode == 8:
        if any(work.glob('engine_*/trace*')):
            raise RuntimeError('Timeout with a witness artifact; inspect before classifying')
        raise ArithmeticTimeout('TIMEOUT; no proof or counterexample')
    if (status, returncode) not in (('PASS', 0), ('FAIL', 2)):
        raise RuntimeError(f'Inconsistent/unsuccessful SBY result: {status}/{returncode}')
    return status


def run_partitions(names, worker, collect):
    # Submit bounded batches. An executor with the whole ISA queued can start
    # another expensive job before the main thread observes a failed future.
    with ThreadPoolExecutor(max_workers=3) as pool:
        for offset in range(0, len(names), 3):
            batch = [pool.submit(worker, name) for name in names[offset:offset+3]]
            results = [job.result() for job in batch]
            for result in results:
                collect(result)


def require_candidate_coverage(target,name,covered):
    if target == 'candidate' and covered != 'PASS':
        raise RuntimeError(f'{name}: candidate lost reference-supported retirement coverage')


def selected_checks(available,selection):
    if selection is None: return list(available)
    chosen=selection.split(',')
    if not chosen or len(set(chosen))!=len(chosen) or not set(chosen)<=set(available):
        raise ValueError('Unknown, empty or duplicate selected ISA check')
    return chosen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=['reference','candidate'], required=True)
    parser.add_argument('--candidate')
    parser.add_argument('--output', required=True)
    parser.add_argument('--jalr-address-invariant',action='store_true',help='Independent all-retirement diagnostic; does not replace ISA checks')
    parser.add_argument('--split-assertions',action='store_true',help='Require exact assertion-union coverage in separate positive proof jobs')
    parser.add_argument('--prove-window',action='store_true',help='PDR proof of the same fixed startup-window checker; not unbounded ISA correctness')
    parser.add_argument('--checks',help='Explicit focused subset; omitted checks remain unverified')
    parser.add_argument('--timeout',type=int,default=600,help='Per-partition limit, at most the original 600 seconds')
    parser.add_argument('--unabstracted-multiply', action='store_true',
                        help='On-demand unresolved arithmetic diagnostic; never used by CI')
    args = parser.parse_args()
    if not 0<args.timeout<=600: parser.error('--timeout must be between 1 and 600')
    if args.jalr_address_invariant and (args.target!='candidate' or args.checks!='jalr' or args.split_assertions or args.unabstracted_multiply):
        parser.error('JALR invariant requires candidate --checks jalr, without split/arithmetic diagnostic')
    if args.checks and args.unabstracted_multiply: parser.error('--checks cannot select the multiply diagnostic')
    started = time.monotonic()
    if (args.target == 'candidate') != bool(args.candidate):
        parser.error('--candidate source directory is required only for target candidate')
    from candidate import manifest
    registered=bool(args.candidate and (manifest(args.candidate) or {}).get('implementation') in ('registered-execution-v1','rv32imfc-v1'))
    # Preserve the reference/baseline windows. The separately identified
    # registered profile needs room for operand qualification and 36 MUL edges.
    # This still does not cover a full nonzero 111-edge divide; its class remains
    # explicitly early-zero-only, with separate divider/refinement obligations.
    depth,check_cycle=(144,64) if registered else (DEPTH,CHECK_CYCLE)
    output = output_dir(args.output)
    (output / 'result.json').write_text('{"status":"blocked"}\n')
    lock = inputs()
    frontends(output / 'frontend', 'slang', args.candidate)
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
    from candidate import parameters as candidate_parameters
    parameters = candidate_parameters(args.candidate)
    (output / 'parameters.tsv').write_text(''.join(f'{n}\t{typed_parameter(n,v)}\n' for n,v in parameters.items()))
    run([sys.executable, 'tools/sbt.py', 'set hw / Compile / unmanagedSourceDirectories += file("/work/dv/core")',
         f'hw/runMain deadhorse.reference.EmitReferenceFormal {output}'], output, 'emit')
    rf = VENDOR / 'riscv-formal'
    insns = (rf / 'insns/isa_rv32imc.txt').read_text().split()
    core_sources = adapted_sources(output,lock)
    if args.candidate:
        from candidate import sources as candidate_sources
        core_sources = candidate_sources(args.candidate,lock,output)
    sources = [*core_sources, str(output / 'rvfi_wrapper.sv'),
               str(rf / 'checks/rvfi_macros.vh'), str(rf / 'checks/rvfi_insn_check.sv'),
               str(rf / 'checks/rvfi_testbench.sv'), str(rf / 'insns/isa_rv32imc.v'),
               *[str(rf / f'insns/insn_{n}.v') for n in insns]]
    if args.unabstracted_multiply:
        insns = list(MULTIPLY)
    else:
        # Exercise the changed proof route first; every other partition stays
        # mandatory, with exactly its existing model and environment.
        insns = list(MULTIPLY) + [name for name in insns if name not in MULTIPLY]
    available=list(insns)
    insns=selected_checks(available,args.checks)
    defines = [*lock['defines'], 'YOSYS', 'RISCV_FORMAL', 'RISCV_FORMAL_NRET=1', 'RISCV_FORMAL_XLEN=32',
               'RISCV_FORMAL_ILEN=32', 'RISCV_FORMAL_COMPRESSED', 'RISCV_FORMAL_CHECKER=rvfi_insn_check',
               'RISCV_FORMAL_INSN_MODEL=rvfi_isa_rv32imc', 'RISCV_FORMAL_RESET_CYCLES=1',
               f'RISCV_FORMAL_CHECK_CYCLE={check_cycle}']
    split = sources.index(str(rf / 'checks/rvfi_macros.vh'))
    script = ('read_slang --top rvfi_wrapper ' + ' '.join('-D'+d for d in lock['defines']) + ' ' +
              ' '.join('-I'+str(VENDOR/p) for p in lock['include_dirs']) + ' ' + ' '.join(sources[:split]) + '\n' +
              'read_verilog -formal -sv ' + ' '.join('-D'+d for d in defines) + ' ' + ' '.join(sources[split:]) + '\n' +
              'prep -top rvfi_testbench -flatten\nsetundef -undriven -anyseq\n' +
              'fminit -seq clock ' + ','.join(str(i % 2) for i in range(depth)) + '\n')

    if args.jalr_address_invariant:
        from jalr_invariant import check_invariant
        return check_invariant(output, script.replace(
            'RISCV_FORMAL_INSN_MODEL=rvfi_isa_rv32imc', 'RISCV_FORMAL_INSN_MODEL=rvfi_insn_jalr'),
            sources, depth, args.timeout)

    def check(name, mode, model, source):
        directory = output_dir(output / name)
        config = directory / 'check.sby'
        if args.split_assertions and mode=='bmc' and name.endswith('/bmc'):
            from assertion_partitions import run_split
            return run_split(directory,source.replace(
                'RISCV_FORMAL_INSN_MODEL=rvfi_isa_rv32imc',f'RISCV_FORMAL_INSN_MODEL=rvfi_insn_{model}'),
                depth,args.timeout,args.prove_window,run,sby_status)
        # The longer registered window is substantially better handled by
        # btormc. Same model, depth, assumptions, obligations and timeout.
        proof_mode='prove' if mode=='bmc' and args.prove_window and name.endswith('/bmc') else mode
        engine = 'abc pdr' if proof_mode=='prove' else 'abc bmc3' if mode=='bmc' and not registered else 'btor btormc'
        config.write_text(f'[options]\nmode {proof_mode}\ndepth {depth}\nmulticlock on\ntimeout {args.timeout}\n' +
                          f'[engines]\n{engine}\n[script]\n' + source.replace(
                              'RISCV_FORMAL_INSN_MODEL=rvfi_isa_rv32imc', f'RISCV_FORMAL_INSN_MODEL=rvfi_insn_{model}'))
        result = run(['sby', '-f', '-d', directory/'work', config], directory, mode, allowed=(0,2,8,16), timeout=args.timeout+30)
        return sby_status(directory/'work', result.returncode)

    fault = output_dir(output / 'fault-wrapper')
    for filename in ('parameters.tsv', 'ports.tsv'):
        shutil.copyfile(output / filename, fault / filename)
    run([sys.executable, 'tools/sbt.py', 'set hw / Compile / unmanagedSourceDirectories += file("/work/dv/core")',
         f'hw/runMain deadhorse.reference.EmitReferenceFormal {fault} fault'], output, 'emit-fault')
    fault_script = script.replace(str(output/'rvfi_wrapper.sv'), str(fault/'rvfi_wrapper.sv'))
    alt_script = capture_script = alt_fault_script = None
    if not args.unabstracted_multiply and set(insns)&set(MULTIPLY):
        original_sources = sources[:split]
        alt_sources = prepare_altops(output/'altops', original_sources, candidate=args.candidate)
        capture_sources = prepare_altops(output/'capture-fault', original_sources, capture_fault=True, candidate=args.candidate)
        def alternate(new_sources):
            return script.replace(' '.join(original_sources), ' '.join(new_sources)).replace(
                'read_slang --top', 'read_slang -DRISCV_FORMAL_ALTOPS --top').replace(
                '\nread_verilog -formal', '\nselect -assert-count 4 t:$check\nread_verilog -DRISCV_FORMAL_ALTOPS -formal')
        alt_script = alternate(alt_sources)
        capture_script = alternate(capture_sources)
        nonzero = output_dir(output/'nonzero-fault-wrapper')
        for filename in ('parameters.tsv', 'ports.tsv'):
            shutil.copyfile(output/filename, nonzero/filename)
        run([sys.executable, 'tools/sbt.py', 'set hw / Compile / unmanagedSourceDirectories += file("/work/dv/core")',
             f'hw/runMain deadhorse.reference.EmitReferenceFormal {nonzero} fault-nonzero'], output, 'emit-nonzero-fault')
        alt_fault_script = alt_script.replace(str(output/'rvfi_wrapper.sv'), str(nonzero/'rvfi_wrapper.sv'))
    results = {}
    def instruction(name):
        abstracted = name in MULTIPLY and not args.unabstracted_multiply
        source = alt_script if abstracted else script
        bounded = check(name + '/bmc', 'bmc', name, source)
        if bounded != 'PASS':
            raise RuntimeError(f'riscv-formal {args.target} assertion failed: {name}; inspect counterexample')
        covered = check(name + '/cover', 'cover', name, source)
        require_candidate_coverage(args.target,name,covered)
        negative = check(name + '/negative', 'bmc', name, alt_fault_script if abstracted else fault_script) if covered == 'PASS' else None
        if covered == 'PASS' and negative != 'FAIL':
            raise RuntimeError(f'{name}: formal result-bit fault escaped checker')
        capture_negative = check(name + '/capture-negative', 'bmc', name, capture_script) if abstracted and covered == 'PASS' else None
        if abstracted and (covered != 'PASS' or capture_negative != 'FAIL'):
            raise RuntimeError(f'{name}: missing ALTOPS cover or operand-capture fault escaped')
        kind = ('bounded, arithmetic abstracted (ALTOPS)' if abstracted else
                f'bounded, divisor-zero early-finish path only at check cycle {check_cycle}' if name in ('div','divu','rem','remu') else
                'bounded, unabstracted diagnostic' if args.unabstracted_multiply else 'bounded')
        result = dict(status=kind if covered == 'PASS' else 'unsupported',
                      depth=depth, check_cycle=check_cycle, cover=covered, negative_control=negative,
                      capture_negative_control=capture_negative,
                      unabstracted='unresolved (arithmetic)' if abstracted else None,
                      reason=None if covered == 'PASS' else 'Checked retirement not reached within bound')
        print(f'{name}: {result["status"]}, depth {depth}, cover {covered}', flush=True)
        return name, result

    # Partitioning the same upstream ISA property avoids a monolithic divider
    # miter. Every instruction in the pinned ISA list remains a required job.
    def collect(item):
        name, result = item
        results[name] = result
        (output/'result.json').write_text(json.dumps(dict(status='running', checks=results), indent=2)+'\n')
    try:
        if args.split_assertions:
            for name in insns: collect(instruction(name))
        else:
            run_partitions(insns, instruction, collect)
    except Exception as exc:
        status = 'unresolved (arithmetic)' if args.unabstracted_multiply and isinstance(exc, ArithmeticTimeout) else 'failed'
        (output/'result.json').write_text(json.dumps(dict(status=status, error=str(exc), checks=results), indent=2)+'\n')
        raise
    (output/'result.json').write_text(json.dumps(dict(status='diagnostic complete' if args.unabstracted_multiply else 'pass', depth=depth, check_cycle=check_cycle,
        profile=(manifest(args.candidate) or {}).get('implementation','reference-cycle-baseline') if args.candidate else 'reference-cycle-baseline',
        scope='selected instruction subset' if args.checks else 'complete configured instruction list',
        omitted_checks=[name for name in available if name not in insns],timeout_seconds=args.timeout,
        engine='PDR over the fixed startup-window checker' if args.prove_window else 'BMC',
        assertion_partitioning=args.split_assertions,
        target=args.target, candidate=args.candidate, elapsed_seconds=time.monotonic()-started,
        checks=results, negative_control='rejected', limitations=['bounded startup window only',
        'CSR, interrupts, debug, liveness, memory causality, and unbounded ISA proof unsupported']), indent=2)+'\n')
    label = 'DIAGNOSTIC COMPLETE' if args.unabstracted_multiply else 'PASS'
    print(f'{label} riscv-formal: bounded/covered classifications recorded at depth {depth}; fault rejected; no unbounded proof')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'FAIL riscv-formal: {exc}', file=sys.stderr)
        sys.exit(1)

"""Local check gate. Invoke through tools/env/run.py run."""
from pathlib import Path
import subprocess
import sys
import json
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    started = time.monotonic()
    output = ROOT/'build/ci'
    output.mkdir(parents=True,exist_ok=True)
    receipt = dict(status='running',commands=[])
    commands = ([sys.executable, 'tools/env/check.py'],
                    [sys.executable, '-m', 'unittest', 'discover', '-s', 'tools', '-p', 'test_*.py', '-v'],
                    [sys.executable, 'tools/check_structure.py', '--include-untracked'],
                    [sys.executable, 'hw/vendor/ibex_ref/verify_lock.py'],
                    [sys.executable, '-m', 'unittest', 'discover', '-s', 'dv/core', '-p', 'test_*.py', '-v'],
                    [sys.executable, 'dv/core/isolation.py', '--self-check'],
                    [sys.executable, '-m', 'unittest', 'discover', '-s', 'hw/lib/formal', '-p', 'test_*.py', '-v'],
                    [sys.executable, '-m', 'unittest', 'hw/regmap/test_regmap.py', '-v'],
                    [sys.executable, 'tools/sbt.py', 'hw/compile'],
                    [sys.executable, 'tools/sbt.py', 'hw/test'],
                    [sys.executable, 'tools/sbt.py', 'hw/runMain deadhorse.top.EmitHello build/emit/hello'],
                    ['iverilog', '-g2012', '-o', 'build/emit/hello/a.out', 'build/emit/hello/Hello.sv'],
                    [sys.executable, 'tools/formal_smoke.py', '--output', 'build/t07/formal'],
                    [sys.executable, 'hw/lib/formal/regblock_proof.py'],
                    [sys.executable, 'tools/timing/check.py', '--self-test', '--output', 'build/t09/ci'],
                    [sys.executable, 'tools/sbt.py', 'hw/runMain deadhorse.lib.EmitClockGate build/t11/ci/clock_gate'],
                    [sys.executable, 'hw/lib/formal/clock_gate_proof.py', '--emitted', 'build/t11/ci/clock_gate', '--output', 'build/t11/ci/clock_gate_proof'],
                    [sys.executable, 'hw/lib/formal/clock_gate_timing.py', '--source', 'build/t11/ci/clock_gate/asic/ClockGate.sv', '--output', 'build/t11/ci/clock_gate_timing'],
                    [sys.executable, 'tools/sbt.py', 'hw/runMain deadhorse.perf_core.EmitLeaves build/t11/ci/emit'],
                    [sys.executable, 'hw/ip/perf_core/formal/check_leaves.py', '--emitted', 'build/t11/ci/emit', '--output', 'build/t11/ci/leaves'],
                    [sys.executable, 'hw/ip/perf_core/check_timing.py', '--emitted', 'build/t11/ci/emit', '--output', 'build/t11/ci/timing'],
                    [sys.executable, 'tools/sbt.py', 'hw/runMain deadhorse.perf_core.EmitCore build/t11/ci/core'],
                    [sys.executable, 'hw/ip/perf_core/formal/check_core.py', '--emitted', 'build/t11/ci/core', '--output', 'build/t11/ci/core_equiv'],
                    [sys.executable, 'tools/sbt.py', 'hw/runMain deadhorse.perf_core.EmitTop build/t11/ci/top'],
                    [sys.executable, 'hw/ip/perf_core/formal/package_candidate.py', '--top', 'build/t11/ci/top/model', '--leaves', 'build/t11/ci/emit', '--core', 'build/t11/ci/core', '--output', 'build/t11/ci/baseline'],
                    [sys.executable, 'dv/core/equiv.py', '--all-modules', '--candidate', 'build/t11/ci/baseline', '--self-check', '--output', 'build/t11/ci/baseline_modules'],
                    [sys.executable, 'dv/core/equiv.py', '--top', '--candidate', 'build/t11/ci/baseline', '--self-check', '--output', 'build/t11/ci/baseline_top'],
                    [sys.executable, 'dv/core/riscv_formal.py', '--target', 'candidate', '--candidate', 'build/t11/ci/baseline', '--output', 'build/t11/ci/baseline_rvf'],
                    [sys.executable, 'dv/core/lockstep.py', '--candidate', 'build/t11/ci/baseline', '--suite', 'arch,flight', '--output', 'build/t11/ci/baseline_lockstep'],
                    [sys.executable, 'tools/sbt.py', 'hw/runMain deadhorse.perf_core.EmitRegisteredCore build/t11/ci/registered_emit'],
                    [sys.executable, 'hw/ip/perf_core/check_top_timing.py', '--emitted', 'build/t11/ci/registered_emit/asic', '--output', 'build/t11/ci/registered_timing'],
                    [sys.executable, 'hw/ip/perf_core/formal/package_candidate.py', '--registered', '--top', 'build/t11/ci/registered_emit/model', '--leaves', 'build/t11/ci/emit', '--core', 'build/t11/ci/core', '--output', 'build/t11/ci/registered'],
                    [sys.executable, 'hw/ip/perf_core/formal/check_integration.py', '--emitted', 'build/t11/ci/registered_emit/asic', '--output', 'build/t11/ci/registered_protocol'],
                    [sys.executable, 'dv/core/riscv_formal.py', '--target', 'candidate', '--candidate', 'build/t11/ci/registered', '--output', 'build/t11/ci/registered_rvf'],
                    [sys.executable, 'dv/core/lockstep.py', '--candidate', 'build/t11/ci/registered', '--suite', 'arch,flight', '--output', 'build/t11/ci/registered_lockstep'],
                    [sys.executable, 'dv/core/reference_timing.py', '--output', 'build/t11/ci/reference_timing'],
                    [sys.executable, 'hw/ip/perf_core/formal/check_iterative.py', '--candidate', 'build/t11/ci/emit/iterative_multiply/IterativeMultiply.sv', '--output', 'build/t11/ci/iterative'],
                    [sys.executable, 'hw/ip/perf_core/formal/check_division.py', '--candidate', 'build/t11/ci/emit/multdiv_iterative', '--output', 'build/t11/ci/division'],
                    [sys.executable, 'hw/ip/perf_core/formal/check_execute.py', '--candidate', 'build/t11/ci/emit/clocked_execute', '--output', 'build/t11/ci/execute'],
                    [sys.executable, 'dv/core/common.py', 'build/t10/ci/frontends'],
                    [sys.executable, 'dv/core/isolation.py', '--self-check'],
                    [sys.executable, 'dv/core/equiv.py', '--self-check', '--output', 'build/t10/ci/equiv'],
                    [sys.executable, 'dv/core/equiv.py', '--self-check', '--all-modules', '--output', 'build/t10/ci/equiv_all'],
                    [sys.executable, 'dv/core/equiv.py', '--self-check', '--top', '--output', 'build/t10/ci/equiv_top'],
                    [sys.executable, 'dv/core/lockstep.py', '--self-check', '--output', 'build/t10/ci/lockstep'],
                    [sys.executable, 'dv/core/riscv_formal.py', '--target', 'reference', '--output', 'build/t10/ci/rvf'],
                    [sys.executable, 'dv/core/candidate.py', '--reference-copy', 'build/t10/ci/reference_copy'],
                    [sys.executable, 'dv/core/riscv_formal.py', '--target', 'candidate', '--candidate', 'build/t10/ci/reference_copy', '--output', 'build/t10/ci/rvf_candidate'],
                    [sys.executable, 'dv/core/mul_lemma.py', '--output', 'build/t10/ci/mul_lemma'],
                    [sys.executable, 'dv/core/mul_diagnose.py', '--output', 'build/t10/ci/mul_stress'],
                    [sys.executable, 'dv/core/div_diagnose.py', '--output', 'build/t10/ci/div_stress'],
                    ['bash', 'sw/flight/loop-measurement/check.sh'],
                    [sys.executable, 'dv/core/lockstep.py', '--candidate', 'build/t10/ci/reference_copy', '--suite', 'arch,flight', '--output', 'build/t10/ci/lockstep_suites'],
                    [sys.executable, 'dv/core/candidate_check.py', '--output', 'build/t10/ci/candidate_negative'],
                    [sys.executable, 'dv/fpu/check.py', '--output', 'build/t12'])
    if sys.argv[1:]:
        if sys.argv[1:] != ['--scope', 'fpu']:
            raise ValueError('Usage: tools/ci.py [--scope fpu]')
        output = ROOT/'build/ci/fpu'
        output.mkdir(parents=True,exist_ok=True)
        receipt['scope']='fpu; unrelated core checks not run'
        commands = ([sys.executable, 'tools/env/check.py'],
                    [sys.executable, '-m', 'unittest', 'discover', '-s', 'tools', '-p', 'test_*.py', '-v'],
                    [sys.executable, 'tools/check_structure.py', '--include-untracked'],
                    [sys.executable, 'dv/fpu/check.py', '--output', 'build/t12'])
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    for command in commands:
        step_started = time.monotonic()
        result = subprocess.run(command, cwd=ROOT)
        receipt['commands'].append(dict(command=command,returncode=result.returncode,
                                        elapsed_seconds=time.monotonic()-step_started))
        receipt['elapsed_seconds'] = time.monotonic()-started
        receipt['status'] = 'failed' if result.returncode else 'running'
        (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
        if result.returncode: return result.returncode
    receipt['status']='pass'
    receipt['elapsed_seconds']=time.monotonic()-started
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS', flush=True)
    return 0


if __name__ == '__main__': sys.exit(main())

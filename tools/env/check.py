"""Check locked image provenance, actual tools, and independent smoke outcomes."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
INSTALLED = Path('/opt/deadhorse-env')


def run(command, *, data=None):
    p = subprocess.run(command, input=data, text=True, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, timeout=180)
    if p.returncode:
        raise RuntimeError(f'{command}: exit {p.returncode}\n{p.stdout}')
    return p.stdout.strip()


def solver_controls(skip=False):
    """Keep default controls intact; explicit non-formal runs record omission."""
    if skip:
        return 'not run (explicit no-formal request)'
    solver = run(['z3', '-in'], data='(set-logic QF_BV)\n(declare-const x (_ BitVec 8))\n(assert (not (= x x)))\n(check-sat)\n')
    if solver != 'unsat': raise RuntimeError(f'solver negative control: {solver}')
    solver = run(['z3', '-in'], data='(set-logic QF_BV)\n(declare-const x (_ BitVec 8))\n(assert (= x x))\n(check-sat)\n')
    if solver != 'sat': raise RuntimeError(f'solver positive control: {solver}')
    return 'pass'


def main():
    no_formal = os.environ.get('DEADHORSE_NO_FORMAL', '0')
    if no_formal not in ('0', '1'): raise ValueError('DEADHORSE_NO_FORMAL must be 0 or 1')
    if platform.system() != 'Linux' or not (INSTALLED / 'lock.json').is_file():
        raise RuntimeError('run in the pinned Linux image via tools/env/run.py')
    lock_bytes = (ROOT / 'tools/env/lock.json').read_bytes()
    if lock_bytes != (INSTALLED / 'lock.json').read_bytes():
        raise RuntimeError('image lock differs from repository; rebuild')
    lock = json.loads(lock_bytes)
    if sys.version_info[:2] != (3, 12): raise RuntimeError('Python 3.12 required')
    import tkinter
    import yaml
    if tkinter.Tcl().eval('expr {6 * 7}') != '42': raise RuntimeError('Tcl smoke failed')
    if yaml.safe_load('answer: 42')['answer'] != 42: raise RuntimeError('YAML smoke failed')
    inventory = run(['dpkg-query', '-W', '-f=${Package}\t${Version}\n'])
    if inventory != (INSTALLED / 'apt-installed.txt').read_text().strip():
        raise RuntimeError('installed Ubuntu packages differ from image build inventory')
    for item in lock['wheels']:
        actual = importlib.metadata.version(item['package'])
        if actual != item['version']: raise RuntimeError(f"{item['package']}: {actual}")
    for item in lock['maven']:
        with (Path('/opt/maven-pins') / item['name']).open('rb') as f:
            if hashlib.file_digest(f, 'sha256').hexdigest() != item['sha256']:
                raise RuntimeError(f"Maven artifact checksum: {item['name']}")
    versions = {}
    commands = {
        'java': ['java', '-version'], 'sbt': ['sbt', '--script-version'],
        'firtool': ['firtool', '--version'], 'iverilog': ['iverilog', '-V'],
        'verilator': ['verilator', '--version'], 'yosys': ['yosys', '-V'],
        'yowasp-yosys': ['yowasp-yosys', '-V'], 'sby': ['sby', '--version'],
        'boolector': ['boolector', '--version'], 'btormc': ['btormc', '--version'],
        'z3': ['z3', '--version'], 'sta': ['sta', '-version'],
        'riscv-gcc': ['riscv64-unknown-elf-gcc', '--version'],
        'qemu': ['qemu-system-riscv32', '--version'], 'git': ['git', '--version'],
        'sv2v': ['sv2v', '--version'],
    }
    for name, command in commands.items(): versions[name] = run(command)
    for name, expected in [('java', '21.'), ('sbt', lock['versions']['sbt']),
                           ('firtool', lock['versions']['firtool']), ('yowasp-yosys', '0.71'),
                           ('sv2v', lock['versions']['sv2v'])]:
        if expected not in versions[name]: raise RuntimeError(f'{name}: unexpected version {versions[name]}')
    for tool, command in [('yowasp-yosys', 'read_slang'), ('yosys', 'sat')]:
        help_text = run([tool, '-Q', '-T', '-p', f'help {command}'])
        if 'No such command' in help_text or command not in help_text:
            raise RuntimeError(f'{tool}: missing {command}')
    solver_status = solver_controls(skip=no_formal == '1')
    out = ROOT / 'build/env/smoke'; out.mkdir(parents=True, exist_ok=True)
    source = out / 'smoke.c'; source.write_text('int answer(void) { return 42; }\n')
    run(['riscv64-unknown-elf-gcc', '-march=rv32imc', '-mabi=ilp32', '-c', str(source), '-o', str(out/'smoke.o')])
    receipt = {'status': 'pass', 'lock_sha256': hashlib.sha256(lock_bytes).hexdigest(),
               'python': sys.version, 'versions': versions, 'solver_controls': solver_status,
               'apt_sha256': hashlib.sha256(inventory.encode()).hexdigest(),
               'scope': 'Environment presence and smoke only; no Chisel project or hardware qualification'}
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(f'PASS environment: {len(commands)} tools; locked artifacts, Python/Tcl/YAML, RV32 compiler; solver controls: {solver_status}')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        sys.exit(f'ENV_CHECK: {exc}')

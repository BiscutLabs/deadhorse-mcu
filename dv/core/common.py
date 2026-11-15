"""Shared pinned reference inputs and fail-closed command receipts."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
VENDOR = ROOT / 'hw/vendor/ibex_ref'
CONFIG = json.loads((ROOT / 'dv/core/config.json').read_text())


def typed_parameter(name, value):
    kind = {'RV32M': 'rv32m_e', 'RV32B': 'rv32b_e', 'RegFile': 'regfile_e'}.get(name)
    return f"ibex_pkg::{kind}'({value})" if kind else value


def local(value):
    path = (ROOT / value).resolve()
    path.relative_to(ROOT)
    if re.search(r'[\s;{}"$]', str(path)):
        raise ValueError('Unsupported path characters')
    return path


def output_dir(value):
    output = local(value)
    output.relative_to(ROOT / 'build')
    output.mkdir(parents=True, exist_ok=True)
    return output


def run(args, output, name, allowed=(0,), timeout=600):
    started = time.monotonic()
    try:
        result = subprocess.run([str(a) for a in args], cwd=ROOT, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        data = exc.stdout or b''
        (output / (name + '.log')).write_text(data.decode(errors='replace') if isinstance(data, bytes) else data)
        with (output / 'commands.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(command=[str(a) for a in args], status='timeout', seconds=timeout)) + '\n')
        raise RuntimeError(f'{name}: timeout after {timeout}s; log retained') from exc
    (output / (name + '.log')).write_text(result.stdout)
    result.elapsed_seconds = time.monotonic() - started
    with (output / 'commands.jsonl').open('a') as stream:
        stream.write(json.dumps(dict(command=[str(a) for a in args], returncode=result.returncode,
                                     elapsed_seconds=result.elapsed_seconds)) + '\n')
    if result.returncode not in allowed:
        raise RuntimeError(f'{name}: exit {result.returncode}; see {output}/{name}.log')
    return result


def inputs():
    spec = importlib.util.spec_from_file_location('verify_ibex', VENDOR / 'verify_lock.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify()


def adapted_sources(output, lock):
    adaptation = json.loads((ROOT / 'dv/core/adaptations.json').read_text())
    original = VENDOR / adaptation['source']
    data = original.read_bytes()
    if hashlib.sha256(data).hexdigest() != adaptation['source_sha256']:
        raise ValueError('Adaptation input hash mismatch')
    remove = adaptation['remove'].encode()
    if data.count(remove) != 1:
        raise ValueError('Adaptation must match exactly once')
    result = data.replace(remove, b'', 1)
    target = output / 'adapted/ibex_top.sv'
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(result)
    (output / 'adaptation.json').write_text(json.dumps(dict(
        id=adaptation['id'], original_sha256=adaptation['source_sha256'],
        adapted_sha256=hashlib.sha256(result).hexdigest(), removed=adaptation['remove']), indent=2) + '\n')
    return [str(target if name == adaptation['source'] else VENDOR / name) for name in lock['sources']]


def frontends(output, backend='both'):
    output = output_dir(output)
    lock = inputs()
    run([sys.executable, 'tools/env/check.py'], output, 'environment')
    sources = adapted_sources(output, lock)
    includes = [str(VENDOR / name) for name in lock['include_dirs']]
    params = CONFIG['parameters']
    slang = output / 'slang.ys'
    slang.write_text('read_slang --top ibex_top ' +
                     ' '.join('-D' + d for d in lock['defines']) + ' ' +
                     ' '.join('-I' + p for p in includes) + ' ' +
                     ' '.join(f'-G{k}={typed_parameter(k, v)}' for k, v in params.items()) + ' ' +
                     ' '.join(sources) + '\nhierarchy -check -top ibex_top\n' +
                     f'write_json {output}/slang.json\n')
    if backend in ('both', 'slang'):
        run(['yosys', '-Q', '-T', '-s', slang], output, 'slang')
    if backend == 'slang':
        return
    args = ['sv2v', '--top=ibex_top', *['-D' + d for d in lock['defines']],
            *['-I' + p for p in includes], *sources, '--write=' + str(output / 'reference.v')]
    run(args, output, 'sv2v')
    # Native Yosys Verilog parsing cannot resolve the RVFI cross-module refs.
    # Verilator elaborates sv2v output independently; slang is the formal route.
    run(['verilator', '--cc', '--top-module', 'ibex_top', '-Wno-fatal',
         '--Mdir', str(output / 'sv2v-obj'), *[f'-G{k}={v}' for k, v in params.items()],
         str(output / 'reference.v')], output, 'sv2v-elaborate')
    print(f'PASS reference elaboration: {backend}', flush=True)


if __name__ == '__main__':
    frontends(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'both')

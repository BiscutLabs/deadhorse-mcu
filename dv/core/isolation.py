"""Reject verification-only reference inputs from production source/physical flows."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / 'hw/vendor/ibex_ref'


def reject_sources(sources):
    lock = json.loads((REFERENCE / 'ibex_ref.lock.json').read_text())
    hashes = {entry['sha256'] for name, entry in lock['files'].items()
              if Path(name).suffix in ('.sv', '.v', '.svh', '.vh')}
    adaptation = json.loads((ROOT / 'dv/core/adaptations.json').read_text())
    original = (REFERENCE / adaptation['source']).read_bytes()
    hashes.add(hashlib.sha256(original.replace(adaptation['remove'].encode(), b'', 1)).hexdigest())
    for source in sources:
        path = (ROOT / source).resolve()
        path.relative_to(ROOT)
        if any(path.is_relative_to(ROOT / name) for name in ('hw/vendor/ibex_ref', 'dv/core', 'build/t10')):
            raise ValueError(f'Reference-only source forbidden in production: {path}')
        data = path.read_bytes()
        text = data.decode(errors='replace').replace('\\', '/').lower()
        if path.suffix == '.scala':
            # Translations retain upstream attribution in comments. Actual
            # BlackBox/resource paths in code remain subject to the guard.
            text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
        if hashlib.sha256(data).hexdigest() in hashes or any(marker in text for marker in (
                'hw/vendor/ibex_ref/', 'dv/core/referenceformal', 'dv/core/multiplyaltop',
                'deadhorsemultiplyaltop', 'build/t10/')):
            raise ValueError(f'Reference-only content/provenance forbidden in production: {path}')
        if path.suffix in ('.sv', '.v'):
            code = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
            if re.search(r'\bmodule\s+(?:automatic\s+)?(?:ibex_top|rvfi_wrapper|deadhorsemultiplyaltop)\b', code):
                raise ValueError(f'Reference comparison top forbidden in production: {path}')


def repository_sources():
    for base in ('hw/lib', 'hw/ip', 'hw/top'):
        yield from (ROOT / base).rglob('*.scala')
    for path in (ROOT / 'phys').rglob('*'):
        if path.is_file() and path.suffix in ('.json', '.tcl', '.yaml', '.yml', '.f'):
            yield path


def self_check():
    reject_sources(repository_sources())
    build = ROOT / 'build/isolation'
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=build, prefix='isolation-') as directory:
        copied = Path(directory) / 'renamed.sv'
        copied.write_bytes((REFERENCE / 'rtl/ibex_alu.sv').read_bytes())
        transformed = ROOT / 'build/t10/ci/frontends/reference.v'
        sources = [REFERENCE / 'rtl/ibex_alu.sv', copied]
        for run_name in ('ci', 'd44'):
            for filename in ('DeadhorseMultiplyAltop.sv', 'ibex_multdiv_fast.sv'):
                helper = ROOT / f'build/t10/{run_name}/rvf/altops/{filename}'
                if helper.exists():
                    copied_helper = copied.parent / f'{run_name}-{filename}'
                    copied_helper.write_bytes(helper.read_bytes())
                    sources.append(copied_helper)
        if transformed.exists():
            renamed = Path(directory) / 'converted.v'
            renamed.write_bytes(transformed.read_bytes())
            sources.extend((transformed, renamed))
        for source in sources:
            try:
                reject_sources([source])
            except ValueError:
                pass
            else:
                raise ValueError('Reference source escaped production guard')
        # Exercise the real physical entrypoint as well as its guard function.
        probe = subprocess.run([sys.executable, str(ROOT/'tools/timing/check.py'),
            '--top', 'ibex_top', '--source', str(copied), '--clock', 'clk_i',
            '--output', 'build/isolation/physical-negative'], cwd=ROOT,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
        if probe.returncode == 0 or 'BLOCKED timing: Reference-only' not in probe.stdout:
            raise ValueError('Physical entrypoint did not reject reference content before mapping')
    print('PASS reference isolation: production inputs accepted; vendor and copied sources rejected')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check', action='store_true')
    parser.add_argument('sources', nargs='*')
    args = parser.parse_args()
    reject_sources(args.sources)
    if args.self_check:
        self_check()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f'FAIL isolation: {exc}', file=sys.stderr)
        sys.exit(1)

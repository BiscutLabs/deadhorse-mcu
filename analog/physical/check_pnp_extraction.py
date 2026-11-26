"""Authenticate and exercise the local PNP extraction-deck correction.

The foundry device models and physical leaves remain unchanged. Outputs,
including the corrected copy of the technology file, belong under build/.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdk', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    pdk = (ROOT / args.pdk).resolve()
    pdk.relative_to(ROOT / 'build')
    output = (ROOT / args.output).resolve()
    output.relative_to(ROOT / 'build')
    output.mkdir(parents=True, exist_ok=False)
    try:
        run(pdk, output)
    except BaseException as error:
        if not (output / 'result.json').exists():
            (output / 'result.json').write_text(json.dumps(dict(
                status='failed', phase='input authentication', error=repr(error),
                script_sha256=sha(Path(__file__))), indent=2)+'\n')
        raise


def run(pdk, output):
    lock_path = Path(__file__).with_name('inputs.lock.json')
    lock = json.loads(lock_path.read_text())
    original = pdk / 'libs.tech/magic/gf180mcuD.tech'
    assert sha(original) == lock['original_tech_sha256'], 'Unpinned extraction deck'
    corrected, count = re.subn(
        r'^(\s*device msubcircuit pnp_\S+ pnp) pwell,space/w \*pdiff error a2>(\S+) a2<(\S+)',
        r'\1 *pdiff pwell,space/w a1>\2 a1<\3', original.read_text(), flags=re.M)
    assert count == 4
    tech = output / 'gf180mcuD.tech'
    tech.write_text(corrected)
    assert sha(tech) == lock['patched_tech_sha256'], 'Unexpected patch output'
    magic = Path(shutil.which('magic')).resolve()
    assert sha(magic) == lock['magic_executable_sha256'], 'Unpinned Magic executable'
    tool_root = magic.parent.parent
    assert str(tool_root) == lock['magic_store_path']
    tool_files = {str(p.relative_to(tool_root)): sha(p)
                  for p in sorted(tool_root.rglob('*')) if p.is_file()}
    assert hashlib.sha256(json.dumps(tool_files, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == lock['magic_output_tree_sha256'], 'Unpinned Magic output tree'
    rc = pdk / 'libs.tech/magic/gf180mcuD.magicrc'
    initialization = [pdk / 'libs.tech/magic' / name for name in lock['initialization_sha256']]
    for path in initialization:
        assert sha(path) == lock['initialization_sha256'][path.name], path
    receipt = dict(status='running', scope='PNP extraction grammar and primitive identity only',
                   inputs={str(p.relative_to(ROOT)): sha(p) for p in
                           (lock_path, Path(__file__), original, *initialization)},
                   tool=dict(path=str(magic), sha256=sha(magic), files=tool_files), cases=[])

    def extract(directory, name):
        script = directory / 'extract.tcl'
        script.write_text(f'tech load {tech}\nload {name}\nextract all\n'
                          'ext2spice lvs\next2spice -o extracted.spice\nquit -noprompt\n')
        command = [str(magic), '-dnull', '-noconsole', '-rcfile', str(rc), str(script)]
        start = time.monotonic()
        case = dict(name=name, command=command, status='running')
        receipt['cases'].append(case)
        try:
            with (directory / 'extract.log').open('w') as log:
                result = subprocess.run(command, cwd=directory,
                                        env={**os.environ, 'PDK_ROOT': str(pdk.parent)},
                                        stdout=log, stderr=subprocess.STDOUT, timeout=60)
            case.update(exit_code=result.returncode, status='completed')
        except subprocess.TimeoutExpired:
            case['status'] = 'timeout'
            raise
        finally:
            case['seconds'] = time.monotonic()-start
        assert result.returncode == 0
        return (directory / 'extract.log').read_text(), (directory / 'extracted.spice').read_text()

    try:
        expected_areas = {'pnp_05p00x00p42': 84000, 'pnp_10p00x00p42': 168000,
                          'pnp_05p00x05p00': 1000000, 'pnp_10p00x10p00': 4000000}
        for model, area in expected_areas.items():
            source = pdk / 'libs.ref/gf180mcu_fd_pr/mag' / f'{model}_0.mag'
            assert sha(source) == lock['primitive_mag_sha256'][model], source
            receipt['inputs'][str(source.relative_to(ROOT))] = sha(source)
            directory = output / model
            directory.mkdir()
            shutil.copyfile(source, directory / source.name)
            log, netlist = extract(directory, source.stem)
            assert 'Device parameters do not match' not in log
            instances = re.findall(r'^X\S+ .+$', netlist, re.M)
            assert len(instances) == 1 and re.fullmatch(r'X\d+ C B E '+model, instances[0]), netlist
            assert re.search(r'^'+re.escape(instances[0])+r'\n\*\*devattr s='+str(area)+r',', netlist, re.M), netlist
            receipt['cases'][-1].update(emitter_area_um2=area*.005*.005,
                                        model=model, pin_order=['C', 'B', 'E'])

        # Widen only the emitter diffusion from .42 to .50 um. Leave its
        # contacts, base and collector untouched. Area=2.5um2 fits no model.
        source = output / 'pnp_05p00x00p42' / 'pnp_05p00x00p42_0.mag'
        directory = output / 'invalid_emitter'
        directory.mkdir()
        lines, layer = [], None
        for line in source.read_text().splitlines():
            if line.startswith('<< '):
                layer = line[3:-3]
            if line.startswith('string GDS_'):
                continue  # diagnostic geometry must not stream the original leaf
            if layer in ('pdiff', 'pdiffc') and line.startswith('rect '):
                rect = list(map(int, line.split()[1:]))
                rect[0] = -50 if rect[0] == -42 else rect[0]
                rect[2] = 50 if rect[2] == 42 else rect[2]
                line = 'rect '+' '.join(map(str, rect))
            lines.append(line)
        (directory / 'invalid.mag').write_text('\n'.join(lines)+'\n')
        log, _ = extract(directory, 'invalid')
        ext = (directory / 'invalid.ext').read_text()
        assert 'Device parameters do not match any extraction model' in log
        assert not re.search(r'^equiv .*"[BCE]".*"[BCE]"', ext, re.M), ext
        assert re.search(r'"E" \d+ 100000,', ext), ext
        receipt['cases'][-1].update(emitter_area_um2=2.5, rejected=True)
        receipt['status'] = 'pass'
    except BaseException as error:
        receipt.update(status='failed', error=repr(error))
        raise
    finally:
        receipt['artifacts'] = {str(p.relative_to(output)): sha(p)
                                for p in sorted(output.rglob('*')) if p.is_file()}
        (output / 'result.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print('PASS four PNP identities/areas/pin orders and distinct-terminal invalid-area control')


if __name__ == '__main__':
    main()

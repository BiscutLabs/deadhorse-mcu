"""Read-only evidence/partition audit for PLAN03; never reruns a solver."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.formal import assertion_names, validate_job
from dv.soc.plan03_debt import CASES


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case', choices=CASES, required=True)
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    folder = (ROOT / a.input).resolve()
    out = (ROOT / a.output).resolve()
    folder.relative_to(ROOT / 'build'); out.relative_to(ROOT / 'build')
    out.mkdir(parents=True, exist_ok=False)
    old_path, top, count, depth, _, _, indices = CASES[a.case]
    old = ROOT / old_path
    receipt = json.loads((folder / 'result.json').read_text())
    baseline_path = old.parent / 'result.json'
    baseline = json.loads(baseline_path.read_text())
    old_jobs = baseline['instructions']['addi']['jobs'] if a.case == 'lite' else baseline['cases'][old.name]['jobs']
    hashes = {str(p.relative_to(ROOT)): digest(p) for p in
              (baseline_path, folder / 'result.json', Path(__file__), ROOT / 'dv/soc/plan03_debt.py')}
    assert receipt['status'] in ('unresolved', 'proved_partition')
    assert [j['index'] for j in receipt['jobs']] == indices
    assert receipt['assumed_siblings'] == receipt['cutpoints'] == []
    for name, expected in receipt['source_sha256'].items():
        source = ROOT / name
        if digest(source) != expected:
            assert name == 'dv/soc/plan03_debt.py' and a.case == 'dma'
            source = folder / 'executed_runner.py'
            assert digest(source) == expected, 'Unbound executed runner'
        hashes[str(source.relative_to(ROOT))] = expected
    for name, expected in receipt['artifact_sha256'].items():
        assert digest(folder / name) == expected, name
        hashes[str((folder / name).relative_to(ROOT))] = expected
    for inventory in receipt['historical_evidence'].values():
        for name, expected in inventory.items():
            assert digest(ROOT / name) == expected, name
            hashes[name] = expected
    # Bind original configs, prepared models, witnesses and logs to their
    # historical receipt, in addition to fresh emission identity.
    for name, expected in baseline['artifact_sha256'].items():
        if name.startswith(old.name + '/'):
            source = old.parent / name
            assert digest(source) == expected, name
            hashes[str(source.relative_to(ROOT))] = expected
    fault_properties = ({'corrupt': {'d.' + assertion_names(10)[1]}} if a.case == 'dma' else
                        {'corrupt': {assertion_names(14)[5]}} if a.case == 'lite' else
                        {'early': {assertion_names(12)[1], assertion_names(12)[7]},
                         'hold': {assertion_names(12)[3]},
                         'retention': {assertion_names(12)[0], assertion_names(12)[1], assertion_names(12)[3]}})
    witnesses = []
    expected_reset = "fminit -seq por_n 0,'z -seq reset_n 0,'z" if a.case == 'watchdog' else "fminit -seq reset_n 0,'z"
    expected_assumes = 2 if a.case == 'watchdog' else 1
    for job in old_jobs:
        variant = job['variant']
        config = (old / (variant + '.sby')).read_text()
        assert expected_reset in config and f'select -assert-count {expected_assumes} t:$assume' in config
        for name, expected in receipt['model_sha256'][variant].items():
            assert digest(folder / 'emit' / variant / name) == expected
            assert digest(old / variant / 'src' / name) == expected
        if a.case == 'lite':
            model = ROOT / 'hw/vendor/ibex_ref/riscv-formal/insns/insn_addi.v'
            assert digest(old / variant / 'src' / model.name) == digest(model)
            hashes[str(model.relative_to(ROOT))] = digest(model)
        if variant != 'correct':
            failed = validate_job(old / variant, 'cover' if variant == 'cover' else 'negative',
                                  job['returncode'], job['solver_status'], fault_properties.get(variant))
            witnesses.append(dict(variant=variant, failed_properties=failed))
    template = (old / 'correct.sby').read_text().replace(str(old / 'emit'), str(folder / 'emit'))
    old_engine = template.split('[engines]\n', 1)[1].split('[script]', 1)[0]
    engine = 'smtbmc z3' if a.case == 'dma' else 'abc pdr'
    template = template.replace('[engines]\n' + old_engine, '[engines]\n' + engine + '\n')
    stats = []
    for job in receipt['jobs']:
        index = job['index']; prop = ('d.' if a.case == 'dma' else '') + assertion_names(count)[index]
        marker = f'select -assert-count {count} t:$assert'
        expected = template.replace(marker, marker + '\n' + '\n'.join([
            f'select -assert-count 1 c:{prop}', f'delete t:$assert c:{prop} %d',
            'select -assert-count 1 t:$assert', 'select *', 'opt_clean']))
        name = f'property-{index}'
        assert (folder / (name + '.sby')).read_text() == expected
        actual_status = (folder / name / 'status').read_text().split()
        assert actual_status[0] == job['status']
        assert int(actual_status[1]) == job['returncode']
        if job['status'] == 'PASS':
            validate_job(folder / name, 'proof', job['returncode'], 'PASS')
        else:
            assert job['status'] == 'TIMEOUT' and job['returncode'] == 8
        model = out / (name + '.json')
        with (out / (name + '.log')).open('w') as log:
            subprocess.run(['yosys', '-Q', '-T', '-p',
                f'read_rtlil {folder/name}/model/design.il; stat; write_json {model}'],
                cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
        cells = json.loads(model.read_text())['modules'][top]['cells']
        assert sum(c['type'] == '$assert' for c in cells.values()) == 1
        assert {n for n, c in cells.items() if c['type'] == '$assert'} == {prop}
        assert sum(c['type'] == '$assume' for c in cells.values()) == expected_assumes
        stats.append(dict(index=index, cells=len(cells), sequential_bits=sum(
            len(c['connections'].get('Q', [])) for c in cells.values()
            if 'dff' in c['type'] or c['type'] in ('$ff', '$anyinit')),
            memories=sum(c['type'].startswith('$mem') for c in cells.values())))
    result = dict(status='pass', scope='Evidence/partition audit, not closure of unresolved or unqualified claims',
                  evidence_sha256=hashes, witnesses=witnesses, stats=stats,
                  fault_coverage_limit='Existing faults target listed assertions only; other singleton fault qualification remains open',
                  addi_trivial_indices=[6, 9, 10, 11, 12] if a.case == 'lite' else [])
    result['artifact_sha256'] = {str(p.relative_to(out)): digest(p) for p in out.iterdir() if p.is_file()}
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS', a.case, 'exact partition and concrete evidence audit', flush=True)


if __name__ == '__main__':
    main()

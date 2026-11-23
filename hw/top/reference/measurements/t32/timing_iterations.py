"""Bounded T32 mapped-cell sizing experiment; never changes RTL or STA limits."""
import argparse
import copy
import csv
import hashlib
import itertools
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from tools.physical.usb_cells import signature
from tools.timing.usb_boundary import groups
from tools.timing.usb_async import boolean_function
from tools.timing.check import electrical_checks

PREFIX = 'gf180mcu_fd_sc_mcu7t5v0__'
TOP = 'DeadhorsePerfCore'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def audit(before, after, replacements, cells):
    normalized = copy.deepcopy(after)
    for name, entry in replacements.items():
        old, new = entry['old'], entry['new']
        assert before['cells'][name]['type'] == old
        assert after['cells'][name]['type'] == new
        left, right = signature(cells[old]), signature(cells[new])
        assert left == right and not left['ff'], 'Changed cell function/state'
        expected = {p: r['direction'] for p, r in left['pins'].items()}
        for model in (before, after):
            cell = model['cells'][name]
            assert cell['port_directions'] == expected
            assert set(cell['connections']) == set(expected)
            assert all(len(b) == 1 for b in cell['connections'].values())
        normalized['cells'][name]['type'] = old
    assert normalized == before, 'Changed connectivity, ports, state or aliases'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--minimum-delay', type=float, default=1.2)
    parser.add_argument('--max-current-drive', type=int, default=1)
    args = parser.parse_args()
    base, out = args.base.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    lib = ROOT/'build/riscay-mcu/.tools/physical/pdk/gf180mcu_fd_sc_mcu7t5v0__ss_125C_3v00.lib'
    receipt = dict(status='running', commands=[], base=str(base),
                   revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                   producer_sha256=sha(__file__), liberty_sha256=sha(lib),
                   parameters=vars(args) | {'base': str(base), 'output': str(out)})

    def run(command, label):
        start = time.monotonic()
        with (out/(label+'.log')).open('w') as stream:
            code = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT).returncode
        receipt['commands'].append(dict(command=command, returncode=code,
                                        seconds=time.monotonic()-start))
        assert code == 0, label

    try:
        source = base/'candidate.json'
        receipt['inputs'] = {str(p): sha(p) for p in
                             (source, base/'mapped.v', base/'sta.log', base/'timing.tcl')}
        data = json.loads(source.read_text())
        before = data['modules'][TOP]
        cells = dict(groups(lib.read_text(), 'cell'))
        # Protect all combinational fan-in of clock/reset/gate-control pins.
        protected = {b for c in before['cells'].values() for p, bits in c['connections'].items()
                     if p in ('CLK', 'CLKN', 'RN', 'SETN', 'E', 'TE') for b in bits}
        while True:
            previous = set(protected)
            for c in before['cells'].values():
                if any(p in c['connections'] for p in ('CLK', 'CLKN')):
                    continue
                outputs = {b for p, bits in c['connections'].items()
                           if c['port_directions'][p] == 'output' for b in bits}
                if outputs & protected:
                    protected.update(b for p, bits in c['connections'].items()
                                     if c['port_directions'][p] == 'input' for b in bits)
            if previous == protected:
                break
        # Only max data paths in the prior report; min paths are never candidates.
        delays = {}
        active = False
        for line in (base/'sta.log').read_text().splitlines():
            if line.startswith('Path Type:'):
                active = line.strip() == 'Path Type: max'
            match = re.match(r'\s*([0-9.]+)\s+[0-9.]+\s+[\^v]\s+(\S+)/\S+\s+\(', line)
            if active and match:
                delays[match[2]] = max(delays.get(match[2], 0), float(match[1]))
        after = copy.deepcopy(before)
        replacements, excluded = {}, []
        for name, delay in sorted(delays.items()):
            c = before['cells'][name]
            match = re.fullmatch(re.escape(PREFIX)+r'(\w+)_([1248])', c['type'])
            if not match or delay < args.minimum_delay or int(match[2]) > args.max_current_drive:
                continue
            new = PREFIX + match[1] + '_' + str(int(match[2])*2)
            if new not in cells or any(p in c['connections'] for p in ('CLK', 'CLKN')):
                continue
            outputs = {b for p, bits in c['connections'].items()
                       if c['port_directions'][p] == 'output' for b in bits}
            if outputs & protected:
                excluded.append(name)
                continue
            left, right = signature(cells[c['type']]), signature(cells[new])
            assert left == right and not left['ff']
            replacements[name] = dict(old=c['type'], new=new, prior_increment_ns=delay)
            after['cells'][name]['type'] = new
        assert replacements, 'No eligible sizing candidate'
        audit(before, after, replacements, cells)
        # Qualify each distinct library pair for every scalar input assignment.
        truth_tables = {}
        for old, new in sorted({(r['old'], r['new']) for r in replacements.values()}):
            left, right = signature(cells[old]), signature(cells[new])
            inputs = sorted(p for p, r in left['pins'].items() if r['direction'] == 'input')
            outputs = sorted(p for p, r in left['pins'].items() if r['direction'] == 'output')
            for bits in itertools.product((False, True), repeat=len(inputs)):
                values = dict(zip(inputs, bits))
                for pin in outputs:
                    assert boolean_function(left['pins'][pin]['function'], values) == boolean_function(right['pins'][pin]['function'], values)
            truth_tables[old+' -> '+new] = dict(assignments=2**len(inputs), outputs=outputs)
        first = next(iter(replacements))
        fault = copy.deepcopy(after)
        pin = next(p for p, d in fault['cells'][first]['port_directions'].items() if d == 'input')
        old_bit = fault['cells'][first]['connections'][pin][0]
        fault['cells'][first]['connections'][pin] = ['1' if old_bit == '0' else '0']
        try:
            audit(before, fault, replacements, cells)
        except AssertionError:
            pass
        else:
            raise AssertionError('Wrong-pin fault survived')
        fault = copy.deepcopy(after)
        fault['cells'][first]['type'] = PREFIX+'inv_1'
        try:
            audit(before, fault, replacements, cells)
        except AssertionError:
            pass
        else:
            raise AssertionError('Wrong-family fault survived')
        data['modules'][TOP] = after
        write(out/'candidate.json', data)
        write(out/'transform.json', dict(replacements=replacements, excluded=excluded,
              truth_tables=truth_tables, wrong_pin_rejected=True, wrong_family_rejected=True,
              protected_bits=len(protected), exact_normalized_graph=True))
        (out/'export.ys').write_text(f'read_json "{out}/candidate.json"\nhierarchy -check -top {TOP}\ncheck -assert\nstat -liberty "{lib}"\nwrite_verilog -noattr -noexpr "{out}/mapped.v"\n')
        run(['yosys', '-Q', '-T', '-s', str(out/'export.ys')], 'export')
        (out/'timing.tcl').write_text((base/'timing.tcl').read_text().replace(str(base), str(out)))
        run(['sta', '-no_init', '-exit', str(out/'timing.tcl')], 'sta')
        log = (out/'sta.log').read_text()
        assert 'TIMING_COMPLETE' in log and not re.search(r'^Error:', log, re.M)
        rows = list(csv.DictReader((out/'paths.tsv').open(), delimiter='\t'))
        worst = max(rows, key=lambda r: float(r['delay_ns']))
        classes = {}
        for r in rows:
            kind = r.get('kind', r.get('class', 'all'))
            if kind not in classes or float(r['delay_ns']) > float(classes[kind]['delay_ns']):
                classes[kind] = r
        gates = list(csv.DictReader((out/'gate_checks.tsv').open(), delimiter='\t'))
        assert gates
        electrical = electrical_checks(log)
        area = {n: float(re.search(r'\barea\s*:\s*([0-9.]+)', body)[1])
                for n, body in cells.items() if re.search(r'\barea\s*:', body)}
        delta = sum(area[r['new']]-area[r['old']] for r in replacements.values())
        budget = 0.60*1000/9
        ok = (float(worst['delay_ns']) <= budget and
              electrical['max_capacitance_and_slew_violations'] == 0 and
              min(float(g['slack_ns']) for g in gates) >= 0)
        receipt.update(status='pass' if ok else 'fail', worst=worst, classes=classes,
                       budget_ns=budget, replacements=len(replacements),
                       area_delta_um2=delta, electrical=electrical,
                       gate_min_slack_ns=min(float(g['slack_ns']) for g in gates),
                       qualification='Mapped pre-layout diagnostic; unchanged constraints, no production-flow acceptance or physical signoff.')
    except Exception as error:
        receipt.update(status='error', error=repr(error))
        raise
    finally:
        receipt['artifacts'] = {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'result.json'}
        write(out/'result.json', receipt)
        print(json.dumps({k: receipt.get(k) for k in ('status', 'worst', 'replacements', 'area_delta_um2', 'error')}), flush=True)


if __name__ == '__main__':
    main()

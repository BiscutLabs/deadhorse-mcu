"""T20 description validation; no SoC RTL or acceptance claim."""
from pathlib import Path
import argparse
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import yaml
from hw.regmap.regmap import UniqueLoader, load as load_regmap


def check(ok, message):
    if not ok:
        raise ValueError(message)


def keys(value, required, optional=()):
    check(isinstance(value, dict), 'Expected mapping')
    check(set(required) <= set(value) <= set(required) | set(optional), 'Missing or unknown keys')


def number(value, low, high):
    return type(value) is int and low <= value <= high


def name(value):
    check(isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9_]*', value), 'Invalid name')


def validate(data):
    keys(data, ('schema', 'name', 'clocks', 'resets', 'masters', 'regions', 'interrupts', 'pins'))
    check(type(data['schema']) is int and data['schema'] == 1, 'Unsupported schema')
    name(data['name'])
    check(isinstance(data['clocks'], dict) and data['clocks'], 'Missing clocks')
    for n, c in data['clocks'].items():
        name(n); keys(c, ('hz', 'source'))
        check(c['source'] == 'external_test_input', 'Unimplemented clock source')
        check(isinstance(c['hz'], list) and c['hz'] and
              all(number(h, 1, 100000000) for h in c['hz']), 'Invalid frequency')
    check(isinstance(data['resets'], list) and data['resets'], 'Missing resets')
    for n in data['resets']: name(n)
    check(len(set(data['resets'])) == len(data['resets']), 'Duplicate reset')
    check(isinstance(data['masters'], dict) and data['masters'], 'Missing masters')
    origins = set()
    for n, m in data['masters'].items():
        name(n); keys(m, ('origin', 'implementation'))
        check(number(m['origin'], 0, 7) and m['origin'] not in origins, 'Duplicate/invalid origin')
        origins.add(m['origin'])
        check(m['implementation'] in ('real', 'test_standin', 'inactive'), 'Invalid master kind')
    check(isinstance(data['regions'], list) and data['regions'], 'Missing regions')
    seen = set()
    for r in data['regions']:
        keys(r, ('name', 'base', 'size', 'home', 'domains', 'kind', 'reset'), ('regmap',))
        name(r['name']); check(r['name'] not in seen, 'Duplicate region'); seen.add(r['name'])
        check(number(r['base'], 0, 0xffffffff) and number(r['size'], 4, 1 << 32), 'Invalid range')
        check(r['base'] % 4 == 0 and r['size'] % 4 == 0 and
              r['base'] + r['size'] <= 1 << 32, 'Unaligned/wrapped range')
        check(isinstance(r['home'], str) and r['home'], 'Invalid home')
        check(isinstance(r['domains'], list) and r['domains'], 'Missing domains')
        check(all(d in data['clocks'] for d in r['domains']) and
              len(set(r['domains'])) == len(r['domains']), 'Invalid domains')
        check(r['reset'] in data['resets'], 'Unknown reset')
        check(r['kind'] in ('model', 'stub', 'real', 'local_pair', 'optional_usb', 'reserved'), 'Invalid kind')
        check(r['kind'] not in ('real', 'local_pair', 'optional_usb') or 'regmap' in r,
              'Implemented register target requires regmap')
        if 'regmap' in r:
            check(isinstance(r['regmap'], str), 'Invalid regmap path')
            path = (ROOT / r['regmap']).resolve()
            check(path.is_relative_to(ROOT / 'hw/ip'), 'Regmap outside IP tree')
            regs = load_regmap(path)
            check((1 << regs['address_width']) <= r['size'], 'Regmap exceeds window')
            check(r['base'] % (1 << regs['address_width']) == 0, 'Regmap base alignment')
    for i, a in enumerate(data['regions']):
        for b in data['regions'][:i]:
            if set(a['domains']) & set(b['domains']):
                check(a['base'] + a['size'] <= b['base'] or
                      b['base'] + b['size'] <= a['base'], 'Overlapping regions')
    check(isinstance(data['interrupts'], dict), 'Invalid interrupts')
    indices = list(data['interrupts'].values())
    check(all(number(i, 0, 14) for i in indices) and len(set(indices)) == len(indices), 'Invalid/duplicate interrupt')
    check(set(data['interrupts']) <= seen, 'Interrupt source missing')
    check(isinstance(data['pins'], dict) and data['pins'], 'Missing pins')
    for n, p in data['pins'].items():
        name(n); keys(p, ('width', 'direction', 'clock', 'safe'))
        check(number(p['width'], 1, 32) and p['clock'] in data['clocks'], 'Invalid pin width/clock')
        safe = {'input': 'input', 'output': 'disabled', 'bidirectional': 'disabled', 'open_drain': 'released'}
        check(p['direction'] in safe and p['safe'] == safe[p['direction']], 'Unsafe pin default')
    return data


def contract_rows(text):
    rows = []
    for line in text.splitlines():
        fields = [x.strip() for x in line.split('|')]
        if len(fields) == 7 and re.fullmatch(r'0x[0-9a-f]+', fields[2]):
            rows.append((fields[1], int(fields[2], 16), int(fields[3], 16), fields[4]))
    return rows


def check_contract(data, text):
    actual = [(r['name'], r['base'], r['size'], r['home']) for r in data['regions']]
    check(contract_rows(text) == actual, 'Contract address table differs')
    irq_rows = []
    for line in text.splitlines():
        fields = [x.strip() for x in line.split('|')]
        if len(fields) == 5 and fields[2].isdigit():
            irq_rows.append((fields[1], int(fields[2])))
    check(sorted(irq_rows) == sorted(data['interrupts'].items()), 'Contract interrupt table differs')


def emit(data, output):
    output = output.resolve()
    check(output.is_relative_to(ROOT / 'build'), 'Output must be under build')
    output.mkdir(parents=True, exist_ok=True)
    for filename in ('soc.h', 'SocMap.scala', 'soc-map.md', 'soc.json'):
        path = output / filename
        check(not path.is_symlink() and path.resolve().parent == output,
              'Output file must not be a symlink or escape its directory')
    header = ['/* T20 provisional generated map; not a frozen ABI. */', '#pragma once']
    scala = ['package deadhorse.top', '', 'object SocMap {',
             '  final case class Region(name: String, base: BigInt, size: BigInt)',
             '  val regions = Seq(']
    markdown = ['| Endpoint | Base | Size | Home |', '| --- | --- | --- | --- |']
    for r in data['regions']:
        n = r['name'].upper()
        header += [f'#define DH_SOC_{n}_BASE 0x{r["base"]:08x}u', f'#define DH_SOC_{n}_SIZE 0x{r["size"]:x}u']
        scala.append(f'    Region("{r["name"]}", BigInt("{r["base"]:x}",16), BigInt("{r["size"]:x}",16)),')
        markdown.append(f'| {r["name"]} | 0x{r["base"]:08x} | 0x{r["size"]:x} | {r["home"]} |')
    scala[-1] = scala[-1].removesuffix(',')
    scala += ['  )', '  val fastInterrupts = Map(']
    for n, i in data['interrupts'].items():
        header.append(f'#define DH_SOC_{n.upper()}_FAST_IRQ {i}u')
        scala.append(f'    "{n}" -> {i},')
    if data['interrupts']: scala[-1] = scala[-1].removesuffix(',')
    scala += ['  )', '}']
    for filename, lines in [('soc.h', header), ('SocMap.scala', scala), ('soc-map.md', markdown)]:
        (output / filename).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (output / 'soc.json').write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, default=Path(__file__).with_name('soc.yaml'))
    p.add_argument('--output', type=Path, default=ROOT / 'build/t20/map')
    args = p.parse_args()
    data = validate(yaml.load(args.config.read_text(encoding='utf-8'), Loader=UniqueLoader))
    check_contract(data, (ROOT / 'docs/spec/soc.md').read_text(encoding='utf-8'))
    emit(data, args.output)
    print(f'PASS provisional SoC map: {len(data["regions"])} regions; not RTL or pin-fit acceptance')


if __name__ == '__main__':
    main()

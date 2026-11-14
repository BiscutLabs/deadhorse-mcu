"""Validate a register description and emit expanded JSON, C and Markdown."""
import argparse
import copy
import json
from pathlib import Path
import re
import sys

import yaml

try:
    from .keywords import KEYWORDS
except ImportError:
    from keywords import KEYWORDS

ACCESS = {'rw', 'ro', 'w1c', 'w1p', 'rwh', 'wo'}
STORED = {'rw', 'w1c', 'rwh'}


class RegmapError(ValueError):
    def __init__(self, code, message):
        super().__init__(f'{code}: {message}')


def require(ok, code, message):
    if not ok:
        raise RegmapError(code, message)


def integer(value):
    return type(value) is int


def mapping(value, allowed, required, context):
    require(isinstance(value, dict), 'REGMAP_SCHEMA', f'{context} must be a mapping')
    unknown = set(value) - set(allowed)
    require(not unknown, 'REGMAP_UNKNOWN_KEY', f'{context}: unknown keys {sorted(map(str, unknown))}')
    require(set(required) <= set(value), 'REGMAP_SCHEMA', f'{context}: missing required key')
    require(isinstance(value.get('description', ''), str), 'REGMAP_SCHEMA', f'{context}: description must be text')


def name(value):
    require(isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9]*(?:_[a-z0-9]+)*', value)
            and value not in KEYWORDS, 'REGMAP_NAME', f'invalid name {value!r}')


class UniqueLoader(yaml.SafeLoader):
    """Do not silently discard repeated YAML keys before validation."""


def unique_mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        require(isinstance(key, str), 'REGMAP_SCHEMA', 'YAML keys must be strings')
        require(key not in result, 'REGMAP_DUP', f'duplicate YAML key {key}')
        result[key] = loader.construct_object(value_node)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def validate(raw, directory_name=None):
    mapping(raw, ('block', 'description', 'data_width', 'address_width', 'registers'),
            ('block', 'data_width', 'address_width', 'registers'), 'block')
    name(raw['block'])
    require(directory_name is None or raw['block'] == directory_name,
            'REGMAP_NAME', 'block must equal its directory name')
    require(integer(raw['data_width']) and raw['data_width'] == 32,
            'REGMAP_SCHEMA', 'data_width must be 32')
    aw = raw['address_width']
    require(integer(aw) and aw >= 2, 'REGMAP_SCHEMA', 'address_width must be an integer >= 2')
    require(isinstance(raw['registers'], list), 'REGMAP_SCHEMA', 'registers must be a list')
    result = dict(schema_version=1, block=raw['block'], description=raw.get('description', ''),
                  data_width=32, address_width=aw, registers=[])
    source_names, expanded_names, offsets, ports = set(), set(), set(), set()
    for reg in raw['registers']:
        mapping(reg, ('name', 'offset', 'description', 'count', 'fields'), ('name', 'offset', 'fields'), 'register')
        name(reg['name'])
        require(reg['name'] not in source_names, 'REGMAP_DUP', f'duplicate register {reg["name"]}')
        source_names.add(reg['name'])
        count, offset = reg.get('count', 1), reg['offset']
        require(integer(count) and count > 0, 'REGMAP_SCHEMA', 'count must be a positive integer')
        require(integer(offset), 'REGMAP_SCHEMA', 'offset must be an integer')
        require(offset % 4 == 0, 'REGMAP_OFFSET_ALIGN', f'{reg["name"]}: offset {offset}')
        require(offset >= 0 and offset + 4 * count <= 1 << aw,
                'REGMAP_OFFSET_RANGE', f'{reg["name"]}: register/array exceeds address range')
        require(isinstance(reg['fields'], list), 'REGMAP_SCHEMA', 'fields must be a list')
        fields, field_names, used_bits = [], set(), set()
        for field in reg['fields']:
            mapping(field, ('name', 'bits', 'access', 'reset', 'description'), ('name', 'bits', 'access'), 'field')
            name(field['name'])
            require(field['name'] not in field_names, 'REGMAP_DUP', f'duplicate field {field["name"]}')
            field_names.add(field['name'])
            bits = field['bits']
            if integer(bits):
                msb = lsb = bits
            else:
                require(isinstance(bits, list) and len(bits) == 2 and all(integer(b) for b in bits),
                        'REGMAP_BITS', 'bits must be an index or [msb, lsb]')
                msb, lsb = bits
            require(0 <= lsb <= msb <= 31, 'REGMAP_BITS', f'invalid bits {bits}')
            selected = set(range(lsb, msb + 1))
            require(not used_bits & selected, 'REGMAP_OVERLAP_FIELD', f'{reg["name"]}.{field["name"]}')
            used_bits |= selected
            access = field['access']
            require(isinstance(access, str) and access in ACCESS, 'REGMAP_ACCESS', f'unknown access {access!r}')
            width = msb - lsb + 1
            if 'reset' in field:
                require(access in STORED and integer(field['reset']) and 0 <= field['reset'] < 1 << width,
                        'REGMAP_RESET', f'{reg["name"]}.{field["name"]}: invalid reset')
            item = dict(name=field['name'], lsb=lsb, msb=msb, width=width,
                        access=access, description=field.get('description', ''))
            if access in STORED:
                item['reset'] = field.get('reset', 0)
            fields.append(item)
        for index in range(count):
            regname = reg['name'] + (str(index) if 'count' in reg else '')
            address = offset + index * 4
            require(regname not in expanded_names, 'REGMAP_DUP', f'duplicate expanded name {regname}')
            require(address not in offsets, 'REGMAP_OVERLAP_REG', f'overlapping offset {address:#x}')
            expanded_names.add(regname)
            offsets.add(address)
            for field in fields:
                # Concatenated names must remain unique for both ports and C macros.
                prefix = f'{regname}_{field["name"]}'
                require(prefix not in ports, 'REGMAP_DUP', f'colliding field prefix {prefix}')
                ports.add(prefix)
            result['registers'].append(dict(name=regname, offset=address,
                                           description=reg.get('description', ''), fields=copy.deepcopy(fields)))
    return result


def load(path):
    path = Path(path)
    try:
        raw = yaml.load(path.read_text(encoding='utf-8'), Loader=UniqueLoader)
    except (yaml.YAMLError, UnicodeError) as exc:
        raise RegmapError('REGMAP_SCHEMA', str(exc)) from exc
    return validate(raw, path.parent.name)


def emit(description, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    block = description['block']
    prefix = f'DH_{block.upper()}'
    guard = prefix + '_REGS_H'
    header = [f'#ifndef {guard}', f'#define {guard}', '', '#include <stdint.h>', '']
    table = [f'# {block} registers', '', '| Register | Offset | Field | Bits | Access | Reset | Description |',
             '| --- | --- | --- | --- | --- | --- | --- |']
    def escaped(text):
        return text.replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')
    for reg in description['registers']:
        stem = f'{prefix}_{reg["name"].upper()}'
        header.append(f'#define {stem}_OFFSET 0x{reg["offset"]:02X}u')
        for field in reg['fields']:
            key = f'{stem}_{field["name"].upper()}'
            mask = ((1 << field['width']) - 1) << field['lsb']
            header.extend((f'#define {key}_SHIFT {field["lsb"]}u',
                           f'#define {key}_MASK UINT32_C(0x{mask:08X})'))
            table.append(f'| {reg["name"]} | 0x{reg["offset"]:02X} | {field["name"]} | '
                         f'{field["msb"]}:{field["lsb"]} | {field["access"]} | '
                         f'{field.get("reset", "-")} | {escaped(field["description"])} |')
        header.append('')
    header.append(f'#endif /* {guard} */')
    interchange = copy.deepcopy(description)
    for reg in interchange['registers']:
        reg['offset'] = str(reg['offset'])  # Exact even in JSON readers backed by Double.
    for suffix, content in (('json', json.dumps(interchange, indent=2)),
                            ('h', '\n'.join(header)), ('md', '\n'.join(table))):
        (output / f'{block}_regs.{suffix}').write_text(content + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('description', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        description = load(args.description)
        emit(description, args.out)
    except (RegmapError, OSError) as exc:
        print(str(exc) if isinstance(exc, RegmapError) else f'REGMAP_IO: {exc}', file=sys.stderr)
        return 1
    print(f'PASS regmap: {description["block"]} -> {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

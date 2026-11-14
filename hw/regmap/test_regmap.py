"""Validator diagnostics, artifacts, and independent model known answers."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from hw.regmap.regmap import RegmapError, emit, load, validate
from hw.regmap.model import RegModel

BASE = dict(block='example', data_width=32, address_width=8,
            registers=[dict(name='control', offset=0,
                            fields=[dict(name='value', bits=[15, 0], access='rw', reset=3)])])
FIXTURES = Path('hw/regmap/fixtures')


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.raw = copy.deepcopy(BASE)
        self.reg = self.raw['registers'][0]
        self.field = self.reg['fields'][0]

    def error(self, expected):
        with self.assertRaisesRegex(RegmapError, '^' + expected + ':'):
            validate(self.raw)

    def test_name(self):
        for value in ('Bad', 'module', 'switch', 'always_ff', 'true', 'bad__name'):
            with self.subTest(value=value):
                self.field['name'] = value
                self.error('REGMAP_NAME')

    def test_offset_align(self):
        self.reg['offset'] = 2
        self.error('REGMAP_OFFSET_ALIGN')

    def test_offset_range(self):
        for offset, count in ((256, 1), (-4, 1), (252, 2)):
            with self.subTest(offset=offset, count=count):
                self.reg.update(offset=offset, count=count)
                self.error('REGMAP_OFFSET_RANGE')

    def test_overlap_reg(self):
        other = copy.deepcopy(self.reg)
        other['name'] = 'other'
        self.raw['registers'].append(other)
        self.error('REGMAP_OVERLAP_REG')

    def test_overlap_field(self):
        self.reg['fields'].append(dict(name='other', bits=15, access='rw'))
        self.error('REGMAP_OVERLAP_FIELD')

    def test_bits(self):
        self.field.pop('reset')
        for bits in (-1, 32, [2, 3], [1], [True, 0], '3:0'):
            with self.subTest(bits=bits):
                self.field['bits'] = bits
                self.error('REGMAP_BITS')

    def test_reset(self):
        for access, value in (('rw', 65536), ('rw', -1), ('rw', True),
                              ('ro', 0), ('wo', 0), ('w1p', 0)):
            with self.subTest(access=access, value=value):
                self.field.update(access=access, reset=value)
                self.error('REGMAP_RESET')

    def test_access(self):
        self.field.pop('reset')
        self.field['access'] = 'read_write'
        self.error('REGMAP_ACCESS')

    def test_dup(self):
        other = copy.deepcopy(self.reg)
        other['offset'] = 4
        self.raw['registers'].append(other)
        self.error('REGMAP_DUP')

    def test_unknown_key(self):
        for target in (self.raw, self.reg, self.field):
            target['unexpected'] = 1
            self.error('REGMAP_UNKNOWN_KEY')
            del target['unexpected']

    def test_expansion_and_field_name_collisions(self):
        self.reg.update(name='value', count=2)
        other = dict(name='value1', offset=8, fields=[])
        self.raw['registers'].append(other)
        self.error('REGMAP_DUP')
        self.raw = dict(block='example', data_width=32, address_width=8, registers=[
            dict(name='a_b', offset=0, fields=[dict(name='c', bits=0, access='rw')]),
            dict(name='a', offset=4, fields=[dict(name='b_c', bits=0, access='ro')])])
        self.error('REGMAP_DUP')

    def test_schema_types_and_required_keys(self):
        for key, value in (('data_width', 64), ('address_width', True), ('registers', {})):
            original = self.raw[key]
            self.raw[key] = value
            self.error('REGMAP_SCHEMA')
            self.raw[key] = original
        del self.raw['block']
        self.error('REGMAP_SCHEMA')

    def test_fixture_header_and_json(self):
        Path('build/t05').mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir='build/t05') as directory:
            out = Path(directory)
            description = load(FIXTURES / 'coverage/coverage.regmap.yaml')
            emit(description, out)
            header = (out / 'coverage_regs.h').read_text()
            self.assertIn('#define DH_COVERAGE_VALUE8_OFFSET 0xA0u', header)
            self.assertIn('#define DH_COVERAGE_STATUS_LIVE_SHIFT 5u', header)
            self.assertIn('#define DH_COVERAGE_STATUS_LIVE_MASK UINT32_C(0x00FFFFE0)', header)
            self.assertIn('#ifndef DH_COVERAGE_REGS_H', header)
            self.assertIn('#endif /* DH_COVERAGE_REGS_H */', header)
            encoded = copy.deepcopy(description)
            for reg in encoded['registers']:
                reg['offset'] = str(reg['offset'])
            self.assertEqual(json.loads((out / 'coverage_regs.json').read_text()), encoded)
            self.assertIn('| value8 | 0xA0 | v | 15:0 | rw | 0 |', (out / 'coverage_regs.md').read_text())
            self.assertEqual({f['access'] for r in description['registers'] for f in r['fields']},
                             {'rw', 'ro', 'w1c', 'w1p', 'rwh', 'wo'})

    def test_cli_errors_and_duplicate_yaml_keys(self):
        Path('build/t05').mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir='build/t05') as directory:
            out = Path(directory)
            source = out / 'bad.regmap.yaml'
            for text, code in (('block: first\nblock: second\n', 'REGMAP_DUP'),
                               ('block: [', 'REGMAP_SCHEMA'), (b'\xff', 'REGMAP_SCHEMA')):
                source.write_bytes(text if isinstance(text, bytes) else text.encode('utf-8'))
                result = subprocess.run([sys.executable, 'hw/regmap/regmap.py', str(source),
                                         '--out', str(out / 'output')], capture_output=True, text=True)
                self.assertEqual(result.returncode, 1)
                self.assertTrue(result.stderr.startswith(code + ':'), result.stderr)
                self.assertFalse((out / 'output').exists())

    def test_large_offsets_remain_exact(self):
        self.raw['address_width'] = 66
        self.reg['offset'] = (1 << 65) + 4
        description = validate(self.raw)
        Path('build/t05').mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir='build/t05') as directory:
            emit(description, directory)
            path = Path(directory) / 'example_regs.json'
            decoded = json.loads(path.read_text())
            self.assertEqual(decoded['registers'][0]['offset'], str((1 << 65) + 4))
            model = RegModel(path)
            self.assertEqual(model.request(False, (1 << 65) + 4, 0, 0), (3, False))
            self.assertEqual(model.request(False, 1 << 65, 0, 0), (0, True))


class ModelKnownAnswers(unittest.TestCase):
    def setUp(self):
        self.model = RegModel(load(FIXTURES / 'coverage/coverage.regmap.yaml'))

    def test_masked_store_and_hardware_priority(self):
        m = self.model
        self.assertEqual(m.request(True, 0, 0x12345678, 1), (0, False))
        self.assertEqual(m.request(False, 0, 0, 0), (0xAABBCC78, False))
        m.request(True, 0x10, 0xFFFFFFFF, 2)
        self.assertEqual(m.outputs()['counter_value_q'], 0x8765FF21)
        m.drive({'counter_value_we': 1, 'counter_value_d': 17})
        m.request(True, 0x10, 0xFFFFFFFF, 15)
        self.assertEqual(m.outputs()['counter_value_q'], 17)

    def test_ro_w1c_and_pulses(self):
        m = self.model
        m.drive({'status_live_d': 7, 'events_flags_set': 3})
        self.assertEqual(m.request(False, 4, 0, 0), (224, False))
        m.request(True, 4, 0xFFFFFFFF, 15)
        self.assertEqual(m.inputs['status_live_d'], 7)
        m.request(True, 8, 0xFFFFFFFF, 15)
        self.assertEqual(m.outputs()['events_flags_q'], 3)
        m.request(True, 12, 0xFFFFFFFF, 1)
        self.assertEqual(m.outputs()['command_go_pulse'], 15)
        m.idle()
        self.assertEqual(m.outputs()['command_go_pulse'], 0)

    def test_commands_errors_and_zero_mask(self):
        m = self.model
        self.assertEqual(m.request(True, 0x14, 0, 1), (0, True))
        self.assertEqual(m.outputs()['key_payload_we'], 0)
        self.assertEqual(m.request(True, 0x14, 0, 15), (0, False))
        self.assertEqual(m.outputs()['key_payload_we'], 1)
        self.assertEqual(m.request(True, 0x14, 7, 0), (0, False))
        self.assertEqual(m.outputs()['key_payload_we'], 0)
        self.assertEqual(m.request(True, 1, 0, 0), (0, True))
        self.assertEqual(m.request(False, 0xFC, 0, 15), (0, True))

    def test_partial_command_suppresses_other_fields_but_not_hardware(self):
        m = RegModel(load(FIXTURES / 'mixed/mixed.regmap.yaml'))
        m.drive({'mixed_hwvalue_we': 1, 'mixed_hwvalue_d': 23, 'mixed_flags_set': 1})
        self.assertEqual(m.request(True, 0, 0xFFFFFFFF, 13), (0, True))
        out = m.outputs()
        self.assertEqual(out['mixed_setting_q'], 5)
        self.assertEqual(out['mixed_hwvalue_q'], 23)
        self.assertEqual(out['mixed_flags_q'], 11)
        self.assertEqual(out['mixed_pulse_pulse'], 0)
        self.assertEqual(out['mixed_cmd_we'], 0)
        self.assertEqual(out['mixed_other_cmd_we'], 0)
        m.reset()
        self.assertEqual(m.outputs()['mixed_hwvalue_q'], 0xAB)


if __name__ == '__main__':
    unittest.main()

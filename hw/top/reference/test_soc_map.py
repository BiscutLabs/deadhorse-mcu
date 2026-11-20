"""Configuration fault controls; never reads RTL source."""
import copy
import tempfile
from pathlib import Path
import unittest

import yaml
import check_soc_map as soc


class SocMapTests(unittest.TestCase):
    def setUp(self):
        self.model = yaml.load(Path(soc.__file__).with_name('soc.yaml').read_text(), Loader=soc.UniqueLoader)

    def test_current_contract_and_register_windows(self):
        soc.validate(self.model)
        soc.check_contract(self.model, (soc.ROOT / 'docs/spec/soc.md').read_text())

    def test_invalid_configurations_are_rejected(self):
        def region(m): return m['regions'][0]
        faults = {
            'unknown key': lambda m: m.update(typo=True),
            'duplicate origin': lambda m: m['masters']['lite'].update(origin=1),
            'boolean origin': lambda m: m['masters']['lite'].update(origin=False),
            'duplicate region': lambda m: m['regions'].append(copy.deepcopy(region(m))),
            'overlap': lambda m: m['regions'][1].update(base=0),
            'wrap': lambda m: region(m).update(base=0xfffffffc),
            'unaligned': lambda m: region(m).update(base=2),
            'unknown clock': lambda m: region(m).update(domains=['missing']),
            'unknown reset': lambda m: region(m).update(reset='missing'),
            'unknown kind': lambda m: region(m).update(kind='pretend'),
            'small regmap window': lambda m: m['regions'][6].update(size=4),
            'missing regmap': lambda m: m['regions'][6].pop('regmap'),
            'regmap escape': lambda m: m['regions'][6].update(regmap='../outside.yaml'),
            'duplicate IRQ': lambda m: m['interrupts'].update(uart1=0),
            'missing IRQ source': lambda m: m['interrupts'].update(missing=14),
            'bad IRQ': lambda m: m['interrupts'].update(uart0=15),
            'unsafe pin': lambda m: m['pins']['i2c_host'].update(safe='drive_high'),
        }
        for label, fault in faults.items():
            with self.subTest(fault=label):
                changed = copy.deepcopy(self.model); fault(changed)
                with self.assertRaises(ValueError): soc.validate(changed)

    def test_contract_drift_is_rejected(self):
        text = (soc.ROOT / 'docs/spec/soc.md').read_text()
        with self.assertRaisesRegex(ValueError, 'table differs'):
            soc.check_contract(self.model, text.replace('0x40010000', '0x40010500'))

    def test_duplicate_yaml_keys_are_rejected(self):
        with self.assertRaises(ValueError):
            yaml.load('schema: 1\nschema: 2\n', Loader=soc.UniqueLoader)

    def test_interrupt_contract_drift_is_rejected(self):
        self.model['interrupts']['uart0'] = 12
        soc.validate(self.model)
        with self.assertRaisesRegex(ValueError, 'interrupt table differs'):
            soc.check_contract(self.model, (soc.ROOT / 'docs/spec/soc.md').read_text())

    def test_output_symlink_is_rejected_before_any_write(self):
        root = soc.ROOT / 'build/t20'; root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as d:
            parent = Path(d); target = parent / 'preserve.txt'; target.write_text('keep')
            output = parent / 'out'; output.mkdir()
            (output / 'soc.json').symlink_to(target)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                soc.emit(self.model, output)
            self.assertEqual(target.read_text(), 'keep')
            self.assertFalse((output / 'soc.h').exists())

    def test_outputs_and_destination_guard(self):
        root = soc.ROOT / 'build/t20'
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as d:
            output = Path(d); soc.emit(soc.validate(self.model), output)
            self.assertEqual({p.name for p in output.iterdir()}, {'soc.h', 'SocMap.scala', 'soc-map.md', 'soc.json'})
            header = (output / 'soc.h').read_text()
            self.assertIn('#define DH_SOC_RETAINED_SRAM_SIZE 0xc00u', header)
            self.assertIn('#define DH_SOC_FUTURE_BRIDGE_FAST_IRQ 7u', header)
            self.assertIn('"mailbox" -> 5', (output / 'SocMap.scala').read_text())
        with self.assertRaisesRegex(ValueError, 'under build'):
            soc.emit(self.model, soc.ROOT / 'scratch/should-not-emit')


if __name__ == '__main__':
    unittest.main()

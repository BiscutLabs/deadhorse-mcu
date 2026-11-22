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
            'watchdog scope': lambda m: m['watchdog'].update(reset='main_service'),
            'watchdog owner': lambda m: m['watchdog'].update(owners=['lite','performance']),
            'watchdog overlap': lambda m: m['watchdog'].update(offset=0),
            'watchdog boolean count': lambda m: m['watchdog'].update(count=True),
            'boot scope': lambda m: m['boot_control'].update(reset='aon_service'),
            'boot owner': lambda m: m['boot_control'].update(owner='performance'),
            'boot overlap': lambda m: m['boot_control'].update(offset=512),
            'qspi scope': lambda m: m['qspi'].update(reset='main_core'),
            'qspi owner': lambda m: m['qspi'].update(reset_owner='performance'),
            'PWM reset mismatch': lambda m: m['pwm'].update(reset='warm'),
            'PWM alias window': lambda m: m['pwm'].update(size=4096),
            'PWM ownership mismatch': lambda m: m['pwm'].update(owner='lite'),
            'PWM boolean offset': lambda m: m['pwm'].update(offset=False),
            'DMA owner': lambda m: m['dma'].update(owner='lite'),
            'DMA memory': lambda m: m['dma'].update(memory='retained_sram'),
            'DMA reset': lambda m: m['dma'].update(reset='main_core'),
            'DMA size': lambda m: m['dma'].update(size=4096),
            'DMA boolean offset': lambda m: m['dma'].update(offset=False),
            'pinmux owner': lambda m: m['pinmux'].update(owner='lite'),
            'pinmux overlap': lambda m: m['pinmux'].update(offset=256),
            'pinmux reset': lambda m: m['pinmux'].update(reset='main_core'),
            'pinmux arbitrary crossbar': lambda m: m['pinmux'].update(channels=[2,1,0]),
            'pinmux boolean channel': lambda m: m['pinmux'].update(channels=[False,1,2]),
            'pinmux foreign source': lambda m: m['pinmux'].update(sources=['disconnected','gpio','uart','pwm']),
            'unknown kind': lambda m: region(m).update(kind='pretend'),
            'small regmap window': lambda m: m['regions'][6].update(size=4),
            'missing regmap': lambda m: m['regions'][6].pop('regmap'),
            'regmap escape': lambda m: m['regions'][6].update(regmap='../outside.yaml'),
            'duplicate IRQ': lambda m: m['interrupts'].update(uart1=0),
            'missing IRQ source': lambda m: m['interrupts'].update(missing=14),
            'bad IRQ': lambda m: m['interrupts'].update(uart0=15),
            'unsafe pin': lambda m: m['pins']['i2c_host'].update(safe='drive_high'),
            'unknown pin clock': lambda m: m['pins']['jtag_tck'].update(clock='missing'),
            'zero pin width': lambda m: m['pins']['qspi_dq'].update(width=0),
            'unsafe inactive pin': lambda m: m['pins']['jtag_tdo'].update(safe='enabled'),
            'output pad overflow': lambda m: m['pins']['gpio'].update(width=4),
            'input pad overflow': lambda m: m['pins']['adc_miso'].update(width=4),
            'changed slot capacity': lambda m: m['pin_budget'].update(bidirectional=41),
            'missing pin group': lambda m: m['pins'].pop('uart_tx'),
            'renamed pin group': lambda m: m['pins'].update(uart_tx_alias=m['pins'].pop('uart_tx')),
            'duplicate pin alias': lambda m: m['pins'].update(adc_alias=m['pins']['adc_miso']),
            'reduced real pin width': lambda m: m['pins']['uart_rx'].update(width=2),
            'changed pin direction': lambda m: m['pins']['uart_tx'].update(direction='input', safe='input'),
            'group missing member': lambda m: m['groups']['serial']['members'].append('unknown'),
            'group overflow': lambda m: m['groups']['serial'].update(size=256),
            'fabric overflow': lambda m: m['fabrics']['main'].append('uart0'),
            'fabric overlap': lambda m: m['fabrics']['main'].__setitem__(1,'uart0'),
            'missing fabric': lambda m: m['fabrics'].pop('aon'),
            'invalid groups container': lambda m: m.update(groups=[]),
            'invalid fabrics container': lambda m: m.update(fabrics=[]),
            'invalid member type': lambda m: m['groups']['serial']['members'].__setitem__(0,[]),
            'timer overlaps GPIO': lambda m: m['flight_io']['timers'].update(offset=0),
            'timer wrong domain': lambda m: m['flight_io']['timers'].update(clock='aon'),
            'ADC wrong owner': lambda m: m['flight_io']['adc'].update(owner='performance'),
            'ADC wrong size': lambda m: m['flight_io']['adc'].update(size=65536),
            'GPIO wrong map': lambda m: m['flight_io']['gpio'].update(regmap='hw/ip/uart/uart.regmap.yaml'),
            'missing timer service': lambda m: m['flight_io'].pop('aon_timer'),
        }
        for label, fault in faults.items():
            with self.subTest(fault=label):
                changed = copy.deepcopy(self.model); fault(changed)
                with self.assertRaises(ValueError): soc.validate(changed)

    def test_contract_drift_is_rejected(self):
        text = (soc.ROOT / 'docs/spec/soc.md').read_text()
        with self.assertRaisesRegex(ValueError, 'table differs'):
            soc.check_contract(self.model, text.replace('0x40010000', '0x40010500'))

    def test_dma_endpoint_table_is_derived_from_register_contracts(self):
        table=soc.dma_endpoints(soc.validate(self.model))
        self.assertEqual(table['data'][:8], [0x4001000c,0x40010010,0x4001010c,0x40010110,
            0x4001020c,0x40010210,0x40010310,0x40010314])
        self.assertEqual(table['command_value'], [0,2,0,2,0,2,0,4]+[1<<i for i in range(9)])
        self.assertEqual(table['data'][8:], [0x400300c0+4*i for i in range(9)])
        self.assertEqual(table['period'], [0x40030040+4*i for i in range(9)])
        self.assertEqual(table['pending'], 0x4003000c)

    def test_pin_accounting_counts_simultaneous_interfaces_without_sharing(self):
        self.assertEqual(soc.pin_usage(self.model), {'bidirectional': 40, 'input_only': 10})
        for direction, bucket in [('input', 'input_only'), ('output', 'bidirectional'),
                                  ('bidirectional', 'bidirectional'), ('open_drain', 'bidirectional')]:
            model=copy.deepcopy(self.model)
            model['pins']={'test': {'width': 5, 'direction': direction}}
            self.assertEqual(soc.pin_usage(model)[bucket], 5)

    def test_direction_contract_rejects_a_fault_that_still_fits_both_capacities(self):
        model=copy.deepcopy(self.model)
        model['pins']['qspi_sclk'].update(direction='input', safe='input')
        self.assertEqual(soc.pin_usage(model), {'bidirectional': 39, 'input_only': 11})
        with self.assertRaisesRegex(ValueError, 'Logical pin contract differs: qspi_sclk'):
            soc.validate(model)

    def test_xip_binding_rejects_reset_or_owner_drift(self):
        for key,value in [('owner','lite'),('reset','aon_service'),('control','spi_host')]:
            model=copy.deepcopy(self.model);model['qspi_xip'][key]=value
            with self.assertRaisesRegex(ValueError,'XIP binding differs'):
                soc.validate(model)

    def test_duplicate_yaml_keys_are_rejected(self):
        with self.assertRaises(ValueError):
            yaml.load('schema: 1\nschema: 2\n', Loader=soc.UniqueLoader)

    def test_interrupt_contract_drift_is_rejected(self):
        self.model['interrupts']['uart0'] = 13
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
            self.assertIn('#define DH_SOC_IO_TIMERS_BASE 0x40012100u', header)
            self.assertIn('#define DH_SOC_PINMUX_BASE 0x40012200u', header)
            self.assertIn('#define DH_SOC_PINMUX_PWM 3u', header)
            self.assertIn('Region("adc", BigInt("40020000",16)', (output / 'SocMap.scala').read_text())
            self.assertIn('"mailbox" -> 5', (output / 'SocMap.scala').read_text())
        with self.assertRaisesRegex(ValueError, 'under build'):
            soc.emit(self.model, soc.ROOT / 'scratch/should-not-emit')


if __name__ == '__main__':
    unittest.main()

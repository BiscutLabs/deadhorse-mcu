import unittest
from tools.physical.usb_bus_fixture import compose


def module(ports, cells):
    return dict(ports={n: dict(direction=d, bits=bs) for n, (d, bs) in ports.items()}, cells=cells, netnames={})


def flop(d, q, clk):
    return dict(type='test_dff', port_directions={'D': 'input', 'Q': 'output', 'CLK': 'input'},
                connections={'D': [d], 'Q': [q], 'CLK': [clk]}, parameters={})


class CompositionTest(unittest.TestCase):
    def setUp(self):
        self.usb = module({'appClock': ('input', [2]), 'bus_req': ('input', [3]),
                           'bus_rdata': ('output', [5, 5])}, {'capture': flop(3, 5, 2)})
        self.slot = module({'clk': ('input', [2]), 'target_req': ('output', [5]),
                            'target_rdata': ('input', [6, 7]), 'bus_req': ('input', [3])},
                           {'launch': flop(3, 5, 2), 'reply': flop(6, 8, 2), 'reply2': flop(7, 9, 2)})

    def test_exact_shared_clock_bus_and_distinct_internal_nets(self):
        model, audit = compose(self.usb, self.slot)
        self.assertEqual(model['cells']['capture'], self.usb['cells']['capture'])
        self.assertEqual(model['cells']['source_slot_launch']['connections']['Q'], [3])
        self.assertEqual(model['cells']['source_slot_launch']['connections']['CLK'], [2])
        self.assertNotEqual(model['cells']['source_slot_launch']['connections']['D'], [3])
        self.assertEqual(model['cells']['source_slot_reply']['connections']['D'], [5])
        self.assertNotEqual(model['cells']['source_slot_reply']['connections']['Q'],
                            model['cells']['source_slot_reply2']['connections']['Q'])
        self.assertEqual(audit['bindings']['target_req'], 'bus_req')
        self.assertNotIn('bus_req', model['ports'])

    def test_wrong_direction_rejected(self):
        self.slot['ports']['target_req']['direction'] = 'input'
        with self.assertRaisesRegex(ValueError, 'directions'):
            compose(self.usb, self.slot)

    def test_name_collision_rejected(self):
        self.usb['cells']['source_slot_launch'] = flop(3, 10, 2)
        with self.assertRaisesRegex(ValueError, 'collision'):
            compose(self.usb, self.slot)

    def test_conflicting_port_alias_rejected(self):
        self.slot['ports']['target_req']['bits'] = [2]
        with self.assertRaisesRegex(ValueError, 'alias'):
            compose(self.usb, self.slot)

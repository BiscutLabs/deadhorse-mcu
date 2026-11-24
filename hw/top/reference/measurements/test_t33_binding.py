import copy
from pathlib import Path
import tempfile
import unittest

from hw.top.reference.measurements.t33_binding import (ROOT, Nets, account_rows, digest,
    identity_cells, reconcile, require_same_hierarchy, verify_hashes)


class BindingTests(unittest.TestCase):
    def fixture(self):
        child = dict(ports={'out': dict(direction='output', bits=[2, 3])},
            netnames={'state': dict(bits=[2, 3])}, cells={'ff': dict(type='$dff',
                connections=dict(Q=[2, 3], D=[4, 5], CLK=[6]))})
        top = dict(ports={}, netnames={'result': dict(bits=[10, 11])},
                   cells={'sync': dict(type='Child', connections=dict(out=[10, 11]))})
        mapped = dict(ports={'input': dict(direction='input', bits=[30])},
            netnames={'result': dict(bits=[20, 21])}, cells={
                'a': dict(type='flop', connections=dict(Q=[20], D=[30]),
                          port_directions=dict(Q='output', D='input')),
                'b': dict(type='flop', connections=dict(Q=[21], D=[20]),
                          port_directions=dict(Q='output', D='input'))})
        regs = {n: dict(domain='main', reset_events=[]) for n in ('a', 'b')}
        return {'Top': top, 'Child': child}, mapped, regs

    def bind(self, modules, mapped, regs):
        return reconcile(modules, 'Top', mapped, regs, {})

    def test_vector_order_and_exact_instance(self):
        modules, mapped, regs = self.fixture()
        result = self.bind(modules, mapped, regs)
        a = result['bindings']['a']['states'][0]
        self.assertEqual(result['states'][a]['bit'], 0)
        modules['Top']['cells']['sync']['connections']['out'] = [11, 10]
        result = self.bind(modules, mapped, regs)
        a = result['bindings']['a']['states'][0]
        self.assertEqual(result['states'][a]['bit'], 1)
        self.assertEqual(result['instances']['["sync"]']['bindings']['out']['actual'], [11, 10])

    def test_dropped_alias_is_unbound(self):
        modules, mapped, regs = self.fixture()
        mapped['netnames'] = {}
        self.assertEqual(self.bind(modules, mapped, regs)['bindings']['a']['status'], 'unbound')

    def test_merged_owners_are_not_selected(self):
        modules, mapped, regs = self.fixture()
        modules['Top']['cells']['other'] = copy.deepcopy(modules['Top']['cells']['sync'])
        result = self.bind(modules, mapped, regs)
        self.assertEqual(result['bindings']['a']['status'], 'merged_or_ambiguous')
        self.assertEqual(len(result['bindings']['a']['states']), 2)

    def test_inversion_is_not_identity(self):
        def lib(function, direction='output'):
            return ('cell (BUF) { pin (I) { direction : input; } pin (Z) {'
                    f'direction : {direction}; function : "{function}";'+ ' } }')
        self.assertEqual(identity_cells(lib('(I)')), {'BUF': ('I', 'Z')})
        for function in ('!I', 'I ^ 1', 'I | X'):
            self.assertEqual(identity_cells(lib(function)), {})
        self.assertEqual(identity_cells(lib('I', 'input')), {})
        modules, mapped, regs = self.fixture()
        mapped['cells']['a']['connections']['QN'] = mapped['cells']['a']['connections'].pop('Q')
        mapped['cells']['a']['port_directions']['QN'] = mapped['cells']['a']['port_directions'].pop('Q')
        self.assertEqual(self.bind(modules, mapped, regs)['bindings']['a']['status'], 'unsupported_output')

    def test_constants_do_not_merge_unrelated_registers(self):
        nets = Nets()
        nets.connect((), 2, (), '0')
        nets.connect((), 3, (), '0')
        self.assertNotEqual(nets.root(((), 2)), nets.root(((), 3)))
        with self.assertRaisesRegex(ValueError, 'Conflicting constant'):
            nets.connect((), 2, (), '1')

    def test_unconnected_outputs_retained_missing_inputs_rejected(self):
        modules, mapped, regs = self.fixture()
        modules['Child']['ports']['unused'] = dict(direction='output', bits=[9])
        result = self.bind(modules, mapped, regs)
        self.assertEqual(result['instances']['["sync"]']['bindings']['unused']['status'], 'unconnected_output')
        modules['Child']['ports']['unused']['direction'] = 'input'
        with self.assertRaisesRegex(ValueError, 'Incomplete instance port binding'):
            self.bind(modules, mapped, regs)

    def test_hierarchical_buffer_and_constant_are_retained(self):
        modules, mapped, regs = self.fixture()
        modules['Child']['ports']['out']['bits'] = [7, 8]
        modules['Child']['cells']['buf'] = dict(type='$buf', connections=dict(A=[2, 3], Y=[7, 8]))
        result = self.bind(modules, mapped, regs)
        self.assertEqual(result['bindings']['a']['status'], 'unique')
        modules['Top']['cells']['sync']['connections']['out'] = ['0', 11]
        result = self.bind(modules, mapped, regs)
        self.assertEqual(result['states']['["sync","ff","Q",0]']['constant'], '0')

    def test_all_rows_accounted_no_qualification(self):
        modules, mapped, regs = self.fixture()
        binding = self.bind(modules, mapped, regs)['bindings']
        rows = [dict(kind='external', source='input/0', source_domain='external',
                     destination='a/D', destination_bit='0', destination_domain='main'),
                dict(kind='rdc', source='a/Q', source_domain='main',
                     destination='b/D', destination_bit='0', destination_domain='main')]
        result = account_rows(rows, binding, mapped)
        self.assertEqual(result['counts'], {'external': 1, 'rdc': 1})
        self.assertEqual(sum(x['count'] for x in result['statuses']), 2)
        del binding['b']
        with self.assertRaisesRegex(ValueError, 'Uninventoried destination'):
            account_rows(rows, binding, mapped)

    def test_primitive_name_does_not_qualify_bypass(self):
        modules, mapped, regs = self.fixture()
        # Bypass the second state. Alias binding must not imply synchronization.
        modules['Child']['ports']['out']['bits'] = [2, 2]
        result = self.bind(modules, mapped, regs)
        self.assertEqual(result['bindings']['a']['states'], result['bindings']['b']['states'])
        self.assertEqual(len(result['unmapped_source_states']), 1)
        self.assertNotIn('qualified', result)

    def test_non_ff_storage_is_never_silently_lost(self):
        modules, mapped, regs = self.fixture()
        for name, kind in (('latch', '$dlatch'), ('ram', '$mem_v2')):
            modules['Child']['cells'][name] = dict(type=kind, connections=dict(Q=[90], D=[91]),
                                                  parameters={'SIZE': '100'})
        result = self.bind(modules, mapped, regs)
        self.assertEqual({s['kind'] for s in result['other_storage'].values()}, {'$dlatch', '$mem_v2'})
        self.assertEqual(len(result['states']), 2)

    def test_mutated_hierarchy_fails_replay_authentication(self):
        modules, _, _ = self.fixture()
        regenerated = copy.deepcopy(modules)
        require_same_hierarchy(modules, regenerated)
        regenerated['Top']['cells']['sync']['connections']['out'].reverse()
        with self.assertRaisesRegex(ValueError, 'Hierarchy differs'):
            require_same_hierarchy(modules, regenerated)

    def test_changed_proof_artifact_fails_closed(self):
        (ROOT / 'scratch').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / 'scratch') as directory:
            base = Path(directory)
            path = base / 'model.json'
            path.write_text('{"state": 1}')
            hashes = {'model.json': digest(path)}
            verify_hashes(base, hashes)
            path.write_text('{"state": 2}')
            with self.assertRaisesRegex(ValueError, 'Changed authenticated input'):
                verify_hashes(base, hashes)


if __name__ == '__main__':
    unittest.main()

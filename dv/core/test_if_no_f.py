"""Independent encoding-table checks for the IF conditional proof guard."""
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[2]/'hw/ip/perf_core/formal/check_if_no_f.py'
spec = importlib.util.spec_from_file_location('if_no_f', PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class IfNoFTest(unittest.TestCase):
    def test_guard_matches_compressed_encoding_table(self):
        # Four RV32 floating load/store compressed formats, mask e003.
        floating = {0x6000, 0x6002, 0xe000, 0xe002}
        m = {'cells': {'seed': {'connections': {'A': list(range(1,33))}}}}
        result = module.no_float(m, list(range(1,33)))
        cells = [c for n,c in m['cells'].items() if n != 'seed']
        for instruction in range(65536):
            values = {i+1:(instruction >> i)&1 for i in range(32)}
            def number(bits):
                return sum((int(b) if isinstance(b,str) else values[b]) << i for i,b in enumerate(bits))
            for cell in cells:
                c = cell['connections']; a=number(c['A']); b=number(c['B']) if 'B' in c else 0
                value = {'$eq':lambda:a==b, '$and':lambda:a&b, '$or':lambda:a|b, '$not':lambda:not a}[cell['type']]()
                values[c['Y'][0]] = int(value)
            self.assertEqual(values[result[0]], int((instruction & 0xe003) not in floating))

    def test_profile_rejects_unadvertised_input(self):
        full = {'modules': {module.MODULE: {'ports': {'surprise': {'direction': 'input', 'bits': [1]}},
                                             'cells': {}, 'netnames': {}}}}
        baseline = {'modules': {module.MODULE: {'ports': {}}}}
        with self.assertRaises(ValueError): module.profile(full, baseline)

    def test_guard_rejects_wrong_width(self):
        with self.assertRaises(ValueError): module.no_float({}, [1]*16)


if __name__ == '__main__': unittest.main()

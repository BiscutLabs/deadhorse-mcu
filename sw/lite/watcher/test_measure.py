"""Fail-closed measurement inventory, including omitted-positive negative control."""
import unittest
from sw.lite.watcher.measure import parse_results

class ReceiptTests(unittest.TestCase):
    def text(self):
        return '\n'.join('\n'.join([*(f'CASE {k} {d} 2000 200' for k in (0,1,2,2)),f'STACK {d} 8']) for d in (1,2,4))
    def test_complete_inventory(self):
        cases,stack=parse_results(self.text())
        self.assertEqual((len(cases),stack),(12,8))
    def test_no_vacuous_valid_case_success(self):
        for text in ('',self.text().replace('CASE 2','OMITTED 2'), self.text().replace('STACK 4','OMITTED 4'),
                     self.text().replace('2000 200','0 200'),self.text()+'\nCASE 2 4 2000 200'):
            with self.assertRaises(ValueError):parse_results(text)

if __name__=='__main__':unittest.main()

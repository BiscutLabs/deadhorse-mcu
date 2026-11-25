"""Structural fixtures for the reset-inventory counting boundary (no RTL tests)."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]
TOOL=Path(__file__).with_name('reset_inventory.py')


def fixture():
    def ff(q,reset,clk=2):
        pins={'CLK':[clk],'D':['0']*len(q),'Q':q}
        if reset is not None:pins['ARST']=[reset]
        return {'type':'$adff' if reset is not None else '$dff',
                'connections':pins,'port_directions':{p:'output' if p=='Q' else 'input' for p in pins}}
    rr={'ports':{'clk':{'bits':[2],'direction':'input'},'reset_n':{'bits':[3],'direction':'input'},
                 'released':{'bits':[5],'direction':'output'}},
        'cells':{'first':ff([4],3),'second':ff([5],3)},'netnames':{}}
    top={'ports':{},'netnames':{'reset_n':{'bits':[3]},'clock':{'bits':[2]},
                              'alias1':{'bits':[6,7,8,9]},'alias2':{'bits':[6,7,8,9]}},
         'cells':{'r0':{'type':'ResetRelease$fixture','connections':{'clk':[2],'reset_n':[3],'released':[30]}},
                  'r1':{'type':'ResetRelease$fixture','connections':{'clk':[2],'reset_n':[3],'released':[31]}},
                  'wire':{'type':'$buf','connections':{'A':[3],'Y':[13]},'port_directions':{'A':'input','Y':'output'}},
                  'inv':{'type':'$not','connections':{'A':[13],'Y':[14]},'port_directions':{'A':'input','Y':'output'}},
                  'bank':ff([6,7,8,9],14),'unreset':ff(list(range(20,28)),None)}}
    return {'modules':{'DeadhorseSoc':top,'ResetRelease$fixture':rr}}


class ResetInventoryTest(unittest.TestCase):
    def run_model(self,model):
        base=ROOT/'build/t41/inventory-fixtures';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as directory:
            path=Path(directory);source=path/'hier.json';source.write_text(json.dumps(model),encoding='utf-8')
            process=subprocess.run([sys.executable,str(TOOL),'--hier',str(source),'--output',str(path/'out')],
                                   cwd=ROOT,capture_output=True,text=True)
            result=path/'out/reset-inventory.json'
            return process,json.loads(result.read_text(encoding='utf-8')) if result.exists() else None

    def test_shared_aliases_count_once_and_reset_polarities_remain_visible(self):
        process,result=self.run_model(fixture())
        self.assertEqual(process.returncode,0,process.stderr)
        counts=result['summary']
        self.assertEqual(counts['release_instances'],2)
        self.assertEqual(counts['release_flop_bits'],4)
        self.assertEqual(counts['distinct_reset_control_nets_inversion_normalized'],1)
        self.assertEqual(counts['reset_controlled_flop_bits'],8)
        self.assertEqual(counts['all_explicit_flop_bits'],16)
        self.assertEqual(counts['nonreset_flop_bits'],8)
        self.assertEqual({c['inversion'] for c in result['reset_groups'][0]['consumers']},{0,1})

    def test_unknown_sequential_primitive_fails_closed(self):
        model=fixture();model['modules']['DeadhorseSoc']['cells']['unreset']['type']='$_DFF_P_'
        process,result=self.run_model(model)
        self.assertNotEqual(process.returncode,0)
        self.assertIsNone(result)
        self.assertIn('Unclassified sequential cell',process.stderr)


if __name__=='__main__':unittest.main()

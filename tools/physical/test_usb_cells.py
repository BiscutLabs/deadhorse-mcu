"""Independent tiny-library faults for physical cell qualification."""
import copy
from pathlib import Path
import tempfile
import unittest
from usb_cells import qualify
from usb_graph import equivalent
from test_usb_graph import model, SC

FF = '''ff (IQ1, IQN1) { clocked_on : "CLK"; next_state : "D"; clear : "!RN"; }
pin (CLK) { direction : input; clock : true; }
pin (D) { direction : input; } pin (RN) { direction : input; }
pin (Q) { direction : output; function : "IQ1"; }'''


class CellsTests(unittest.TestCase):
    def check(self, body=FF, mutation=None):
        a=model();b=copy.deepcopy(a);b['cells']['f0']['type']=SC+'dffrnq_4'
        manifest={'f0':dict(old=SC+'dffrnq_1',new=SC+'dffrnq_4')}
        if mutation: mutation(a,b,manifest)
        root=Path('build/physical/unit-tests');root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as directory:
            library=Path(directory)/'fixture.lib'
            library.write_text(f'cell ({SC}dffrnq_1) {{ {FF} }}\ncell ({SC}dffrnq_4) {{ {body} }}')
            return equivalent(a,b,manifest,[library])

    def test_same_function_drive_strength(self):
        self.assertEqual(set(self.check()['replacements']),{'f0'})

    def test_sequential_and_pin_faults(self):
        for body in (FF.replace('"!RN"','"RN"'),FF.replace('"CLK"','"!CLK"'),
                     FF.replace('"D"','"!D"'),FF.replace('function : "IQ1"','function : "IQN1"'),
                     FF[FF.index('pin (CLK)'):],FF.replace('pin (D)','pin (D[1:0])'),
                     FF.replace('pin (D) { direction : input','pin (D) { direction : output')):
            with self.subTest(body=body),self.assertRaises(ValueError): self.check(body)

    def test_manifest_and_connectivity_faults(self):
        faults=[lambda a,b,m:m.clear(),
                lambda a,b,m:m.update(extra=m['f0']),
                lambda a,b,m:m['f0'].update(old=SC+'dffrnq_2'),
                lambda a,b,m:b['cells']['f0']['connections'].update(D=['0']),
                lambda a,b,m:b['cells']['f0']['connections'].update(RN=[5]),
                lambda a,b,m:b['cells']['f0']['connections'].update(CLK=[3]),
                lambda a,b,m:b['cells']['f0']['connections'].update(D=['1','1'])]
        for fault in faults:
            with self.subTest(fault=fault),self.assertRaises(ValueError): self.check(mutation=fault)


if __name__=='__main__':unittest.main()

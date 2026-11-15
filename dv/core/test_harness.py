"""Behavioral regression cases for comparison-harness corner cases."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import candidate
from common import CONFIG,output_dir
from div_diagnose import expected
from riscv_formal import require_candidate_coverage
from suites import flight_reentry


class Coverage(unittest.TestCase):
    def test_candidate_cannot_lose_reference_coverage(self):
        require_candidate_coverage('candidate','add','PASS')
        for status in ('FAIL','UNKNOWN','TIMEOUT'):
            with self.subTest(status=status),self.assertRaisesRegex(RuntimeError,'lost reference-supported'):
                require_candidate_coverage('candidate','add',status)


class FixedConfiguration(unittest.TestCase):
    def test_fixed_manifest_is_hash_bound_and_exact(self):
        with tempfile.TemporaryDirectory(dir=output_dir('build/t10/config-tests')) as directory:
            root = Path(directory)
            name = 'rtl/ibex_fixture.sv'
            source = root/name
            source.parent.mkdir()
            source.write_bytes(b'synthetic provenance fixture; not RTL')
            manifest = dict(schema=1,kind='fixed',parameters=copy.deepcopy(CONFIG['parameters']),
                            source_sha256={name:hashlib.sha256(source.read_bytes()).hexdigest()})
            path = root/'candidate.json'
            with patch.object(candidate,'inputs',return_value=dict(sources=[name])):
                self.assertEqual(candidate.parameters(root),CONFIG['parameters'])
                path.write_text(json.dumps(manifest))
                self.assertEqual(candidate.parameters(root),{})
                for fault in ('configuration','missing-hash','wrong-hash','kind'):
                    changed = copy.deepcopy(manifest)
                    if fault=='configuration': changed['parameters']['RV32M']='0'
                    elif fault=='missing-hash': changed['source_sha256']={}
                    elif fault=='wrong-hash': changed['source_sha256'][name]='0'*64
                    else: changed['kind']='ignore-parameters'
                    path.write_text(json.dumps(changed))
                    with self.subTest(fault=fault),self.assertRaises(ValueError):
                        candidate.parameters(root)


class DivisionOracle(unittest.TestCase):
    def test_architectural_corner_cases(self):
        for a,b,want in ((0x80000000,0xffffffff,(0x80000000,0,0,0x80000000)),
                         (0xfffffff9,3,(0xfffffffe,0x55555553,0xffffffff,0)),
                         (7,0xfffffffd,(0xfffffffe,0,1,7)),
                         (0x87654321,0,(0xffffffff,0xffffffff,0x87654321,0x87654321))):
            with self.subTest(a=a,b=b):
                self.assertEqual(tuple(expected(a,b,op) for op in range(4,8)),want)


class FlightReentry(unittest.TestCase):
    def fixture(self):
        base = 0x80000000
        code = (0x0062a023).to_bytes(4,'little')+(0x00012383).to_bytes(4,'little')+bytes(16)
        registers = {n:0 for n in range(32)}
        registers.update({2:base+16,5:0x10000000,6:1})
        rows = [dict(pc=base,regs=dict(registers)),dict(pc=base+4,regs=dict(registers)),
                dict(pc=base+4,regs=dict(registers)),dict(pc=base+8,regs=dict(registers))]
        return base,code,rows

    def test_only_identical_post_marker_load_prestate_is_collapsed(self):
        base,code,rows = self.fixture()
        got,evidence = flight_reentry(rows,code,base)
        self.assertEqual(got,[rows[0],rows[1],rows[3]])
        self.assertEqual(len(evidence),1)
        self.assertEqual(evidence[0]['marker_value'],1)

    def test_changed_state_nonmarker_and_nonload_remain_visible(self):
        for fault in ('state','marker','opcode','store-poststate','ram-address','pc'):
            base,code,rows = self.fixture()
            if fault=='state': rows[2]['regs'][7]=1
            elif fault=='marker':
                for row in rows: row['regs'][5]=base+12
            elif fault=='opcode': code=code[:4]+(0x13).to_bytes(4,'little')+code[8:]
            elif fault=='store-poststate': rows[0]['regs'][6]=2
            elif fault=='ram-address':
                for row in rows: row['regs'][2]=0x10000000
            else: rows[2]['pc']+=4
            with self.subTest(fault=fault):
                got,evidence=flight_reentry(rows,code,base)
                self.assertEqual(got,rows)
                self.assertEqual(evidence,[])


if __name__=='__main__':
    unittest.main()

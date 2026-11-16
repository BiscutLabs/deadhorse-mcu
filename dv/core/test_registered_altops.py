"""Registered adapter contract rejection tests, not RTL behavior tests."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import registered_altops
from common import ROOT


class RegisteredAltopContractTests(unittest.TestCase):
    def test_malformed_contract_never_reaches_adapter_emission(self):
        (ROOT/'build').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as directory:
            path=Path(directory)
            original=path/'IterativeMultiply.sv'
            original.write_bytes(b'provenance fixture; no RTL behavior')
            data=dict(implementation='registered-execution-v1',extra_sources={
                original.name:hashlib.sha256(original.read_bytes()).hexdigest()})
            widths=dict(clk_i=1,rst_ni=1,enable_i=1,ready_i=1,a_i=32,b_i=32,
                        signed_mode_i=2,high_i=1,valid_o=1,result_o=32)
            module=dict(ports={n:dict(direction='output' if n in ('valid_o','result_o') else 'input',
                bits=list(range(w))) for n,w in widths.items()},netnames={'sva_mul_fsm_idle':dict(bits=[1])})
            def exercise(contract, metadata=data, sources=None, parsing=True):
                def parsed_run(command, output, name):
                    self.assertEqual(name,'contract')
                    (output/'contract.json').write_text(json.dumps(dict(modules={'IterativeMultiply':contract})))
                with patch('registered_altops.parameters'), patch('registered_altops.manifest',return_value=metadata), \
                     patch('registered_altops.run',side_effect=parsed_run) as run:
                    with self.assertRaises(ValueError):
                        registered_altops.prepare(path,[str(original)] if sources is None else sources,path,False)
                    self.assertEqual(run.call_count,int(parsing))
            for name in widths:
                for fault in ('missing','width','direction'):
                    with self.subTest(port=name,fault=fault):
                        bad=copy.deepcopy(module)
                        if fault=='missing': bad['ports'].pop(name)
                        elif fault=='width': bad['ports'][name]['bits'].append(99)
                        else: bad['ports'][name]['direction']='input' if name in ('valid_o','result_o') else 'output'
                        exercise(bad)
            for bits in (None,[],[1,2]):
                bad=copy.deepcopy(module)
                if bits is None: bad['netnames'].pop('sva_mul_fsm_idle')
                else: bad['netnames']['sva_mul_fsm_idle']['bits']=bits
                exercise(bad)
            bad=copy.deepcopy(data); bad['extra_sources'][original.name]='0'*64
            exercise(module,bad,parsing=False)
            bad=copy.deepcopy(data); bad['implementation']='unknown'
            exercise(module,bad,parsing=False)
            exercise(module,sources=[],parsing=False)
            exercise(module,sources=[str(original),str(original)],parsing=False)


if __name__=='__main__': unittest.main()

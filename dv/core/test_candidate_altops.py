"""Fail-closed adapter provenance/port contract tests, not RTL behavior tests."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import candidate_altops
from common import ROOT


class CandidateAltopContractTest(unittest.TestCase):
    def test_rejects_bad_hash_and_every_malformed_binding(self):
        (ROOT/'build').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as directory:
            path=Path(directory)
            original=path/'primary.bin'
            original.write_bytes(b'provenance fixture; no RTL behavior')
            metadata=dict(schema=1,multiply_altops=dict(
                source_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
                signals={n:n for n in ('mult_en_internal','sva_mul_fsm_idle','mult_valid')}))
            widths=dict(clk_i=1,rst_ni=1,mult_sel_i=1,multdiv_ready_id_i=1,
                op_a_i=32,op_b_i=32,operator_i=2,signed_mode_i=2,div_sel_i=1,multdiv_result_o=32)
            module=dict(ports={n:dict(direction='output' if n=='multdiv_result_o' else 'input',bits=list(range(w)))
                for n,w in widths.items()},netnames={n:dict(bits=[1]) for n in metadata['multiply_altops']['signals']})
            parsed=path/'parsed.json'
            def exercise(bad, contract=metadata, hash_failure=False):
                (path/'formal_adapter.json').write_text(json.dumps(contract))
                parsed.write_text(json.dumps(dict(modules=dict(ibex_multdiv_fast=bad))))
                with patch('equiv.elaborate',return_value=parsed) as elaborate, patch('candidate_altops.run') as run:
                    with self.assertRaises(ValueError):
                        candidate_altops.prepare(path,[],original,path,False)
                    run.assert_not_called()
                    if hash_failure: elaborate.assert_not_called()
                    else:
                        # A module view cannot substitute for the primary file.
                        self.assertEqual(elaborate.call_args.args[1],original)
            for name in widths:
                for mutation in ('missing','width','direction'):
                    with self.subTest(port=name,mutation=mutation):
                        bad=copy.deepcopy(module)
                        if mutation=='missing': bad['ports'].pop(name)
                        elif mutation=='width': bad['ports'][name]['bits'].append(99)
                        else: bad['ports'][name]['direction']='input' if name=='multdiv_result_o' else 'output'
                        exercise(bad)
            for name in metadata['multiply_altops']['signals']:
                for mutation in ('missing','vector'):
                    with self.subTest(signal=name,mutation=mutation):
                        bad=copy.deepcopy(module)
                        if mutation=='missing': bad['netnames'].pop(name)
                        else: bad['netnames'][name]['bits'].append(99)
                        exercise(bad)
            contract=copy.deepcopy(metadata); contract['multiply_altops']['source_sha256']='0'*64
            exercise(module,contract,hash_failure=True)

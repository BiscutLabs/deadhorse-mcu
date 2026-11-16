import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from formal_triage import configured, ENGINES, last_step
from formal_triage import job
from common import ROOT
from riscv_formal import triage_policy

ORIGINAL='[options]\nmode bmc\ndepth 144\nmulticlock on\ntimeout 120\n[engines]\nbtor btormc\n[script]\nread_verilog -DRISCV_FORMAL_CHECK_CYCLE=64 design.v\nfminit -seq clock '+','.join(str(i%2) for i in range(144))+'\n'


class TriageTest(unittest.TestCase):
    def test_completed_timeout_is_reused_not_retried(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as directory:
            folder=Path(directory);(folder/'work').mkdir()
            (folder/'check.sby').write_text(ORIGINAL)
            (folder/'work/status').write_text('TIMEOUT 8')
            (folder/'work/logfile.txt').write_text('bad state property 0 at bound k = 127')
            command=['sby','-f','-d',str(folder/'work'),str(folder/'check.sby')]
            (folder/'commands.jsonl').write_text(json.dumps(dict(command=command,returncode=8,elapsed_seconds=600))+'\n')
            with patch('formal_triage.run',side_effect=AssertionError('solver retried')):
                self.assertEqual(job(folder,ORIGINAL,600,{})['status'],'TIMEOUT')
                with self.assertRaises(ValueError):job(folder,ORIGINAL+'\n',600,{})

    def test_only_complete_accepted_policy_can_feed_full_isa(self):
        valid=dict(status='pass',checks={name:dict(status='accepted',check_cycle=64,depth=144,cutpoints=[]) for name in ('lw','c_add')})
        self.assertEqual(set(triage_policy(valid)),{'lw','c_add'})
        for bad in (dict(status='unresolved',checks=valid['checks']),dict(status='pass',checks={'lw':valid['checks']['lw']})):
            with self.assertRaises(ValueError):triage_policy(bad)

    def test_progress_excludes_configured_maximum(self):
        self.assertEqual(last_step('maximum bound k = 143\nbad state property 0 at bound k = 127 UNSATISFIABLE'),127)

    def test_portfolio_keeps_exact_script(self):
        result=configured(ORIGINAL)
        self.assertEqual(result.split('[script]\n')[1],ORIGINAL.split('[script]\n')[1])
        for engine in ENGINES:self.assertIn(engine+'\n',result)
        self.assertIn('timeout 600\n',result)

    def test_growth_preserves_model(self):
        for depth in (36,72):
            result=configured(ORIGINAL,depth=depth,clock_depth=144)
            self.assertEqual(result.split('[script]\n')[1],ORIGINAL.split('[script]\n')[1])
            self.assertIn(f'depth {depth}\n',result)

    def test_window_margin_and_cover_engines(self):
        result=configured(ORIGINAL,mode='cover',cycle=15,depth=46)
        self.assertIn('CHECK_CYCLE=15',result)
        self.assertEqual(len(result.split('fminit -seq clock ')[1].strip().split(',')),46)
        self.assertNotIn('abc bmc3',result)

    def test_cutpoint_is_symbolic_not_assumption(self):
        result=configured(ORIGINAL,cutpoints=['wrapper.core.result_data'])
        self.assertIn('cutpoint rvfi_testbench/w:wrapper.core.result_data',result)
        self.assertNotIn('assume',result)
        with self.assertRaises(ValueError):configured(ORIGINAL,cutpoints=['data;delete t:$assert'])


if __name__=='__main__':unittest.main()

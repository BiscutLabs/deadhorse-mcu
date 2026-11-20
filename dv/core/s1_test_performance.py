"""S1 throughput denominator regression tests, independent synthetic stream."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("s1_performance",Path(__file__).resolve().parents[2]/"tools/spikes/s1_core/performance.py")
performance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(performance)


class PerformanceTests(unittest.TestCase):
    def stream(self):
        rows=[]
        for mode in range(3):
            for _ in range(40):
                rows.append(dict(pc_rdata=0,mem_wmask=15,mem_addr=0x10000000,mem_wdata=mode))
                rows.extend(dict(pc_rdata=pc,mem_wmask=0) for pc in (10,12,15,20))
        return rows,list(range(0,5*len(rows),5)),dict(start=10,call=12,end=20)

    def test_same_instruction_and_cycle_windows(self):
        result=performance.iteration_metrics(*self.stream(),9)
        self.assertEqual(result['iterations'],120)
        self.assertEqual(result['total_loop_cycles'],2400)
        self.assertEqual(result['total_loop_retired_instructions'],480)
        self.assertEqual(result['aggregate_cpi'],5)
        self.assertEqual(result['aggregate_mips'],1.8)
        self.assertEqual(result['minimum_iteration_mips'],1.8)
        self.assertEqual(result['margin_1khz_cycles'],8980)
        self.assertEqual(result['margin_500hz_cycles'],17980)

    def test_missing_backedge_is_rejected(self):
        rows,cycles,bounds=self.stream()
        rows[-1]['pc_rdata']=22
        with self.assertRaisesRegex(ValueError,'Incomplete'):
            performance.iteration_metrics(rows,cycles,bounds,9)


if __name__=='__main__':
    unittest.main()

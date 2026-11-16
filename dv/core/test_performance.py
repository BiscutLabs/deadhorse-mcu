import unittest
from performance import arithmetic, loop_boundaries, loop_samples, timed_rows


class PerformanceTest(unittest.TestCase):
    def test_timestamp_faults(self):
        rows=[dict(order=1),dict(order=2)]
        self.assertEqual(timed_rows(rows,'1 8\n2 13\n'),[8,13])
        for bad in ('1 8\n','1 8\n3 13\n','1 8\n2 8\n'):
            with self.assertRaises(ValueError):timed_rows(rows,bad)

    def test_iteration_includes_surrounding_work(self):
        rows=[]
        for mode in range(3):
            rows.extend([dict(pc_rdata=0,mem_wmask=15,mem_addr=0x10000000,mem_wdata=mode),
                         *[dict(pc_rdata=pc,mem_wmask=0) for pc in (10,12,15,20)]])
        bounds=dict(start=10,call=12,end=20)
        samples=loop_samples(rows,list(range(0,75,5)),bounds,expected=3)
        self.assertEqual([s['cycles'] for s in samples],[20,20,20])
        broken=[dict(row) for row in rows];broken[2]['pc_rdata']=14
        with self.assertRaises(ValueError):loop_samples(broken,list(range(15)),bounds,3)

    def test_smallest_enclosing_backedge(self):
        listing='80000010: 00000013 addi x0,x0,0\n80000020: 040000ef jal 80000060 <control_step>\n80000030: fe0090e3 bnez a0,80000010 <main+0x10>\n80000040: fc0090e3 bnez a0,80000000 <main>\n'
        self.assertEqual(loop_boundaries(listing),dict(start=0x80000010,end=0x80000030,call=0x80000020))

    def test_arithmetic_is_retirement_spacing(self):
        result=arithmetic([dict(insn=0x13),dict(insn=0x02000033),dict(insn=0x02004033)],[10,14,51])
        self.assertEqual(result['mul']['values'],[4])
        self.assertEqual(result['div']['values'],[37])
        self.assertEqual(result['divu']['status'],'not observed')

    def test_float_arithmetic_decoding(self):
        result=arithmetic([dict(insn=x) for x in (0x13,0x10000053,0x18000053)],[1,44,107])
        self.assertEqual(result['fmul.s']['values'],[43])
        self.assertEqual(result['fdiv.s']['values'],[63])


if __name__=='__main__':unittest.main()

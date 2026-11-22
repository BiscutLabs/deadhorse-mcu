import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import fixture

spec=importlib.util.spec_from_file_location('soc_performance',Path(__file__).with_name('performance.py'))
performance=importlib.util.module_from_spec(spec); spec.loader.exec_module(performance)


class FixtureTests(unittest.TestCase):
    def test_image_capacity_and_bank_contents(self):
        with tempfile.TemporaryDirectory(dir=fixture.ROOT/'build',prefix='soc-image-test-') as name:
            directory=Path(name)
            payload=bytes((i*37+11)%256 for i in range(fixture.CAPACITY))
            image=fixture.write_images(directory,payload,fixture.RAM)
            words=[[int(word,16) for word in (directory/f'ram{bank}.hex').read_text().splitlines()] for bank in range(4)]
            reconstructed=b''.join(words[word%4][word//4].to_bytes(4,'little') for word in range(fixture.CAPACITY//4))
            self.assertEqual(reconstructed,payload)
            self.assertEqual(image.read_bytes()[:fixture.CAPACITY],payload)
            self.assertEqual(image.read_bytes()[fixture.ENTRY-fixture.RAM:],fixture.bootstrap(fixture.RAM))
            with self.assertRaisesRegex(ValueError,'exceeds'):
                fixture.write_images(directory,payload+b'\0',fixture.RAM)

    def test_bootstrap_target(self):
        for destination in (fixture.RAM,fixture.RAM+0x80):
            word=int.from_bytes(fixture.bootstrap(destination),'little')
            immediate=((word>>31)<<20)|((word>>12&255)<<12)|((word>>20&1)<<11)|((word>>21&1023)<<1)
            if immediate&(1<<20): immediate-=1<<21
            self.assertEqual(word&0xfff,0x6f) # JAL x0, no architectural destination.
            self.assertEqual(fixture.ENTRY+immediate,destination)
        for bad in (fixture.ENTRY+1,fixture.ENTRY+(1<<20)):
            with self.assertRaises(ValueError): fixture.bootstrap(bad)

    def test_allocated_sections_and_stack_fit(self):
        def listing(address,size,lma=None):
            return f'  0 .bss {size:08x} {address:08x} {address if lma is None else lma:08x}\n ALLOC\n'
        for address,size,lma in ((fixture.RAM,fixture.CAPACITY-2048,None),
                                 (fixture.RAM,fixture.CAPACITY-2047,None),
                                 (fixture.RAM-4,4,None),(fixture.RAM,4,fixture.RAM+4)):
            with patch.object(fixture,'run',return_value=SimpleNamespace(stdout=listing(address,size,lma))):
                if size==fixture.CAPACITY-2048:
                    self.assertEqual(len(fixture.allocated_sections(Path('unused'),Path('unused'),2048)),1)
                else:
                    with self.assertRaisesRegex(ValueError,'does not fit'):
                        fixture.allocated_sections(Path('unused'),Path('unused'),2048)

    def test_unchanged_overhead_boundary(self):
        for name,baseline in performance.BASELINES.items():
            ceiling=baseline*11//10
            performance.check_overhead(name,ceiling)
            with self.assertRaisesRegex(ValueError,'exceeds'):
                performance.check_overhead(name,ceiling+1)

    def test_stack_bootstrap_pair_and_unchanged_bounds(self):
        top=fixture.RAM+fixture.CAPACITY
        first=dict(insn=0x4117,pc_rdata=fixture.RAM+0x86,rd_addr=2,
                   rd_wdata=top+0x86,rs1_addr=0,rs1_rdata=0,order=36,trap=0,intr=0)
        second=dict(insn=0xf7a10113,pc_rdata=fixture.RAM+0x8a,rd_addr=2,
                    rd_wdata=top,rs1_addr=2,rs1_rdata=top+0x86,order=37,trap=0,intr=0)
        low=dict(second,insn=0x80010113,rd_wdata=top-2048)
        self.assertEqual(performance.stack_range([first,second,low])[:2],(top-2048,top))
        self.assertEqual(performance.stack_range([dict(second,insn=0x80004137),low]),(top-2048,top,None))
        faults=([first], [first,dict(second,insn=0x13)],
                [first,dict(second,rd_addr=0),second],
                [first,dict(second,rs1_rdata=top)],
                [first,dict(second,pc_rdata=second['pc_rdata']+4)],
                [first,dict(second,rd_wdata=top+1)],
                [first,dict(second,order=39)], [dict(first,trap=1),second],
                [first,dict(second,intr=1)], [dict(first,rd_wdata=top+1),second],
                [first,second,first,second],
                [first,second,dict(low,rd_wdata=top-2049)],
                [first,second,dict(low,rd_wdata=top+1)])
        for rows in faults:
            with self.subTest(rows=rows),self.assertRaises(ValueError):
                performance.stack_range(rows)


if __name__=='__main__': unittest.main()

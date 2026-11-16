"""Transformation provenance tests on synthetic bytes, never RTL behavior."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import csr_priority
from common import output_dir


class PriorityNormalization(unittest.TestCase):
    def fixture(self):
        data=b"start\n unique selector one\n middle\n  unique selector two\nend\n"
        normalized=data.replace(b' unique ',b' ')
        entry=dict(source='rtl/ibex_cs_registers.sv',source_sha256=hashlib.sha256(data).hexdigest(),
                   normalized_sha256=hashlib.sha256(normalized).hexdigest(),edits=[
                       dict(line=2,before=' unique selector one\n',after=' selector one\n'),
                       dict(line=4,before='  unique selector two\n',after='  selector two\n')])
        return data,normalized,entry

    def test_exact_reversible_transformation(self):
        data,normalized,entry=self.fixture()
        self.assertEqual(csr_priority.normalize_bytes(data,entry),normalized)
        for fault in ('source','result','location','count','duplicate','content','extra'):
            changed=copy.deepcopy(entry)
            if fault=='source': changed['source_sha256']='0'*64
            elif fault=='result': changed['normalized_sha256']='0'*64
            elif fault=='location': changed['edits'][0]['line']=3
            elif fault=='count': changed['edits'].pop()
            elif fault=='duplicate': changed['edits'][1]['line']=2
            elif fault=='content': changed['edits'][0]['before']='not the input\n'
            else: changed['edits'][0]['after']='a different operation\n'
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                csr_priority.normalize_bytes(data,changed)

    def test_scope_and_unchanged_inputs(self):
        data,normalized,entry=self.fixture()
        with tempfile.TemporaryDirectory(dir=output_dir('build/t11/priority-input-tests')) as directory:
            root=Path(directory); vendor=root/'vendor'; source=vendor/entry['source']
            source.parent.mkdir(parents=True); source.write_bytes(data)
            copied=root/'copy'/'ibex_cs_registers.sv'; copied.parent.mkdir(); copied.write_bytes(data)
            candidate=root/'chisel'/'ibex_cs_registers.sv'; candidate.parent.mkdir(); candidate.write_bytes(b'new emitted implementation')
            def manifest(key):
                if key=='csr_priority': return entry
                return dict(entry,source='rtl/ibex_id_stage.sv')
            with patch.object(csr_priority,'VENDOR',vendor),patch.object(csr_priority,'adaptation_entry',side_effect=manifest):
                for module in ('ibex_cs_registers','ibex_core','ibex_top'):
                    sources,receipts=csr_priority.analysis_sources([str(source),str(copied),str(candidate)],root/module,'gold',module)
                    self.assertEqual(len(receipts),2)
                    self.assertEqual(Path(sources[0]).read_bytes(),normalized)
                    self.assertEqual(sources[2],str(candidate))
                    self.assertEqual(source.read_bytes(),data); self.assertEqual(copied.read_bytes(),data)
                sources,receipts=csr_priority.analysis_sources([str(source)],root/'unused','gold','ibex_alu')
                self.assertEqual(sources,[str(source)]); self.assertEqual(receipts,[])
                source.write_bytes(data+b'changed')
                with self.assertRaisesRegex(ValueError,'input hash mismatch'):
                    csr_priority.analysis_sources([str(source)],root/'bad','gold','ibex_top')

    def test_single_id_edit_and_parent_routing(self):
        data=b'prefix\n unique selector\nsuffix\n'
        normalized=data.replace(b'unique ',b'')
        entry=dict(source='rtl/ibex_id_stage.sv',source_sha256=hashlib.sha256(data).hexdigest(),
            normalized_sha256=hashlib.sha256(normalized).hexdigest(),
            edits=[dict(line=2,before=' unique selector\n',after=' selector\n')])
        self.assertEqual(csr_priority.normalize_bytes(data,entry,1),normalized)
        for count in (0,2,3):
            with self.assertRaisesRegex(ValueError,'count'):
                csr_priority.normalize_bytes(data,entry,count)
        with tempfile.TemporaryDirectory(dir=output_dir('build/t11/priority-input-tests')) as directory:
            root=Path(directory); vendor=root/'vendor'; source=vendor/entry['source']
            source.parent.mkdir(parents=True); source.write_bytes(data)
            def manifest(key):
                return entry if key=='id_priority' else dict(entry,source='rtl/ibex_cs_registers.sv')
            with patch.object(csr_priority,'VENDOR',vendor),patch.object(csr_priority,'adaptation_entry',side_effect=manifest):
                for module in ('ibex_id_stage','ibex_core','ibex_top'):
                    sources,receipts=csr_priority.analysis_sources([str(source)],root/module,'gold',module)
                    self.assertEqual(Path(sources[0]).read_bytes(),normalized)
                    self.assertEqual(len(receipts),1)
                sources,receipts=csr_priority.analysis_sources([str(source)],root/'csr','gold','ibex_cs_registers')
                self.assertEqual(sources,[str(source)]); self.assertEqual(receipts,[])


if __name__=='__main__': unittest.main()

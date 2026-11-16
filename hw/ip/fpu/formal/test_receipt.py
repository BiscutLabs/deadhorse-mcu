"""Proof receipt freshness/inventory regressions; synthetic artifacts only."""
import json
from pathlib import Path
import tempfile
import unittest
from receipt import ROLES, snapshot, authenticate, fingerprints

class ReceiptTest(unittest.TestCase):
    def setUp(self):
        scratch=Path('build/t13/receipt-tests');scratch.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=scratch)
        self.root=Path(self.temp.name).resolve();self.out=self.root/'build/t12/formal'
        self.write('build/t12/emit/Fpu.sv','production')
        for role in ROLES:
            for name in ('prepared.json','abstraction.json','check.sby','proof/engine_0/logfile.txt'):
                self.write(f'build/t12/formal/{role}/{name}','artifact')
            self.write(f'build/t12/formal/{role}/proof/status','FAIL' if role.endswith('fault') else 'PASS')
            self.write(f'build/t12/formal/emit/{role}/FpuFormal.sv','monitor')
        for name in ('projected-canonical.json','production-canonical.json','binding/negative-controls.json'):
            self.write('build/t12/formal/normal/'+name,'binding')
        self.write('build/t12/formal/normal/binding/result.json','{"status":"proved"}')
        for name in ('check.py','FpuFormal.scala','receipt.py'):
            self.write('hw/ip/fpu/formal/'+name,'source')
        for role in ROLES:
            self.write(f'build/t12/formal/{role}/abstraction.json',json.dumps(dict(sources=fingerprints(
                self.root,list((self.out/'emit'/role).glob('*.sv'))))))
        self.protected=fingerprints(self.root,list((self.root/'build/t12/emit').glob('*.sv'))+
            [self.root/'hw/ip/fpu/formal'/name for name in ('check.py','FpuFormal.scala','receipt.py')])
        for role in ROLES:
            paths=[self.out/role/name for name in ('prepared.json','abstraction.json','check.sby')]
            paths+=list((self.out/'emit'/role).glob('*.sv'))
            self.protected.update(fingerprints(self.root,paths))
        self.record=dict(status='pass',authentication=snapshot(self.root,self.out,self.protected))
        self.save()
    def tearDown(self): self.temp.cleanup()
    def write(self,path,text):
        p=self.root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
    def save(self): self.write('build/t12/formal/result.json',json.dumps(self.record))
    def test_exact_snapshot(self): authenticate(self.root,self.out)
    def test_changed_artifacts(self):
        for path in self.record['authentication']['artifacts']:
            with self.subTest(path=path):
                p=self.root/path;old=p.read_text();p.write_text(old+'corrupt')
                with self.assertRaises((ValueError,IndexError)): authenticate(self.root,self.out)
                p.write_text(old)
    def test_missing_or_extra_production(self):
        p=self.root/'build/t12/emit/Fpu.sv';old=p.read_text();p.unlink()
        with self.assertRaises(ValueError): authenticate(self.root,self.out)
        p.write_text(old);self.write('build/t12/emit/Extra.sv','extra')
        with self.assertRaises(ValueError): authenticate(self.root,self.out)
    def test_mutation_between_binding_and_finalization(self):
        self.write('build/t12/emit/Fpu.sv','regenerated after binding')
        with self.assertRaises(ValueError): snapshot(self.root,self.out,self.protected)
    def test_prepared_mutation_after_binding(self):
        self.write('build/t12/formal/normal/prepared.json','replacement model')
        with self.assertRaises(ValueError): snapshot(self.root,self.out,self.protected)
    def test_incomplete_capture(self):
        incomplete=dict(self.protected);incomplete.pop('build/t12/formal/normal/prepared.json')
        with self.assertRaises(ValueError): snapshot(self.root,self.out,incomplete)
    def test_stale_or_legacy_pass(self):
        for status in ('running','failed'):
            self.record['status']=status;self.save()
            with self.assertRaises(ValueError): authenticate(self.root,self.out)
        self.record=dict(status='pass');self.save()
        with self.assertRaises(ValueError): authenticate(self.root,self.out)

if __name__=='__main__': unittest.main()

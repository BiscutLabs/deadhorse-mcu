"""Acceptance bookkeeping faults; no hardware job or CI invocation."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import evidence
spec=importlib.util.spec_from_file_location('usb_acceptance',Path(__file__).with_name('check.py'))
acceptance=importlib.util.module_from_spec(spec);spec.loader.exec_module(acceptance)
packet_obligations=acceptance.packet_obligations


def claims():
    return [dict(role=r,property=p,kind='proved',packet_bytes=16)
            for r in ('in','out') for p in ('capacity','read_nonempty','integrity','held_valid','held_data','progress')]


class EvidenceTests(unittest.TestCase):
    def test_partial_inventory_retains_exact_blocker(self):
        rows=claims();rows[2].update(kind='proved at small model',packet_bytes=8)
        rows[8]=dict(role='out',property='integrity',kind='unresolved')
        result=evidence.inventory(rows)
        self.assertEqual(len(result['closed']),11)
        self.assertEqual(result['unresolved'],['out.integrity'])
        self.assertEqual(result['closed'][2]['qualification'],'proved at small model, simulated at full size')
        self.assertIn('out.integrity',packet_obligations(result)[0])

    def test_complete_inventory(self):
        self.assertEqual(packet_obligations(evidence.inventory(claims())),[])

    def test_missing_duplicate_and_unknown_assertions_rejected(self):
        rows=claims()
        for bad in (rows[:-1],rows+[rows[0]],rows[:-1]+[rows[0]],rows[:-1]+[dict(role='out',property='unknown',kind='proved')]):
            with self.subTest(bad=bad[-1]),self.assertRaises(ValueError):evidence.inventory(bad)

    def test_bounded_or_wrong_geometry_never_closes(self):
        for kind,size in [('bounded',16),('pass',16),('proved',8),('proved at small model',16)]:
            rows=claims();rows[0].update(kind=kind,packet_bytes=size)
            with self.subTest(kind=kind,size=size),self.assertRaises(ValueError):evidence.inventory(rows)

    def test_contradictory_summary_rejected(self):
        result=evidence.inventory(claims());result['status']='unresolved'
        with self.assertRaises(ValueError):packet_obligations(result)
        self.assertTrue(packet_obligations(dict(status='failed')))
        self.assertTrue(packet_obligations({}))

    def test_stale_source_and_windows_receipt_paths(self):
        with tempfile.TemporaryDirectory(dir=evidence.ROOT/'build',prefix='usb-evidence-test-') as name:
            p=Path(name)/'source';p.write_bytes(b'original')
            hashes={str(p.relative_to(evidence.ROOT)).replace('/','\\'):evidence.digest(p)}
            evidence.check_hashes(hashes)
            p.write_bytes(b'changed')
            with self.assertRaises(ValueError):evidence.check_hashes(hashes)
        with self.assertRaises(ValueError):evidence.check_hashes({})

    def test_repository_and_build_boundaries(self):
        for name,build in [('../outside',False),('hw/ip/usb/check.py',True)]:
            with self.subTest(name=name),self.assertRaises(ValueError):evidence.local(name,build)

    def test_wrapper_and_archived_source_faults(self):
        with tempfile.TemporaryDirectory(dir=evidence.ROOT/'build',prefix='usb-evidence-test-') as name:
            base=Path(name);source=base/'rtl';source.write_bytes(b'rtl')
            relative=source.relative_to(evidence.ROOT).as_posix()
            wrapper=base/'wrapper.json';wrapper.write_bytes(b'model')
            archived=base/'simulation-archive/source'/relative;archived.parent.mkdir(parents=True);archived.write_bytes(b'rtl')
            binding=dict(current_source_sha256={relative:evidence.digest(source)},emitted_sha256={relative:evidence.digest(source)},
                         wrapper_sha256=evidence.digest(wrapper),simulation=dict(artifact_sha256={relative:evidence.digest(source)}))
            archive=dict(source_sha256={str(archived):evidence.digest(archived)},files={str(source):dict(origin=relative,sha256=evidence.digest(source))})
            evidence.wrapper_archive(base/'result.json',binding,archive)
            wrapper.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'wrapper model'):evidence.wrapper_archive(base/'result.json',binding,archive)
            wrapper.unlink()
            with self.assertRaises(FileNotFoundError):evidence.wrapper_archive(base/'result.json',binding,archive)
            wrapper.write_bytes(b'model');archived.write_bytes(b'different')
            archive['source_sha256'][str(archived)]=evidence.digest(archived)
            with self.assertRaisesRegex(ValueError,'Archived SIE source'):evidence.wrapper_archive(base/'result.json',binding,archive)

    def test_simulation_requires_exact_command_and_full_inventory(self):
        with tempfile.TemporaryDirectory(dir=evidence.ROOT/'build',prefix='usb-evidence-test-') as name:
            base=Path(name);path=base/'result.json';log=base/'simulation.log'
            log.write_text('Tests: succeeded 2, failed 0\nAll tests passed.\n')
            row=dict(status='pass',returncode=0,command=['python3','tools/sbt.py','testOnly deadhorse.usb.UsbThroughputSpec'],
                     source_sha256={},log_sha256=evidence.digest(log),qualification='fixture')
            source=base/'rtl';source.write_bytes(b'rtl')
            expected={source.relative_to(evidence.ROOT).as_posix():evidence.digest(source)}
            # Unit fixtures must not depend on a previously generated regmap/vendor tree.
            with patch.object(evidence,'simulation_sources',return_value=expected):
                path.write_text(json.dumps(row))
                with self.assertRaisesRegex(ValueError,'source binding'):evidence.full_size_evidence(path)
                row['source_sha256']=expected;path.write_text(json.dumps(row))
                self.assertEqual(evidence.full_size_evidence(path)['status'],'pass')
                row['command']=['true'];path.write_text(json.dumps(row))
                with self.assertRaisesRegex(ValueError,'command'):evidence.full_size_evidence(path)

    def test_sie_inventory_cannot_be_truncated_consistently(self):
        with tempfile.TemporaryDirectory(dir=evidence.ROOT/'build',prefix='usb-evidence-test-') as name:
            base=Path(name);proof=base/'proof.json';binding=base/'binding.json';archive=base/'archive.json'
            # Empty inventories agree with one another but omit real production inputs.
            proof.write_text(json.dumps(dict(status='safety-proved',source_sha256={})))
            binding.write_text(json.dumps(dict(status='pass',proof_sha256=evidence.digest(proof),
                binder_sha256=evidence.digest(evidence.ROOT/'hw/ip/usb/formal/sie_packet_contract.py'),current_source_sha256={})))
            archive.write_text(json.dumps(dict(status='pass',origin_receipt_sha256=evidence.digest(binding),source_sha256={})))
            with self.assertRaisesRegex(ValueError,'Incomplete SIE proof source inventory'):
                evidence.sie_evidence(proof,binding,archive)

    def test_vendor_export_allows_only_terminal_lf_count(self):
        with tempfile.TemporaryDirectory(dir=evidence.ROOT/'build',prefix='usb-evidence-test-') as name:
            a=Path(name)/'source';b=Path(name)/'emitted'
            a.write_bytes(b'line1\nline2\n');b.write_bytes(b'line1\nline2\n\n')
            self.assertNotEqual(evidence.same_vendor(a,b)['source_sha256'],evidence.digest(b))
            for bad in (b'line1\nchanged\n',b'line1\n\nline2\n',b'line1\nline2 \n',b'line1\nline2\r\n'):
                b.write_bytes(bad)
                with self.subTest(bad=bad),self.assertRaises(ValueError):evidence.same_vendor(a,b)

    def test_failed_audit_cannot_be_replaced_by_pass_summary(self):
        with tempfile.TemporaryDirectory(dir=evidence.ROOT/'build',prefix='usb-evidence-test-') as name:
            base=Path(name);manifest=base/'manifest.json'
            manifest.write_text(json.dumps(dict(schema=1,receipts=[str(manifest)],anchors=[str(manifest)],
                sie_proof=str(manifest),sie_binding=str(manifest),sie_archive=str(manifest),full_size_simulation=str(manifest))))
            with patch.object(evidence,'audit_epoch',return_value=dict(status='pass',audit=dict(status='failed'))), \
                 patch.object(evidence,'sie_evidence') as sie,patch('subprocess.run',side_effect=AssertionError('Must not launch commands')):
                result=evidence.collect(manifest,base/'audit')
            self.assertEqual(result['status'],'failed');sie.assert_not_called()
            self.assertIn('Packet artifact audit failed',result['error'])


if __name__=='__main__':unittest.main()

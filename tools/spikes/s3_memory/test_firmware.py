"""Accounting/oracle regressions; executable negative controls live in firmware.py."""
import importlib.util
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("s3_firmware", Path(__file__).with_name("firmware.py"))
firmware = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(firmware)


class FirmwareTests(unittest.TestCase):
    def test_local_labels_do_not_hide_reachable_calls(self):
        dump = """Disassembly of section .text.flight:
00000000 <flight>:
  0: R_RISCV_CALL_PLT sample
00000004 <.L2>:
  4: R_RISCV_CALL_PLT control
  8: R_RISCV_CALL_PLT publish
Disassembly of section .text.cold:
00000000 <cold>:
  0: R_RISCV_CALL_PLT init
"""
        edges = firmware.relocation_edges(dump,{"flight","sample","control","publish","cold","init"})
        self.assertEqual(edges["flight"],{"sample","control","publish"})
        self.assertEqual(edges["cold"],{"init"})
        # Actual removed-call text is a negative control of this parser fixture.
        bad = firmware.relocation_edges(dump.replace("R_RISCV_CALL_PLT control","R_RISCV_CALL_PLT absent"),set(edges))
        self.assertNotEqual(bad["flight"],edges["flight"])

    def test_linked_library_tail_calls_are_counted(self):
        dump = """80000100 <root>:
80000104: 1234 jal 80000200 <__helper>
80000200 <__helper>:
80000204: 1234 j 80000300 <leaf>
80000300 <leaf>:
80000304: 1234 bnez a0,80000300 <leaf>
"""
        symbols = [{"name":name,"kind":"T"} for name in ("root","__helper","leaf")]
        self.assertEqual(firmware.linked_edges(dump,symbols),{"root":{"__helper"},"__helper":{"leaf"},"leaf":set()})

    def test_known_hash_and_rejected_configuration(self):
        self.assertEqual(firmware.fnv(b"hello"),0x4f9f2cab)
        with self.assertRaisesRegex(ValueError,"configuration"):
            firmware.check_records("10 0 1fff 80 1234 0 1\n",0x1234)

    def test_gcc_ipa_clone_stack_records(self):
        self.assertEqual(firmware.stack_frame("remap.isra.0",{"remap.isra":16}),16)
        self.assertEqual(firmware.stack_frame("remap.isra.0",{"remap.isra.1":16,"remap.isra.2":32}),32)
        with self.assertRaisesRegex(ValueError,"missing stack"):
            firmware.stack_frame("remap.constprop.0",{"unrelated":32})

    def test_stack_escaping_allocated_fixture_is_rejected(self):
        self.assertFalse(firmware.checked_stack_pointer(0,False))
        self.assertTrue(firmware.checked_stack_pointer(0x8007ff00,True))
        for pointer in (0,0x8006fffc,0x80080004):
            with self.assertRaisesRegex(ValueError,"outside"):
                firmware.checked_stack_pointer(pointer,True)

    def test_timeout_preserves_partial_output_and_command(self):
        with tempfile.TemporaryDirectory(dir=firmware.ROOT / "build") as temporary:
            directory = Path(temporary)
            runner = firmware.Runner(directory)
            with patch.object(firmware.subprocess,"run",side_effect=subprocess.TimeoutExpired(["tool"],1,output=b"partial",stderr=b"error")):
                with self.assertRaises(subprocess.TimeoutExpired):
                    runner.command(["tool"],directory,"attempt",timeout=1)
            self.assertEqual((directory / "attempt.stdout").read_bytes(),b"partial")
            self.assertEqual((directory / "attempt.stderr").read_bytes(),b"error")
            self.assertEqual(runner.commands[0]["status"],"timeout")
            self.assertEqual(runner.commands[0]["command"],["tool"])


if __name__ == "__main__":
    unittest.main()

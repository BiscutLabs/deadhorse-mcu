import unittest
from check_jalr_metadata import witness


class MetadataWitnessTests(unittest.TestCase):
    def trace(self,rd,trap,insn=0xe7,reset=0):
        return '\n'.join(['$scope module rvfi_testbench $end',
            '$var wire 1 v rvfi_valid $end','$var wire 32 i rvfi_insn $end',
            '$var wire 5 a rvfi_rd_addr $end','$var wire 1 t rvfi_trap $end',
            '$scope module checker_inst $end','$var wire 1 r reset $end',
            '$upscope $end','$upscope $end','$enddefinitions $end','#5',
            '1v',f'b{insn:032b} i',f'b{rd:05b} a',f'{trap}t',f'{reset}r','#10'])

    def test_independent_destination_and_trap_faults(self):
        for role,rd,trap in [('address-cover',1,0),('address-fault',0,0),('trap-cover',1,0),('trap-fault',1,1)]:
            self.assertEqual(witness(self.trace(rd,trap),role)['values']['instruction'],0xe7)
            with self.assertRaises(ValueError):witness(self.trace(rd,trap,reset=1),role)
            with self.assertRaises(ValueError):witness(self.trace(rd,trap,insn=0x13),role)


if __name__=='__main__':unittest.main()

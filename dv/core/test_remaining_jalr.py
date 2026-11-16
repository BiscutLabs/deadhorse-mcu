import unittest
from split_remaining_jalr import memory_fault_witness
from complete_jalr_inventory import normalize_wrapper_metadata


class RemainingJalrTests(unittest.TestCase):
    def trace(self,read,rd,wd,check=1):
        return '\n'.join(['$scope module rvfi_testbench $end',
            '$var wire 1 v rvfi_valid $end','$var wire 32 i rvfi_insn $end',
            '$var wire 4 w rvfi_mem_wmask $end','$var wire 4 r rvfi_mem_rmask $end',
            '$var wire 32 d rvfi_mem_rdata $end','$var wire 32 e rvfi_mem_wdata $end',
            '$var wire 1 t rvfi_trap $end','$scope module checker_inst $end',
            '$var wire 1 c check $end','$var wire 1 z reset $end',
            '$upscope $end','$upscope $end','$enddefinitions $end','#5',
            '1v','b00000000000000000000000001100111 i','b0001 w',f'b{read:04b} r',
            f'b{rd:032b} d',f'b{wd:032b} e','0t',f'{check}c','0z','#10'])

    def test_scalar_vcd_and_original_extra_write_rules(self):
        for read,rd,wd in [(0,0,0),(15,0xaa,0xbb)]:
            self.assertEqual(memory_fault_witness(self.trace(read,rd,wd))['values']['write'],1)
        for args in [(15,0xaa,0xaa),(1,0x1aa,0xaa)]:
            with self.assertRaises(ValueError):memory_fault_witness(self.trace(*args))
        with self.assertRaises(ValueError):memory_fault_witness(self.trace(0,0,0,check=0))

    def test_only_source_path_metadata_is_normalized(self):
        model={'modules':{'rvfi_testbench':{'cells':{'x':{'attributes':{'src':'old.sv:1','init':'01'},'connections':{'Q':[2]}}},'netnames':{}}}}
        normalized,changes=normalize_wrapper_metadata(model,'old.sv','new.sv')
        self.assertEqual(normalized['modules']['rvfi_testbench']['cells']['x']['attributes'],{'src':'new.sv:1','init':'01'})
        self.assertEqual(model['modules']['rvfi_testbench']['cells']['x']['attributes']['src'],'old.sv:1')
        self.assertEqual(normalized['modules']['rvfi_testbench']['cells']['x']['connections'],{'Q':[2]})
        self.assertEqual(changes,[('cells','x','src')])


if __name__=='__main__':unittest.main()

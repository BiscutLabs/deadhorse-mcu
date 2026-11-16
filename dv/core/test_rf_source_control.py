"""Independent nonzero RF selection/hazard witness fixtures."""
import unittest
from check_rf_source_control import witness


class RfControlWitnessTests(unittest.TestCase):
    def trace(self,data):
        lines=['$scope module rvfi_testbench $end']
        for i,n in enumerate(data):
            width=5 if n in ('rfReadAddress','rfWriteAddress','rfPriorAddress') else 1
            lines.append(f'$var wire {width} n{i} __rfcontrol_{n} $end')
        lines+=['$upscope $end','$enddefinitions $end','#5']
        for i,(n,v) in enumerate(data.items()):lines.append(f'b{v:b} n{i}')
        return '\n'.join(lines+['#10'])

    def test_real_read_address_hold_and_fault(self):
        for fault in (False,True):
            role='address-'+('fault' if fault else 'cover')
            data=dict(sourceStabilityActive=1,rfAddressHolds=int(not fault),rfReadAddress=6^int(fault),rfPriorAddress=6)
            self.assertEqual(witness(self.trace(data),role)['values'],data)
            for change in ({'sourceStabilityActive':0},{'rfReadAddress':0},{'rfPriorAddress':3}):
                with self.assertRaises(ValueError):witness(self.trace({**data,**change}),role)

    def test_real_write_hazard_and_nonconflicting_write(self):
        for fault in (False,True):
            role='conflict-'+('fault' if fault else 'cover')
            data=dict(sourceHolding=1,rfNoConflictHolds=int(not fault),rfReadAddress=8,
                      rfWriteEnable=1,rfWriteAddress=8 if fault else 9)
            self.assertEqual(witness(self.trace(data),role)['values'],data)
            for change in ({'sourceHolding':0},{'rfReadAddress':0},{'rfWriteAddress':9 if fault else 8}):
                with self.assertRaises(ValueError):witness(self.trace({**data,**change}),role)


if __name__=='__main__':unittest.main()

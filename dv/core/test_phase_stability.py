"""Independent active hold/one-edge tag witness fixtures."""
import unittest
from check_phase_stability import phase_witness


class PhaseStabilityTests(unittest.TestCase):
    def trace(self,data):
        lines=['$scope module rvfi_testbench $end']
        width=lambda n:68 if n in ('currentTag','previousTag') else 1
        for i,(n,v) in enumerate(data.items()): lines.append(f'$var wire {width(n)} n{i} __phase_{n} $end')
        lines+=['$upscope $end','$enddefinitions $end','#0']
        for i,(n,v) in enumerate(data.items()): lines.append(f'b{v:0{width(n)}b} n{i}')
        return '\n'.join(lines+['#10'])

    def test_immediate_real_pulse_fault_and_active_cover(self):
        for family,check,event in [('write','noWriteHolds','instructionWrite'),('clear','noClearHolds','idClear')]:
            for fault in (False,True):
                role=family+('-fault' if fault else '-cover')
                data={'holding':1,check:int(not fault),event:int(fault)}
                self.assertEqual(phase_witness(self.trace(data),role)['values'],data)
                data['holding']=0
                with self.assertRaises(ValueError): phase_witness(self.trace(data),role)

    def test_phase_bit_layout_and_delayed_check(self):
        # Independent tag encoding: instruction, PC, valid, first, compressed, dummy.
        prior=(0x00208067<<36)|(0x80000100<<4)|(1<<3)|(1<<2)
        for fault in (False,True):
            role='step-fault' if fault else 'step-cover'
            data={'stabilityActive':1,'stabilityHolds':int(not fault),'previousTag':prior,
                  'currentTag':prior^(4 if fault else 0)}
            self.assertEqual(phase_witness(self.trace(data),role)['values'],data)
            for changes in ({'stabilityActive':0},{'currentTag':prior^1},{'stabilityHolds':int(fault)}):
                with self.assertRaises(ValueError): phase_witness(self.trace({**data,**changes}),role)


if __name__=='__main__': unittest.main()

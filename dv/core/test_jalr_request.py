"""Independent saved-request witness examples and binding rejection."""
import copy
import unittest
from check_jalr_request import BINDINGS, OUTPUTS, attach, request_witness
import test_jalr_capture


class RequestTests(unittest.TestCase):
    def test_added_bindings_are_required_and_width_checked(self):
        original,monitor=test_jalr_capture.CaptureBindingTests().fixture()
        with self.assertRaises(ValueError): attach(original,monitor)
        fresh=10000
        for port,width in {'requestA':32,'requestB':32,'requestKind':2,'requestOp':7,
                           'requestFirst':1,'responseValid':1}.items():
            bits=list(range(fresh,fresh+width));fresh+=width
            monitor['ports'][port]=dict(direction='input',bits=bits)
            original['modules']['rvfi_testbench']['netnames'][BINDINGS[port]]=dict(bits=list(bits),attributes={})
        for port in OUTPUTS:
            if port not in monitor['ports']: monitor['ports'][port]=dict(direction='output',bits=['1'])
        attached,signals,nets=attach(original,monitor)
        self.assertEqual(attached['modules']['rvfi_testbench']['netnames'],original['modules']['rvfi_testbench']['netnames'])
        monitor['ports']['requestB']['bits'].pop()
        with self.assertRaises(ValueError): attach(original,monitor)

    def trace(self,role,changes=None):
        alignment=role.startswith('alignment')
        data=({'capture':1,'alignmentHolds':1,'requestA':2,'requestB':0xffffffff,
               'requestKind':0,'requestOp':0,'requestFirst':1,'responseValid':1,
               'sourceValue':2,'idInstruction':0xfff080e7} if alignment else
              {'executeActive':1,'executeAddHolds':1,'requestA':0x80000000,
               'requestB':0xffffffff,'executeTarget':0x7fffffff})
        if role=='alignment-zero': data.update(requestA=0,idInstruction=0xfff00067)
        if role=='alignment-fault': data.update(requestA=3,alignmentHolds=0)
        if role=='execute-fault': data.update(executeTarget=0x7ffffffd,executeAddHolds=0)
        if changes: data.update(changes)
        widths={'capture':1,'alignmentHolds':1,'requestKind':2,'requestOp':7,
                'requestFirst':1,'responseValid':1,'executeActive':1,'executeAddHolds':1}
        lines=['$scope module rvfi_testbench $end']
        for i,(n,v) in enumerate(data.items()): lines.append(f'$var wire {widths.get(n,32)} n{i} __request_{n} $end')
        lines+=['$upscope $end','$enddefinitions $end','#0']
        for i,(n,v) in enumerate(data.items()): lines.append(f'b{v:0{widths.get(n,32)}b} n{i}')
        return '\n'.join(lines+['#10'])

    def test_independent_operand_and_wrapping_sum_witnesses(self):
        for role in ('alignment-zero','alignment-negative','alignment-fault','execute-cover','execute-fault'):
            self.assertIn('values',request_witness(self.trace(role),role))
        for role,changes in [('alignment-negative',{'requestB':4095}),
                             ('alignment-negative',{'responseValid':0}),
                             ('alignment-negative',{'requestFirst':0}),
                             ('alignment-fault',{'capture':0}),
                             ('execute-cover',{'executeTarget':0xffffffff}),
                             ('execute-fault',{'executeActive':0})]:
            with self.subTest(role=role,changes=changes),self.assertRaises(ValueError):
                request_witness(self.trace(role,changes),role)


if __name__=='__main__': unittest.main()

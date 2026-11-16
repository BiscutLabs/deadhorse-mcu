import unittest
from check_jalr_operands import witness
from audit_jalr_operands import project


def trace(values):
    lines=['$scope module rvfi_testbench $end']
    for index, name in enumerate(values): lines.append(f'$var wire 32 v{index} __operand_{name} $end')
    lines += ['$upscope $end', '#10']
    for index, value in enumerate(values.values()): lines.append(f'b{value:b} v{index}')
    return '\n'.join(lines+['#20'])


class OperandWitnessTests(unittest.TestCase):
    def test_negative_immediate_issue(self):
        values=dict(issueActive=1, operandIssueHolds=1, incomingA=17,
                    incomingB=0xffffffff, incomingOp=0, sourceNow=17, idInstruction=0xfff08067)
        self.assertEqual(witness(trace(values),'issue-cover')['values'], values)
        values['incomingB']=0xfff
        with self.assertRaises(ValueError): witness(trace(values),'issue-cover')

    def test_exact_retention_fault(self):
        values=dict(ownerValid=1,operandRetentionHolds=0,requestA=2,requestB=3,requestOp=1,
                    ownerA=2,ownerB=3,ownerOp=0)
        self.assertEqual(witness(trace(values),'retention-fault')['values'],values)
        values['ownerValid']=0
        with self.assertRaises(ValueError): witness(trace(values),'retention-fault')

    def test_source_fault_requires_exact_bit_difference(self):
        values=dict(sourceStabilityActive=1,sourceStabilityHolds=0,sourceNow=5,sourceBefore=4)
        self.assertEqual(witness(trace(values),'source-fault')['values'],values)
        values['sourceNow']=7
        with self.assertRaises(ValueError): witness(trace(values),'source-fault')

    def test_projection_rejects_missing_extension(self):
        with self.assertRaises(ValueError): project({'ports':{}},{'ports':{}})


if __name__=='__main__': unittest.main()

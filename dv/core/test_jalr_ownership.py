"""Independent active-event fixtures, including minimal optimized trace fields."""
import unittest
from check_jalr_ownership import ownership_witness, attach, BINDINGS, OUTPUTS
from audit_jalr_ownership import retained_witness
import test_jalr_capture


class OwnershipTests(unittest.TestCase):
    def test_request_ports_are_bound_and_width_checked(self):
        original,monitor=test_jalr_capture.CaptureBindingTests().fixture()
        widths={'requestA':32,'requestB':32,'requestKind':2,'requestOp':7,'requestFirst':1,
                'responseValid':1,'reqValid':1,'reqReady':1,'incomingKind':2,'rspReady':1}
        with self.assertRaises(ValueError): attach(original,monitor)
        fresh=20000
        for port,width in widths.items():
            bits=list(range(fresh,fresh+width));fresh+=width
            monitor['ports'][port]=dict(direction='input',bits=bits)
            original['modules']['rvfi_testbench']['netnames'][BINDINGS[port]]=dict(bits=list(bits),attributes={})
        for port in OUTPUTS:
            if port not in monitor['ports']: monitor['ports'][port]=dict(direction='output',bits=['1'])
        result,signals,nets=attach(original,monitor)
        self.assertEqual(result['modules']['rvfi_testbench']['netnames'],original['modules']['rvfi_testbench']['netnames'])
        monitor['ports']['incomingKind']['bits'].pop()
        with self.assertRaises(ValueError): attach(original,monitor)

    def fixture(self,role):
        if role.startswith('issue'):
            return {'issueActive':1,'issueHolds':int(role=='issue-cover'),
                    'incomingKind':int(role=='issue-fault'),'idInstruction':0x8067}
        if role=='retention-fault':
            return {'ownerValid':1,'ownerKind':0,'requestKind':1,'retentionHolds':0}
        if role=='retention-cover':
            return {'ownerValid':1,'ownerKind':0,'requestKind':0,'ownerFirst':1,'requestFirst':1,
                    'responseValid':1,'ownerJalr':1,'retentionHolds':1}
        insn=0x8067 if role=='ownership-replacement' else 0x67
        result={'capture':1,'ownershipHolds':1,'ownerValid':1,'ownerJalr':1,'ownerFirst':1,
                'ownerInstruction':insn,'idInstruction':insn,'ownerPc':0x100,'idPc':0x100}
        if role=='ownership-replacement': result.update(captureReplacement=1,sourceValue=42)
        if role=='ownership-fault': result.update(ownershipHolds=0,idPc=0x104)
        return result

    def trace(self,data):
        width32={'idInstruction','ownerInstruction','ownerPc','idPc','sourceValue'}
        width2={'incomingKind','ownerKind','requestKind'}
        width=lambda n:32 if n in width32 else 2 if n in width2 else 1
        lines=['$scope module rvfi_testbench $end']
        for i,(n,v) in enumerate(data.items()): lines.append(f'$var wire {width(n)} n{i} __ownership_{n} $end')
        lines+=['$upscope $end','$enddefinitions $end','#0']
        for i,(n,v) in enumerate(data.items()): lines.append(f'b{v:0{width(n)}b} n{i}')
        return '\n'.join(lines+['#10'])

    def test_role_specific_witnesses_and_faults(self):
        for role in ('issue-cover','issue-fault','retention-cover','retention-fault',
                     'ownership-zero','ownership-replacement','ownership-fault'):
            data=self.fixture(role);self.assertEqual(ownership_witness(self.trace(data),role)['values'],data)
        for role,changes in [('issue-fault',{'incomingKind':0}),('retention-fault',{'ownerValid':0}),
                             ('ownership-zero',{'ownerPc':0}),('ownership-replacement',{'sourceValue':0}),
                             ('ownership-fault',{'idPc':0x100})]:
            data=self.fixture(role);data.update(changes)
            with self.subTest(role=role),self.assertRaises(ValueError): ownership_witness(self.trace(data),role)

    def test_retained_fault_requires_prior_bad_acceptance_and_later_state(self):
        fields=['ownerValid','ownerJalr','ownerKind','retainedKindHolds','issueActive','incomingKind']
        header=['$scope module rvfi_testbench $end']
        for i,n in enumerate(fields):
            header.append(f'$var wire {2 if n in ("ownerKind","incomingKind") else 1} n{i} __ownership_{n} $end')
        header+=['$upscope $end','$enddefinitions $end']
        def frame(time,values):
            return [f'#{time}']+[f'b{v:b} n{i}' for i,v in enumerate(values)]
        accepted=[0,0,0,1,1,1];retained=[1,1,1,0,0,0]
        text='\n'.join(header+frame(0,accepted)+frame(10,retained)+['#20'])
        result=retained_witness(text)
        self.assertEqual((result['accept_time'],result['violation_time']),(0,10))
        for before,after in [(retained,retained),([0,0,0,1,0,1],retained),(accepted,[0,1,1,0,0,0]),
                             (accepted,[1,1,1,1,0,0])]:
            with self.assertRaises(ValueError): retained_witness('\n'.join(header+frame(0,before)+frame(10,after)+['#20']))


if __name__=='__main__': unittest.main()

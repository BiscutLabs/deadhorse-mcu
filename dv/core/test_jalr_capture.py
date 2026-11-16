"""Synthetic state/binding and independently authored witness fixtures."""
import copy
import unittest
from check_jalr_capture import BINDINGS, OUTPUTS, TOP, attach, capture_witness


class CaptureBindingTests(unittest.TestCase):
    def fixture(self):
        widths={'idInstruction':32,'idPc':32,'pcMux':3,'executeTarget':32,
                'observedNextPc':32,'rvfiInstruction':32,'rvfiPc':32,'rvfiNextPc':32,
                'sourceValue':32,'rvfiSource':32}
        fresh=2;ports={};nets={}
        for port,name in BINDINGS.items():
            width=widths.get(port,1);bits=list(range(fresh,fresh+width));fresh+=width
            ports[port]=dict(direction='input',bits=bits)
            nets[name]=dict(bits=bits,attributes={})
        q=ports['rvfiNextPc']['bits'];clock=ports['clock']['bits'];reset=ports['reset']['bits']
        stage=dict(type='$aldff',parameters={'WIDTH':'100000','CLK_POLARITY':'1','ALOAD_POLARITY':'1'},
            attributes={},port_directions={'Q':'output','D':'input','CLK':'input','ALOAD':'input','AD':'input'},
            connections={'Q':q,'D':['0']*32,'CLK':clock,'ALOAD':reset,'AD':['0']*32})
        original={'modules':{TOP:dict(attributes={},ports={},netnames=nets,cells={'rvfi':stage,
            'source':dict(type='$anyseq',parameters={},attributes={},port_directions={'Y':'output'},
                          connections={'Y':ports['rvfiSource']['bits']})})}}
        # Minimal ghost state with a reset value; verify all cell connections and
        # net attributes survive the graft, not just the assertion expression.
        ghost=list(range(fresh,fresh+32));fresh+=32
        monitor_stage=copy.deepcopy(stage);monitor_stage['connections']['Q']=ghost
        monitor_stage['connections']['D']=ports['executeTarget']['bits']
        mports=copy.deepcopy(ports)
        for name in OUTPUTS:
            mports[name]=dict(direction='output',bits=ghost if name=='expectedTarget' else [ghost[0]])
        mnets={n:dict(bits=p['bits'],attributes={}) for n,p in mports.items()}
        mnets['ghost']=dict(bits=ghost,attributes={'init':'0'*32})
        return original,dict(ports=mports,netnames=mnets,cells={'ghost':monitor_stage})

    def test_state_reset_and_net_attributes_preserved(self):
        original,monitor=self.fixture();result,signals,nets=attach(original,monitor)
        self.assertEqual(result['modules'][TOP]['cells']['rvfi'],original['modules'][TOP]['cells']['rvfi'])
        c=result['modules'][TOP]['cells']['__capture_ghost']
        self.assertEqual(c['connections']['CLK'],monitor['ports']['clock']['bits'])
        self.assertEqual(c['connections']['ALOAD'],monitor['ports']['reset']['bits'])
        self.assertEqual(c['connections']['AD'],['0']*32)
        self.assertEqual(c['connections']['Q'],signals['expectedTarget'])
        self.assertEqual(nets['__capture_ghost']['attributes']['init'],'0'*32)
        self.assertEqual(result['modules'][TOP]['netnames'],original['modules'][TOP]['netnames'])

    def test_binding_inventory_width_and_clock_mismatches_rejected(self):
        for mutation in ('missing','width','clock','polarity','reset-data'):
            original,monitor=self.fixture()
            if mutation=='missing': del monitor['ports']['pcSet']
            elif mutation=='width': monitor['ports']['idInstruction']['bits'].pop()
            elif mutation=='clock': original['modules'][TOP]['cells']['rvfi']['connections']['CLK']=['0']
            elif mutation=='polarity': original['modules'][TOP]['cells']['rvfi']['parameters']['ALOAD_POLARITY']='0'
            else: original['modules'][TOP]['cells']['rvfi']['connections']['AD'][0]='1'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError): attach(original,monitor)


class CaptureWitnessTests(unittest.TestCase):
    def trace(self,role,mutation=None):
        source_role=role.startswith('source')
        insn=0xfff080e7 if not source_role else (0x67 if role=='source-zero' else 0x80e7)
        fields={'active':(1,int(source_role)),'capture':(1,int(not source_role)),'stageValid':(1,1),
            'sourceHolds':(1,1),'arithmeticHolds':(1,1),'holds':(1,1),
            'idInstruction':(32,insn),'rvfiInstruction':(32,insn),'sourceValue':(32,2),
            'rvfiSource':(32,0 if role=='source-zero' else 2),'expectedSource':(32,0 if role=='source-zero' else 2),
            'captureExpected':(32,0),'executeTarget':(32,1)}
        if role=='source-fault': fields.update(sourceHolds=(1,0),rvfiSource=(32,3))
        if role=='arithmetic-fault': fields.update(arithmeticHolds=(1,0),executeTarget=(32,3))
        if mutation: fields.update(mutation)
        for name in (['arithmeticHolds','captureExpected','executeTarget'] if source_role else ['active','stageValid','sourceHolds','holds','rvfiSource','expectedSource']): fields.pop(name,None)
        lines=['$scope module rvfi_testbench $end']
        for i,(name,(width,value)) in enumerate(fields.items()): lines.append(f'$var wire {width} n{i} __capture_{name} $end')
        lines+=['$upscope $end','$enddefinitions $end','#0']
        for i,(name,(width,value)) in enumerate(fields.items()): lines.append(f'b{value:0{width}b} n{i}')
        return '\n'.join(lines+['#10'])

    def test_independent_source_and_signed_arithmetic_witnesses(self):
        for role in ('source-zero','source-alias','source-fault','arithmetic-negative','arithmetic-odd','arithmetic-fault'):
            self.assertIn('expected_source' if role.startswith('source') else 'expected_target',capture_witness(self.trace(role),role))
        for role,mutation in [('source-alias',{'rvfiSource':(32,3)}),
                              ('source-fault',{'sourceHolds':(1,1)}),
                              ('arithmetic-negative',{'executeTarget':(32,4)}),
                              ('arithmetic-fault',{'capture':(1,0)})]:
            with self.subTest(role=role),self.assertRaises(ValueError): capture_witness(self.trace(role,mutation),role)


if __name__=='__main__': unittest.main()

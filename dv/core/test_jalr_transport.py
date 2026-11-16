"""Synthetic state/binding and independently authored witness fixtures."""
import copy
import unittest
from check_jalr_transport import BINDINGS, OUTPUTS, TOP, attach, transport_witness


class TransportBindingTests(unittest.TestCase):
    def fixture(self):
        widths={'idInstruction':32,'idPc':32,'pcMux':3,'executeTarget':32,
                'observedNextPc':32,'rvfiInstruction':32,'rvfiPc':32,'rvfiNextPc':32}
        fresh=2;ports={};nets={}
        for port,name in BINDINGS.items():
            width=widths.get(port,1);bits=list(range(fresh,fresh+width));fresh+=width
            ports[port]=dict(direction='input',bits=bits)
            nets[name]=dict(bits=bits,attributes={})
        q=ports['rvfiNextPc']['bits'];clock=ports['clock']['bits'];reset=ports['reset']['bits']
        stage=dict(type='$aldff',parameters={'WIDTH':'100000','CLK_POLARITY':'1','ALOAD_POLARITY':'1'},
            attributes={},port_directions={'Q':'output','D':'input','CLK':'input','ALOAD':'input','AD':'input'},
            connections={'Q':q,'D':['0']*32,'CLK':clock,'ALOAD':reset,'AD':['0']*32})
        original={'modules':{TOP:dict(attributes={},ports={},netnames=nets,cells={'rvfi':stage})}}
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
        c=result['modules'][TOP]['cells']['__transport_ghost']
        self.assertEqual(c['connections']['CLK'],monitor['ports']['clock']['bits'])
        self.assertEqual(c['connections']['ALOAD'],monitor['ports']['reset']['bits'])
        self.assertEqual(c['connections']['AD'],['0']*32)
        self.assertEqual(c['connections']['Q'],signals['expectedTarget'])
        self.assertEqual(nets['__transport_ghost']['attributes']['init'],'0'*32)
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


class TransportWitnessTests(unittest.TestCase):
    def trace(self,valid=1,expected=0x100,reported=0x100,holds=1,active=1):
        fields={'active':(1,active),'stageValid':(1,valid),'expectedTarget':(32,expected),
                'rvfiNextPc':(32,reported),'rvfiInstruction':(32,0x8067),'rvfiPc':(32,0x80),'holds':(1,holds)}
        lines=['$scope module rvfi_testbench $end']
        for i,(name,(width,value)) in enumerate(fields.items()):
            lines.append(f'$var wire {width} n{i} __transport_{name} $end')
        lines+=['$upscope $end','$enddefinitions $end','#0']
        for i,(name,(width,value)) in enumerate(fields.items()): lines.append(f'b{value:0{width}b} n{i}')
        return '\n'.join(lines+['#10'])

    def test_cover_and_exact_pc_bit_fault(self):
        self.assertEqual(transport_witness(self.trace())['expected'],'0x100')
        self.assertEqual(transport_witness(self.trace(reported=0x102,holds=0),True)['reported'],'0x102')
        for text in (self.trace(),self.trace(valid=0,reported=0x102,holds=0),
                     self.trace(reported=0x104,holds=0),self.trace(active=0,reported=0x102,holds=0),''):
            with self.assertRaises(ValueError): transport_witness(text,True)


if __name__=='__main__': unittest.main()

"""Malformed observer bindings must never qualify a production proof."""
import copy
import unittest
from sampling import PORTS, attach


def fixture():
    nets={};ports={};index=2;observer_bit=1000
    for name, names in PORTS.items():
        names=[names] if isinstance(names,str) else names
        for net in names:
            if net not in nets:
                nets[net]=dict(bits=[index],attributes={},hide_name=0);index+=1
        ports[name]=dict(direction='input',bits=list(range(observer_bit,observer_bit+len(names))))
        observer_bit+=len(names)
    base=dict(modules={'UsbEngine':dict(netnames=nets,ports={},cells={'existing':dict(
        type='$not',connections={'A':[2],'Y':[index]},port_directions={'A':'input','Y':'output'})})})
    monitor=dict(modules={'UsbSampling':dict(ports=ports,cells={'ref':dict(type='$not',
        connections={'A':ports['ce']['bits'],'Y':[2000]},port_directions={'A':'input','Y':'output'},parameters={})})})
    return base,monitor


class SamplingBindingTests(unittest.TestCase):
    def test_observers_preserve_original_graph_and_each_other(self):
        base,observer=fixture();old=copy.deepcopy(base)
        first,_=attach(base,observer,'one.');second,_=attach(first,observer,'two.')
        self.assertEqual(base,old)
        self.assertEqual(second['modules']['UsbEngine']['cells']['existing'],old['modules']['UsbEngine']['cells']['existing'])
        self.assertEqual(second['modules']['UsbEngine']['cells']['one.ref'],first['modules']['UsbEngine']['cells']['one.ref'])
        self.assertNotEqual(second['modules']['UsbEngine']['cells']['one.ref']['connections']['Y'],
                            second['modules']['UsbEngine']['cells']['two.ref']['connections']['Y'])

    def test_missing_mixed_and_driven_bindings_rejected(self):
        for kind in ('missing','width','output','alias','drive','assume','check-assume','collision'):
            base,observer=fixture();module=observer['modules']['UsbSampling']
            if kind=='missing':del base['modules']['UsbEngine']['netnames']['cadence.enable']
            if kind=='width':module['ports']['ce']['bits'].append(3000)
            if kind=='output':module['ports']['ce']['direction']='output'
            if kind=='alias':module['ports']['ce']['bits']=module['ports']['clock']['bits']
            if kind=='drive':module['cells']['ref']['connections']['Y']=module['ports']['ce']['bits']
            if kind=='assume':module['cells']['ref']['type']='$assume'
            if kind=='check-assume':module['cells']['ref'].update(type='$check',parameters={'FLAVOR':'assume'})
            if kind=='collision':base['modules']['UsbEngine']['cells']['sampling.ref']=copy.deepcopy(module['cells']['ref'])
            with self.subTest(kind=kind),self.assertRaises((ValueError,KeyError)):attach(base,observer)


if __name__=='__main__':unittest.main()

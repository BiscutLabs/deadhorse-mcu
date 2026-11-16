"""Fixtures for instrumentation projection and distinct binding faults."""
import copy
import unittest
from bind_float_integration import projection, mutate


class IntegrationBindingTests(unittest.TestCase):
    def normal(self):
        m={'ports':{'checking':{'direction':'input','bits':[1]},'result':{'direction':'output','bits':[3]}},
           'cells':{'state':{'type':'$aldff','parameters':{},'connections':{'Q':[3],'D':[2],'AD':['0'],'CLK':[4]},
                            'port_directions':dict(Q='output',D='input',AD='input',CLK='input')}},
           'netnames':{'result':{'bits':[3],'attributes':{}}}}
        for i in range(28):m['cells']['assert'+str(i)]={'type':'$check','parameters':{'FLAVOR':'assert'},'connections':{'A':[1]}}
        return {'modules':{'FloatIntegrationFormal':m}}

    def test_only_assert_instrumentation_is_removed(self):
        source=self.normal();before=copy.deepcopy(source);out,removed=projection(source)
        self.assertEqual(len(removed),28)
        self.assertEqual(set(out['modules']['ibex_core']['cells']),{'state'})
        self.assertEqual(source,before)
        source['modules']['FloatIntegrationFormal']['cells']['assert0']['parameters']['FLAVOR']='assume'
        with self.assertRaises(ValueError):projection(source)

    def test_constant_reset_cell_parameter_mutation(self):
        source,_=projection(self.normal());cell=source['modules']['ibex_core']['cells']['state']
        cell['type']='$adff';cell['parameters']['ARST_VALUE']='0'
        del cell['connections']['AD'];del cell['port_directions']['AD']
        cell['connections']['ARST']=[1];cell['port_directions']['ARST']='input'
        bad,detail=mutate(source,'reset-value')
        self.assertEqual(detail['parameter'],'ARST_VALUE')
        self.assertEqual(bad['modules']['ibex_core']['cells']['state']['parameters']['ARST_VALUE'],'1')
        self.assertEqual(cell['parameters']['ARST_VALUE'],'0')

    def test_output_reset_next_state_and_clock_faults_are_distinct(self):
        source,_=projection(self.normal())
        for name,port in [('reset-value','AD'),('next-state','D'),('clock','CLK')]:
            bad,detail=mutate(source,name)
            self.assertEqual(detail['port'],port)
            self.assertNotEqual(bad['modules']['ibex_core']['cells']['state']['connections'][port],
                                source['modules']['ibex_core']['cells']['state']['connections'][port])
        bad,detail=mutate(source,'output')
        self.assertEqual(detail['port'],'result')
        self.assertNotEqual(bad['modules']['ibex_core']['ports']['result']['bits'],[3])
        self.assertEqual(source['modules']['ibex_core']['ports']['result']['bits'],[3])


if __name__=='__main__':unittest.main()

import unittest
from check_critical_isa_checkall import checkall_config, model_inventory


class CheckallTests(unittest.TestCase):
    def test_only_native_solver_option_changes(self):
        source='[options]\nmode bmc\ndepth 144\nmulticlock on\ntimeout 120\n[engines]\nbtor btormc\n[script]\nread_json /work/build/original.json\n'
        result=checkall_config(source)
        self.assertEqual(result.replace('btormc --checkall','btormc'),source)
        for old,new in [('depth 144','depth 143'),('timeout 120','timeout 121'),('mode bmc','mode prove'),('multiclock on','multiclock off'),('btor btormc','btor pono')]:
            with self.assertRaises(ValueError):checkall_config(source.replace(old,new))

    def test_complete_inventory_retains_constraints(self):
        cells={f'p{i}':{'type':'$assert','connections':{'A':[i+2],'EN':['1']}} for i in range(33)}
        cells['a']={'type':'$assume','connections':{'A':[99],'EN':['1']}}
        model={'modules':{'rvfi_testbench':{'cells':cells}}}
        saved=model_inventory(model)
        self.assertEqual(len(saved['assertions']),33)
        self.assertEqual(saved['assumptions_and_covers'],{'a':cells['a']})
        del cells['p0']
        with self.assertRaises(ValueError):model_inventory(model)


if __name__=='__main__':unittest.main()

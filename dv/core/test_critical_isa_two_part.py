import copy
import unittest
from assertion_partitions import assertions, partition, validate_partition, validate_union
from check_critical_isa_two_part import checkall_config


class TwoPartTests(unittest.TestCase):
    def test_exact_partition_and_missing_property_negative(self):
        cells={f'p{i:02d}':{'type':'$assert','connections':{'A':[i+2],'EN':['1']}} for i in range(33)}
        cells['constraint']={'type':'$assume','connections':{'A':[90],'EN':['1']}}
        cells['state']={'type':'$dff','connections':{'D':[80],'Q':[81],'CLK':[82]}}
        original={'modules':{'rvfi_testbench':{'cells':cells}}}
        names=assertions(original);groups=[names[:11],names[11:]]
        validate_union(names,groups)
        for group in groups:
            selected=partition(original,group)
            self.assertEqual(set(selected['modules']['rvfi_testbench']['cells']),set(group)|{'constraint','state'})
            for mutated in ('constraint','state'):
                bad=copy.deepcopy(selected)
                bad['modules']['rvfi_testbench']['cells'][mutated]['connections']['A']=[0]
                with self.assertRaises(ValueError):validate_partition(original,bad,group)
        with self.assertRaises(ValueError):validate_union(names,[groups[0][:-1],groups[1]])
        with self.assertRaises(ValueError):validate_union(names,[groups[0]+groups[1][:1],groups[1]])

    def test_native_config_preserves_bounds(self):
        original='[options]\nmode bmc\ndepth 144\nmulticlock on\ntimeout 120\n[engines]\nbtor btormc\n[script]\nread_json /work/build/x.json\n'
        self.assertEqual(checkall_config(original).replace(' --checkall',''),original)


if __name__=='__main__':unittest.main()

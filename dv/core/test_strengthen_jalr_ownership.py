"""Monitor projection must preserve the inherited interface and input objects."""
import copy
import unittest
from strengthen_jalr_ownership import project_monitor


class ProjectionTests(unittest.TestCase):
    def fixture(self):
        old=dict(ports={'clock':dict(direction='input',bits=[1]),
                        'ownerJalr':dict(direction='output',bits=[2])},cells={},netnames={},attributes={})
        new=copy.deepcopy(old)
        for i,n in enumerate(('instructionWrite','holding','noWriteHolds','noClearHolds',
                              'stabilityActive','stabilityHolds','currentTag','previousTag')):
            new['ports'][n]=dict(direction='input' if n=='instructionWrite' else 'output',bits=[10+i])
        return old,new

    def test_only_exact_extra_interface_removed(self):
        old,new=self.fixture();saved=copy.deepcopy((old,new))
        gold,candidate=project_monitor(old,new)
        self.assertEqual((old,new),saved)
        self.assertEqual(gold,candidate)

    def test_missing_extra_changed_width_and_direction_rejected(self):
        for change in ('missing','width','direction','extra'):
            old,new=self.fixture()
            if change=='missing': del new['ports']['holding']
            elif change=='width': new['ports']['ownerJalr']['bits'].append(3)
            elif change=='direction': new['ports']['ownerJalr']['direction']='input'
            else: new['ports']['unexpected']=dict(direction='input',bits=[99])
            with self.subTest(change=change),self.assertRaises(ValueError): project_monitor(old,new)


if __name__=='__main__': unittest.main()

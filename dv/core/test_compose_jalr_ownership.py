"""Independent ISA samples and rejected transition-binding fixtures."""
import copy
import random
import unittest
from compose_jalr_ownership import jalr, check_states, frame


def evaluate(module, values, output):
    def read(bits):
        return sum((int(b) if isinstance(b,str) else values[b]) << i for i,b in enumerate(bits))
    for c in module['cells'].values():
        p = c['connections']; a = read(p['A'])
        b = read(p['B']) if 'B' in p else None
        kind = c['type']
        value = {'$and': lambda:a & b, '$or':lambda:a | b,
                 '$not':lambda:int(not a), '$eq':lambda:int(a == b)}[kind]()
        for i,bit in enumerate(p['Y']): values[bit] = value >> i & 1
    return read(output)


class CompositionTests(unittest.TestCase):
    def test_jalr_predicate_against_independent_instruction_examples(self):
        # Dummy cell only allocates the 68 free tag bits for the gate allocator.
        m = {'cells':{'input':{'connections':{'A':list(range(1,69))}}}}
        output = jalr(m,list(range(1,69))); del m['cells']['input']
        rng = random.Random(0x67)
        examples = [(0x00000067,True),(0xfff080e7,True),(0x00001067,False),
                    (0x0000006f,False),(0x00000063,False),(0x00000013,False)]
        examples += [(rng.getrandbits(32)&~0x707f|0x67,True) for _ in range(20)]
        for instruction,is_jalr in examples:
            for flags in range(16):
                # low flags: dummy, compressed, first, valid.
                tag = (instruction<<36)|(rng.getrandbits(32)<<4)|flags
                values = {i+1:tag>>i&1 for i in range(68)}
                self.assertEqual(evaluate(m,values,output), int(is_jalr and flags==12))

    def fixture(self):
        ports = {}; index = 1
        for name,width in [('clock',1),('reset',1),('idDummy',1),('idCompressed',1),
            ('idFirst',1),('idValid',1),('idPc',32),('idInstruction',32),
            ('ownerValid',1),('ownerJalr',1),('ownerFirst',1),
            ('ownerInstruction',32),('ownerPc',32),('previousTag',68)]:
            ports[name] = {'direction':'output' if name.startswith('owner') or name=='previousTag' else 'input',
                           'bits':list(range(index,index+width))}
            index += width
        ports['currentTag'] = {'direction':'output','bits':sum((ports[n]['bits'] for n in
            ('idDummy','idCompressed','idFirst','idValid','idPc','idInstruction')),[])}
        cells = {}
        for name in ('ownerValid','ownerJalr','ownerFirst','ownerInstruction','ownerPc','previousTag'):
            q = ports[name]['bits']; width = len(q)
            cells[name] = {'type':'$aldff','parameters':{'WIDTH':format(width,'b'),
                'CLK_POLARITY':'1','ALOAD_POLARITY':'1'},
                'connections':{'Q':q,'D':q,'AD':['0']*width,
                    'CLK':ports['clock']['bits'],'ALOAD':ports['reset']['bits']},
                'port_directions':dict(Q='output',D='input',AD='input',CLK='input',ALOAD='input')}
        return {'ports':ports,'cells':cells}

    def test_reject_changed_clock_reset_and_tag(self):
        original = self.fixture()
        self.assertEqual(len(check_states(original)),135)
        for path,value in [(('connections','CLK'),[999]),(('connections','ALOAD'),[999]),
                           (('parameters','CLK_POLARITY'),'0'),(('parameters','ALOAD_POLARITY'),'0'),
                           (('connections','AD'),['x'])]:
            bad = copy.deepcopy(original); bad['cells']['ownerValid'][path[0]][path[1]]=value
            with self.assertRaises(ValueError): check_states(bad)
        bad = copy.deepcopy(original); bad['ports']['currentTag']['bits'].reverse()
        with self.assertRaises(ValueError): check_states(bad)

    def test_frame_substitution_must_cover_every_state_bit(self):
        original = self.fixture(); m = {'ports':{},'cells':{}}
        with self.assertRaises(ValueError): frame(m,original,'next_',{})
        states = check_states(original)
        ports,mapping = frame(m,original,'reset_',{q:r for q,(_,r) in states.items()})
        self.assertEqual(ports['ownerValid'],['0'])
        self.assertEqual(ports['ownerInstruction'],['0']*32)
        self.assertFalse(m['cells'])
        self.assertEqual(set(mapping), set(b for p in original['ports'].values() for b in p['bits']))


if __name__ == '__main__': unittest.main()

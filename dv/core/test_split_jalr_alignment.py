"""Independent Boolean/reference fixtures for exact alignment partitioning."""
import copy
import itertools
import unittest
from split_jalr_alignment import TOP, LABELS, split_alignment, qualification
from jalr_invariant import gate, property_cell
from assertion_partitions import partition, validate_partition, validate_union


def fixture():
    m=dict(attributes={},ports={},netnames={},cells={});fresh=1
    for name,width in [('capture',1),('responseValid',1),('requestFirst',1),('requestKind',2),
                       ('requestOp',7),('requestA',32),('requestB',32),('normalizedSource',32),('idInstruction',32)]:
        bits=list(range(fresh,fresh+width));fresh+=width
        m['netnames']['__request_'+name]=dict(bits=bits,attributes={})
        m['cells']['input_'+name]=dict(type='$anyseq',parameters={'WIDTH':format(width,'b')},attributes={},
            port_directions={'Y':'output'},connections={'Y':bits})
    def net(n): return m['netnames']['__request_'+n]['bits']
    def op(kind,a,b=None):
        result=gate(m,kind,a,b)
        old='__jalr_gate_'+str(result[0]);m['cells']['__request_'+str(result[0])]=m['cells'].pop(old)
        return result
    insn=net('idInstruction')
    leaves=[net('responseValid'),op('$logic_not',net('requestKind')),op('$logic_not',net('requestOp')),
            net('requestFirst'),op('$eq',net('requestA'),net('normalizedSource')),
            op('$eq',net('requestB'),insn[20:32]+[insn[31]]*20)]
    combined=leaves[0]
    for leaf in leaves[1:]: combined=op('$and',combined,leaf)
    root=op('$or',op('$not',net('capture')),combined)
    m['cells']['__request_assert']=property_cell('assert',root)
    m['cells']['environment']=property_cell('assume',['1'])
    return {'modules':{TOP:m}}


class AlignmentPartitionTests(unittest.TestCase):
    def test_exact_inventory_and_environment(self):
        original=fixture();saved=copy.deepcopy(original)
        model,groups,info=split_alignment(original)
        self.assertEqual(original,saved)
        self.assertEqual(len(groups),6)
        self.assertEqual([g[0] for g in groups],['__alignment_'+n for n in LABELS])
        self.assertEqual(model['modules'][TOP]['netnames'],original['modules'][TOP]['netnames'])
        for group in groups:
            child=partition(model,group);validate_partition(model,child,group)
            self.assertEqual(child['modules'][TOP]['cells']['environment'],original['modules'][TOP]['cells']['environment'])
        with self.assertRaises(ValueError): validate_union([g[0] for g in groups],groups[:-1])
        with self.assertRaises(ValueError): validate_union([g[0] for g in groups],groups+[groups[0]])

    def test_semantic_mutations_rejected(self):
        for mutation in ('enable','guard','operand','width','duplicate'):
            original=fixture();m=original['modules'][TOP]
            if mutation=='enable': m['cells']['__request_assert']['connections']['EN']=['0']
            elif mutation=='guard': m['netnames']['__request_capture']['bits']=['1']
            else:
                cells=[c for n,c in m['cells'].items() if n.startswith('__request_') and c['type']=='$eq']
                if mutation=='operand': cells[-1]['connections']['B'][-1]='0'
                elif mutation=='width': cells[-1]['parameters']['B_WIDTH']='11111'
                else: m['netnames']['__request_responseValid']['bits']=m['netnames']['__request_requestFirst']['bits']
            with self.subTest(mutation=mutation),self.assertRaises(ValueError): split_alignment(original)

    def test_exhaustive_free_boolean_reference_and_negative(self):
        model,groups,info=split_alignment(fixture())
        def evaluate(q,inputs):
            m=q['modules'][TOP];values=dict(inputs)
            drivers={c['connections']['Y'][0]:c for c in m['cells'].values()}
            def bit(b):
                if isinstance(b,str): return int(b)
                if b in values: return values[b]
                c=drivers[b];a=bit(c['connections']['A'][0]);kind=c['type']
                other=bit(c['connections']['B'][0]) if 'B' in c['connections'] else None
                value={'$not':lambda:1-a,'$and':lambda:a&other,'$or':lambda:a|other,'$eq':lambda:int(a==other)}[kind]()
                values[b]=value;return value
            return bit(m['ports']['same']['bits'][0])
        good=qualification(model,info);bad=qualification(model,info,True)
        cuts=[info['capture'][0],*[b[0] for b in info['leaves']]]
        for bits in itertools.product((0,1),repeat=7):
            inp=dict(zip(cuts,bits));self.assertEqual(evaluate(good,inp),1)
            expected=int(not(bits[0] and all(bits[1:6]) and not bits[6]))
            self.assertEqual(evaluate(bad,inp),expected)


if __name__=='__main__': unittest.main()

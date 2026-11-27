"""Three-valued, two-phase capture replay from the actual inserted pin graph.

Uncontrollable analog/memory values stay unknown. Pad feedback and receiver
enables are modeled, not exposed as arbitrary internal primary inputs.
This is capture-model qualification, not an ATPG coverage measurement.
"""
import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import random
import re
import sys
import time

from scan_cells import PREFIX, groups, expression, model as ff_model

ROOT=Path(__file__).resolve().parents[2]
MASK=(1<<64)-1
ZERO=(0,MASK)
ONE=(MASK,MASK)
UNKNOWN=(0,0)


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def parse(text):
    text=re.sub(r'\s+','',text).replace('*','&').replace('+','|')
    tokens=re.findall(r'[A-Za-z_][A-Za-z_0-9]*|[01!&|^()]',text)
    if ''.join(tokens)!=text:raise ValueError('Unknown Liberty expression')
    pos=0
    def term():
        nonlocal pos
        t=tokens[pos];pos+=1
        if t=='!':return ('!',term())
        if t=='(':
            n=level(0)
            if tokens[pos]!=')':raise ValueError('Missing parenthesis')
            pos+=1;return n
        if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*|[01]',t):raise ValueError('Unknown atom')
        return t
    def level(i):
        nonlocal pos
        if i==3:return term()
        n=level(i+1)
        while pos<len(tokens) and tokens[pos]=='|^&'[i]:
            op=tokens[pos];pos+=1;n=(op,n,level(i+1))
        return n
    result=level(0)
    if pos!=len(tokens):raise ValueError('Trailing expression')
    return result


def evaluate(ast,leaf):
    if isinstance(ast,str):return ZERO if ast=='0' else ONE if ast=='1' else leaf(ast)
    a,ak=evaluate(ast[1],leaf)
    if ast[0]=='!':return (~a&MASK,ak)
    b,bk=evaluate(ast[2],leaf)
    if ast[0]=='&':return (a&b,((ak&~a)|(bk&~b)|(ak&bk))&MASK)
    if ast[0]=='|':return (a|b,((ak&a)|(bk&b)|(ak&bk))&MASK)
    if ast[0]=='^':return (a^b,ak&bk)
    raise ValueError('Unknown Boolean operator')


def qualify_pads(path):
    cells=dict(groups(path.read_text(),'cell'))
    def function(kind,pin,attribute='function'):
        pins=dict(groups(cells[kind],'pin'))
        found=re.findall(r'\b'+attribute+r'\s*:\s*"([^"]+)"',pins[pin])
        if len(found)!=1:raise ValueError('Missing pad equation')
        return found[0].replace('*','&').replace('+','|')
    bi='gf180mcu_fd_io__bi_24t'
    fs={k:function(*k) for k in ((bi,'PAD'),(bi,'Y'),('gf180mcu_fd_io__in_c','Y'),('gf180mcu_fd_io__in_s','Y'))}
    tristate=function(bi,'PAD','three_state')
    for bits in itertools.product((False,True),repeat=4):
        v=dict(zip(('A','OE','IE','PAD'),bits))
        if expression(fs[bi,'PAD'],v)!=v['A'] or expression(tristate,v)!=(not v['OE']):raise ValueError('Changed pad drive model')
        if expression(fs[bi,'Y'],v)!=(v['IE'] and v['PAD']):raise ValueError('Changed receiver model')
        for kind in ('gf180mcu_fd_io__in_c','gf180mcu_fd_io__in_s'):
            if expression(fs[kind,'Y'],v)!=v['PAD']:raise ValueError('Changed input pad model')
    return 'Liberty drive A when OE, receive IE AND resolved PAD; external fixture drives only when OE=0. Electrical behavior excluded.'


class Capture:
    def __init__(self, graph, before, manifest, controls, core, cells):
        self.graph=graph;self.before=before;self.manifest=manifest;self.controls=controls
        self.drivers={}
        for name,c in graph.items():
            for pin in controls['output_pins'][c['type']]:
                n=c['pins'][pin]
                if n is not None:
                    if n in self.drivers:raise ValueError('Multiple data drivers')
                    self.drivers[n]=(name,pin)
        self.functions={}
        for kind in (PREFIX+'dffrnq_1',PREFIX+'dffnrnq_1'):
            ff,pins=ff_model(cells[kind]);negative='dffnrnq' in kind
            if set(ff)!={'clocked_on','next_state','clear'}:raise ValueError('Changed controller state semantics')
            for d,rn,clock,q in itertools.product((False,True),repeat=4):
                values=dict(D=d,RN=rn,IQ1=q,IQN1=not q,**{'CLKN' if negative else 'CLK':clock})
                if (expression(ff['next_state'],values)!=d or expression(ff['clear'],values)!=(not rn)
                    or expression(ff['clocked_on'],values)!=((not clock) if negative else clock)
                    or expression(pins['Q'][1],values)!=q):
                    raise ValueError('Controller finite trace uses wrong primitive relation')
        for kind in {c['type'] for c in graph.values()} & set(cells):
            if kind.startswith(PREFIX+'sdff') or kind.startswith(PREFIX+'dff') or kind.startswith(PREFIX+'icgtp'):continue
            pins=dict(groups(cells[kind],'pin'))
            for pin in controls['output_pins'][kind]:
                f=re.findall(r'\bfunction\s*:\s*"([^"]+)"',pins[pin])
                if len(f)!=1:raise ValueError('Unmodeled combinational output')
                ast=parse(f[0]);self.functions[kind,pin]=ast
                names=sorted(set(re.findall(r'[A-Za-z_][A-Za-z_0-9]*',f[0])))
                # Independent scalar evaluator vs bit-parallel AST on every
                # primitive truth-table assignment; no RTL source matching.
                for bits in itertools.product((False,True),repeat=len(names)):
                    values=dict(zip(names,bits));expected=expression(f[0],values)
                    got=evaluate(ast,lambda n:ONE if values[n] else ZERO)
                    if got!=(ONE if expected else ZERO):raise ValueError('Primitive evaluator mismatch')
        self.scanned={n for r in manifest['lanes'] for n in r['cells']}
        self.rising={n for r in manifest['lanes'] if r['clock_pin']=='CLK' for n in r['cells']}
        self.falling=self.scanned-self.rising
        self.pad_fixed={};self.fixture_pads={}
        # Bind required fixture inputs through actual pre-insertion core
        # endpoints and the actual input pad's Y terminal.
        fixed={'aonClockIn':0,'aonClockSelect':1,'porBypass':1,'externalReset_n':1,
            'pins_inactive_jtagTck':0,'pins_inactive_jtagTms':1,'pins_inactive_jtagTdi':1,
            'pins_uartRx_1':1,'pins_uartRx_2':0,'oscIn':0}
        for port,value in fixed.items():
            bits=core['ports'][port]['bits']
            if len(bits)!=1:raise ValueError('Non-scalar fixture input')
            matches=[('i_chip_core.soc.'+n,p) for n,c in core['cells'].items() for p,v in c['connections'].items()
                if v==bits and c['port_directions'][p]=='input']
            if not matches:raise ValueError('Unbound fixture input')
            net=before[matches[0][0]]['pins'][matches[0][1]]
            name,pin=self.drivers[net];pad=graph[name]
            if pin!='Y' or pad['type'] not in ('gf180mcu_fd_io__in_c','gf180mcu_fd_io__in_s'):
                raise ValueError('Fixture pin is not a dedicated input pad')
            self.pad_fixed[pad['pins']['PAD']]=value
            self.fixture_pads[port]=pad['pins']['PAD']
            if port=='oscIn':self.osc_pad=pad['pins']['PAD']
        rng=random.Random(37)
        self.stimuli={c['pins']['PAD']:(rng.getrandbits(64),MASK) for c in graph.values()
            if c['type'] in ('gf180mcu_fd_io__bi_24t','gf180mcu_fd_io__in_c','gf180mcu_fd_io__in_s')}
        self.initial={graph[n]['pins']['Q']:(rng.getrandbits(64),MASK) for n in sorted(self.scanned)}
        self.entry={graph[n]['pins']['Q']:ONE for n in manifest['excluded']}
        # Reached controller state: position31, closed/accepted/active1, all
        # shared release bits1. Bind to the independently proved access model.
        if set(manifest['excluded'].values())!={
            *('testAccess.armed_position['+str(i)+']' for i in range(5)),
            'testAccess.armed[0]','testAccess.armed_closed[0]','_testAccess_testMode[0]',
            'testAccess._fallingRelease_released[0]','testAccess.fallingRelease.first[0]',
            'testAccess._release_released[0]','testAccess.release_0.first[0]'}:
            raise ValueError('Changed entered access state')

    def settle(self,state,phase,fault=None,entry=None,pad_override=None):
        graph=self.graph;controls=self.controls
        cache={controls['zero']:ZERO,controls['one']:ONE,**state,**(self.entry if entry is None else entry)}
        cache.update(self.stimuli)
        cache.update({n:ONE if v else ZERO for n,v in self.pad_fixed.items()})
        cache[self.osc_pad]=ONE if phase else ZERO
        if pad_override is not None:cache.update(pad_override)
        # ICG control/path qualification establishes Q follows OSC after the
        # parked-low entry. Clock/control faults are excluded from this model.
        for name in self.manifest['clock_gates']:
            cache[graph[name]['pins']['Q']]=(ONE if phase else ZERO) if entry is None else UNKNOWN
        visiting=set();unknown=set();evaluated=set()
        def read(net):
            if net in cache:return cache[net]
            if net in visiting:raise ValueError('Combinational/capture loop: '+str(net))
            if net not in self.drivers:
                unknown.add(str(net));cache[net]=UNKNOWN;return UNKNOWN
            visiting.add(net);name,pin=self.drivers[net];c=graph[name];p=c['pins'];kind=c['type']
            def input(pin):
                if fault and fault[:2]==(name,pin):return ONE if fault[2] else ZERO
                return read(p[pin])
            if fault and fault[:2]==(name,pin):v=ONE if fault[2] else ZERO
            elif (kind,pin) in self.functions:
                v=evaluate(self.functions[kind,pin],input);evaluated.add(name)
            elif kind in ('gf180mcu_fd_io__in_c','gf180mcu_fd_io__in_s') and pin=='Y':v=read(p['PAD'])
            elif kind=='gf180mcu_fd_io__bi_24t' and pin=='Y':
                ie=input('IE');oe=input('OE')
                if ie==ZERO:v=ZERO
                elif ie!=ONE or oe not in (ZERO,ONE):raise ValueError('Test receiver/driver is not fixed')
                else:v=input('A') if oe==ONE else read(p['PAD'])
            else:
                unknown.add(name+'/'+pin);v=UNKNOWN
            visiting.remove(net);cache[net]=v;return v
        return read,dict(evaluated=evaluated,unknown_sources=unknown)

    def phase(self,state,phase,fault=None):
        graph=self.graph
        read,info=self.settle(state,phase,fault)
        sampled={}
        names=self.rising if phase==0 else self.falling
        for name in sorted(names):
            if fault and fault[:2]==(name,'D'):sampled[name]=ONE if fault[2] else ZERO
            else:sampled[name]=read(graph[name]['pins']['D'])
        return sampled,dict(evaluated=len(info['evaluated']),unknown_sources=sorted(info['unknown_sources']),
            unknown_sampled=[n for n,v in sampled.items() if v[1]!=MASK])

    def verify_entry(self):
        """Execute the exact finite entry protocol on mapped controller cells.

        All unrelated pad values, scanned state, and analog/memory outputs are
        UNKNOWN. Known results therefore cannot borrow arbitrary fixed values
        from those sources. This is a deterministic gate-level trace, not a
        replacement for the existing unbounded public-output proof.
        """
        state={n:UNKNOWN for n in self.entry}
        scanned={n:UNKNOWN for n in self.initial}
        pads={n:UNKNOWN for n in self.stimuli}
        pads.update({n:ONE if v else ZERO for n,v in self.pad_fixed.items()})
        pads[self.fixture_pads['pins_uartRx_1']]=ZERO
        reset=self.fixture_pads['externalReset_n'];tck=self.fixture_pads['pins_inactive_jtagTck'];tdi=self.fixture_pads['pins_inactive_jtagTdi']
        def reading():return self.settle(scanned,0,entry=state,pad_override=pads)[0]
        def async_settle():
            nonlocal state
            for _ in range(16):
                read=reading();new=dict(state)
                for name in self.manifest['excluded']:
                    c=self.graph[name];p=c['pins']
                    if c['type'] not in (PREFIX+'dffrnq_1',PREFIX+'dffnrnq_1'):
                        raise ValueError('Unsupported controller FF relation')
                    rn=read(p['RN'])
                    if rn==ZERO:new[p['Q']]=ZERO
                    elif rn!=ONE:new[p['Q']]=UNKNOWN
                if new==state:return
                state=new
            raise ValueError('Controller async reset does not settle')
        def edge(level):
            nonlocal state
            oldread=reading()
            oldclocks={n:oldread(c['pins']['CLKN' if 'CLKN' in c['pins'] else 'CLK'])
                for n,c in self.graph.items() if n in self.manifest['excluded']}
            pads[tck]=ONE if level else ZERO
            read=reading();new=dict(state)
            for name in self.manifest['excluded']:
                p=self.graph[name]['pins'];negative='CLKN' in p;clk=read(p['CLKN' if negative else 'CLK'])
                if oldclocks[name] not in (ZERO,ONE) or clk not in (ZERO,ONE):raise ValueError('Unknown controller clock')
                event=(oldclocks[name]==ONE and clk==ZERO) if negative else (oldclocks[name]==ZERO and clk==ONE)
                if event:
                    rn=read(p['RN'])
                    new[p['Q']]=ZERO if rn==ZERO else read(p['D']) if rn==ONE else UNKNOWN
            state=new;async_settle()
        pads[reset]=ZERO;pads[tck]=ZERO;async_settle()
        if any(v!=ZERO for v in state.values()):raise ValueError('Controller reset not established')
        pads[reset]=ONE;async_settle()
        for _ in range(2):edge(1);edge(0)
        for bit in f'{0xD37A6C95:032b}':
            pads[tdi]=ONE if bit=='1' else ZERO;edge(1);edge(0)
        if state!=self.entry:raise ValueError('Actual entry trace does not establish capture cut state')
        return dict(status='known_exact_state',positive_edges=34,negative_edges=34,
            unrelated_state_and_inputs='unknown',values={n:1 for n in state})

    def capture(self,fault=None,simultaneous=False):
        positive,pinfo=self.phase(self.initial,0,fault)
        updated=dict(self.initial)
        if not simultaneous:updated.update({self.graph[n]['pins']['Q']:v for n,v in positive.items()})
        negative,ninfo=self.phase(updated,1,fault)
        return {**positive,**negative},[pinfo,ninfo]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--insert',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--core',type=Path,required=True)
    p.add_argument('--liberty',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    result=dict(status='error',scope='64 seeded two-phase capture vectors; no ATPG/transition/electrical claim',
        inputs={str(q):sha(q) for q in (Path(__file__),Path(__file__).with_name('scan_cells.py'),
            Path(__file__).with_name('usb_cells.py'),ROOT/'tools/timing/usb_boundary.py',
            ROOT/'phys/gf180-ws-1x1/pdk-lock.json',a.insert/'result.json',a.manifest,a.core,a.liberty)})
    try:
        r=json.loads((a.insert/'result.json').read_text());m=json.loads(a.manifest.read_text())
        if r['status']!='pass_unplaced_insertion':raise ValueError('Insertion not qualified')
        for name in ('after.json','before.json','chains.json'):
            if sha(a.insert/name)!=r['artifacts'][name]:raise ValueError('Stale graph')
        if sha(a.manifest) not in r['input_sha256'].values() or sha(a.core) not in m['input_sha256'].values():
            raise ValueError('Mismatched input provenance')
        lock=json.loads((ROOT/'phys/gf180-ws-1x1/pdk-lock.json').read_text())
        if sha(a.liberty)!=lock['files'][a.liberty.name]:raise ValueError('Unpinned Liberty')
        padlib=a.liberty.parents[2]/'gf180mcu_fd_io/lib/gf180mcu_fd_io__tt_025C_3v30.lib'
        if sha(padlib) not in r['input_sha256'].values():raise ValueError('Unbound pad Liberty')
        result['inputs'][str(padlib)]=sha(padlib)
        result['pad_model']=qualify_pads(padlib)
        model=Capture(json.loads((a.insert/'after.json').read_text()),json.loads((a.insert/'before.json').read_text()),m,r['controls'],
            json.loads(a.core.read_text())['modules']['DeadhorseSoc'],dict(groups(a.liberty.read_text(),'cell')))
        result['entry_trace']=model.verify_entry()
        correct,info=model.capture();result['phases']=info
        if any(row['unknown_sampled'] for row in info):raise ValueError('Unknown physical source reaches capture')
        wrong,_=model.capture(simultaneous=True)
        differing=[n for n in correct if wrong[n]!=correct[n]]
        if not differing:raise ValueError('Two-phase negative control ineffective')
        victim=next(n for n in sorted(model.rising) if correct[n][0]!=MASK)
        faulty,finfo=model.capture((victim,'D',1))
        if any(row['unknown_sampled'] for row in finfo):raise ValueError('Faulted response is unknown')
        if faulty[victim]==correct[victim]:raise ValueError('D fault not captured')
        result.update(status='pass_capture_model_only',state_bits=len(correct),patterns=64,
            negative_controls={'simultaneous_phase':differing,'D_stuck_high':victim},
            assumptions=['Exact unscanned access state established by this mapped gate-level finite entry trace; existing unbounded public-output proof remains separate',
                'Parked-low entered test protocol; mode1, SE0, test reset inactive and dedicated fixture inputs fixed',
                'No clock/reset/ICG/macro/pad faults; these are separate excluded fault classes',
                'Static digital pad model; electrical and contention qualification remains open'])
        print('PASS two-phase capture model:',len(correct),'FFs, 64 seeded vectors; phase/D faults rejected')
    except Exception as error:
        result['error']=repr(error);raise
    finally:
        result['seconds']=time.monotonic()-start
        (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()

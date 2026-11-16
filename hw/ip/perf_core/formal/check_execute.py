"""Registered execution safety, divider step refinement, deadlines and faults."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'dv/core'))
from common import output_dir, run
from equiv import compare, negatives

TOP = 'ClockedExecuteFormal'


def bind_production(prepared, candidate, out):
    """Strip verification-only cones and prove the remaining actual RTL identical."""
    design = json.loads(prepared.read_text())
    m = design['modules'].pop(TOP)
    design['modules']['ClockedExecute'] = m
    m['ports'].pop('checking')
    m['cells'] = {n:c for n,c in m['cells'].items() if c['type'] not in ('$check','$assert','$cover','$assume')}
    projected = out/'projected.json'; projected.write_text(json.dumps(design))
    paths = []
    for name,read in [('projected',f'read_json {projected}'),
                      ('production','read_slang --top ClockedExecute '+' '.join(str(p) for p in sorted(candidate.glob('*.sv'))))]:
        path = out/(name+'-canonical.json')
        script = out/(name+'.ys')
        script.write_text(read+'\nprep -top ClockedExecute -flatten\nopt -full -nodffe -nosdff\ncheck -assert\n'+f'write_json {path}\n')
        run(['yosys','-Q','-T','-s',script],out,name)
        paths.append(path)
    proof = out/'production-binding'; proof.mkdir(exist_ok=True)
    if compare('ClockedExecute',*paths,proof) != 'proved':
        raise RuntimeError('Formal instrumentation changed production behavior')
    negatives('ClockedExecute',*paths,proof)


def history_driver(path):
    """Real one-bit history register: false initially, unconditionally true next.

    Unlike a delayed init-assumption guard, this remains inductive from every
    state. It replaces only the formal checking port, not any production input.
    """
    design = json.loads(path.read_text())
    m = design['modules'][TOP]
    bits = m['ports'].pop('checking')['bits']
    m['netnames']['checking']['attributes']['init'] = '0'
    m['cells']['__history'] = dict(type='$dff',attributes={},
        parameters=dict(WIDTH=format(1,'032b'),CLK_POLARITY='1'),
        port_directions=dict(CLK='input',D='input',Q='output'),
        connections=dict(CLK=m['ports']['clk_i']['bits'],D=['1'],Q=bits))
    path.write_text(json.dumps(design))


def strengthen(path):
    """Add ASSERTED state correspondence and progress invariants, never assumptions.

    Internal child state is deliberately not a production interface. Named nets
    are selected from elaborated RTL, with widths and flop identity checked.
    """
    design = json.loads(path.read_text())
    m = design['modules'][TOP]
    fresh = max(b for n in m['netnames'].values() for b in n['bits'] if isinstance(b, int)) + 1
    serial = 0
    def net(name, width):
        bits = m['netnames'][name]['bits']
        if len(bits) != width:
            raise ValueError(f'Unexpected width {name}')
        return bits
    def state(name, width):
        bits = net(name, width)
        drivers = [c for c in m['cells'].values() if c['type'] in ('$adff','$aldff') and c['connections']['Q'] == bits]
        if len(drivers) != 1:
            raise ValueError(f'Not a unique async-reset state {name}')
        c = drivers[0]
        reset_ok = (c['connections']['AD'] == ['0']*width and
                    c['connections']['ALOAD'] == net('rst_ni',1) and int(c['parameters']['ALOAD_POLARITY'],2)==0) if c['type']=='$aldff' else (
                    int(c['parameters']['ARST_VALUE'],2)==0 and c['connections']['ARST']==net('rst_ni',1) and int(c['parameters']['ARST_POLARITY'],2)==0)
        if c['connections']['CLK'] != net('clk_i',1) or int(c['parameters']['CLK_POLARITY'],2)!=1 or not reset_ok:
            raise ValueError(f'Unexpected state clock/reset {name}')
        return bits
    def const(n, width=7):
        return list(format(n, f'0{width}b')[::-1])
    def cell(kind, a, b, width=1):
        nonlocal serial, fresh
        serial += 1
        y = list(range(fresh, fresh+width)); fresh += width
        m['cells'][f'__invariant_{serial}'] = dict(type='$'+kind, attributes={},
            parameters={k:format(v,'032b') for k,v in dict(A_SIGNED=0,B_SIGNED=0,A_WIDTH=len(a),B_WIDTH=len(b),Y_WIDTH=width).items()},
            port_directions=dict(A='input',B='input',Y='output'),connections=dict(A=a,B=b,Y=y))
        return y
    def eq(a,b): return cell('eq',a,b)
    def land(a,b): return cell('logic_and',a,b)
    def lor(a,b): return cell('logic_or',a,b)
    enable = land(net('checking',1),net('rst_ni',1))
    def assertion(name, value, guard=const(1,1)):
        m['cells']['__assert_'+name] = dict(type='$assert',attributes={},parameters={},
            port_directions=dict(A='input',EN='input'),connections=dict(A=value,EN=land(enable,guard)))
    for name,width in [('div_counter_q',5),('md_state_q',3),('op_numerator_q',32),('op_quotient_q',32),('div_by_zero_q',1)]:
        assertion('divider_'+name,eq(state('divider.'+name,width),state('reference_divider.'+name,width)))
    phase = net('state_q',3)
    age = net('age',7)
    mulstate = state('multiplier.state_q',3)
    mulcount = state('multiplier.count_q',5)
    divstate = state('divider.md_state_q',3)
    divcount = state('divider.div_counter_q',5)
    phaseis = lambda n: eq(phase,const(n,3))
    mulactive = lor(phaseis(2),phaseis(3))
    divactive = lor(lor(phaseis(4),phaseis(5)),phaseis(6))
    assertion('multiplier_idle',eq(mulstate,const(0,3)),eq(mulactive,const(0,1)))
    assertion('divider_idle',eq(divstate,const(0,3)),eq(divactive,const(0,1)))
    assertion('mul_start',land(eq(age,const(0)),eq(mulstate,const(0,3))),phaseis(2))
    for s in range(1,5):
        expected = cell('add',mulcount,const(1),7) if s==1 else const(31+s)
        assertion('mul_age_'+str(s),eq(age,expected),land(phaseis(3),eq(mulstate,const(s,3))))
    assertion('mul_legal',land(cell('ge',mulstate,const(1,3)),cell('le',mulstate,const(4,3))),phaseis(3))
    # age = 3 * completed divider steps + phase offset.
    offset = cell('sub',phase,const(4,3),7)
    zero_fast = land(eq(net('request_q_b',32),const(0,32)),eq(net('request_q_constantTime',1),const(0,1)))
    for s in range(7):
        steps = cell('sub',const(34),divcount,7) if s==3 else const({0:0,1:1,2:2,4:34,5:35,6:36}.get(s,0))
        expected = cell('add',cell('mul',steps,const(3),7),offset,7)
        guard = land(divactive,eq(divstate,const(s,3)))
        if s==6:
            assertion('div_age_fast',eq(age,cell('add',const(3),offset,7)),land(guard,zero_fast))
            guard = land(guard,eq(zero_fast,const(0,1)))
        assertion('div_age_'+str(s),eq(age,expected),guard)
    assertion('div_legal',cell('le',divstate,const(6,3)),divactive)
    assertion('div_counter',cell('ge',divcount,const(1,5)),land(divactive,eq(divstate,const(3,3))))
    # Zero division takes the fast branch; the other path cannot accidentally
    # become reachable under that condition.
    assertion('div_zero_path',lor(eq(divstate,const(0,3)),eq(divstate,const(6,3))),land(divactive,zero_fast))
    result = path.with_name('strengthened.json')
    result.write_text(json.dumps(design))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--candidate',required=True)
    parser.add_argument('--variant',choices=['all','normal','capture','result','hold','reset','dispatch','feedback','cover'],default='all')
    args = parser.parse_args()
    out = output_dir(args.output)
    receipt = dict(status='running',variant=args.variant,assumptions=['initial rst_ni=0, then unconstrained','checking=0 initially, then 1'])
    receipt['verification_inputs'] = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [Path(__file__),ROOT/'hw/ip/perf_core/formal/ClockedExecuteFormal.scala',
                  ROOT/'dv/core/equiv.py',ROOT/'dv/core/state_equiv.py',ROOT/'tools/env/lock.json']}
    try:
        if args.variant=='all':
            receipt['variants'] = {}
            for variant in ('normal','capture','result','hold','reset','dispatch','feedback','cover'):
                target = out/variant
                run([sys.executable,__file__,'--candidate',args.candidate,'--output',target,'--variant',variant],out,variant,timeout=960)
                receipt['variants'][variant] = json.loads((target/'result.json').read_text())
            receipt['status'] = 'pass'
            print('PASS registered execution: induction, production binding, six rejected faults and eight covers',flush=True)
            return
        run([sys.executable,'tools/env/check.py'],out,'environment')
        emitted = out/'emit'
        run([sys.executable,'tools/sbt.py',
             f'set hw / Compile / unmanagedSources += file("{ROOT}/hw/ip/perf_core/formal/ClockedExecuteFormal.scala")',
             f'hw/runMain deadhorse.perf_core.EmitClockedExecuteFormal {emitted.relative_to(ROOT)} {args.variant}'],out,'emit',timeout=600)
        sources = sorted(emitted.glob('*.sv'))
        receipt['sources'] = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
        script = out/'prepare.ys'
        script.write_text(f'read_slang --top {TOP} '+ ' '.join(map(str,sources))+f'\nprep -top {TOP} -flatten\n'
                          f'write_json {out}/prepared.json\n')
        run(['yosys','-Q','-T','-s',script],out,'prepare')
        prepared = json.loads((out/'prepared.json').read_text())['modules'][TOP]
        inventory = {}
        for cell in prepared['cells'].values():
            if cell['type'] not in ('$check','$assert','$cover','$assume'): continue
            flavor = cell['parameters']['FLAVOR'] if cell['type']=='$check' else cell['type'][1:]
            inventory[flavor] = inventory.get(flavor,0)+1
        receipt['properties'] = inventory
        if inventory != ({'cover':8} if args.variant=='cover' else {'assert':37}):
            raise RuntimeError(f'Unexpected property inventory or hidden assumptions: {inventory}')
        candidate = (ROOT/args.candidate).resolve()
        candidate.relative_to(ROOT/'build')
        receipt['production_sources'] = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(candidate.glob('*.sv'))}
        if args.variant=='normal':
            bind_production(out/'prepared.json',candidate,out)
        history_driver(out/'prepared.json')
        source = strengthen(out/'prepared.json') if args.variant=='normal' else out/'prepared.json'
        mode = 'prove' if args.variant=='normal' else 'cover' if args.variant=='cover' else 'bmc'
        depth = 120 if mode=='cover' else 12
        config = out/'check.sby'
        startup = "fminit -seq rst_ni 0,'z"
        if mode=='cover':
            # Witness search only: one request, no subsequent reset, fixed A,
            # signed operands and B in {0,1}. Kind and constantTime are free;
            # all eight original covers remain required. This trims irrelevant
            # stimulus branching without constraining the safety proof.
            startup = ("fminit -seq rst_ni 0,1 -seq req_valid 0,1,0 -set rsp_ready 0 "
                       "-set req_bits_a 2147483649 -set req_bits_b 32'b0000000000000000000000000000000z "
                       "-set req_bits_signedMode 3 -set req_bits_high 1 -set req_bits_firstCycle 1 -set req_bits_aluOp 0")
            receipt['cover_stimulus'] = startup
        # With the held response all eight witness predicates persist. Search
        # the terminal frame instead of repeatedly solving impossible prefixes;
        # keep the same depth and timeout and retain every original cover.
        skip = 'skip 119\n' if mode=='cover' else ''
        config.write_text(f'[options]\nmode {mode}\ndepth {depth}\n{skip}timeout 300\n\n[engines]\nsmtbmc z3\n\n[script]\n'
            f'read_json {source.name}\nprep -top {TOP}\n{startup}\n'
            f'async2sync\nchformal -lower\ndffunmap\n\n[files]\n{source}\n')
        result = run(['sby','-f','-d',out/'proof',config],out,'proof',allowed=(0,2,16),timeout=330)
        status = (out/'proof/status').read_text().split()[0]
        expected = 'PASS' if args.variant in ('normal','cover') else 'FAIL'
        if status != expected or result.returncode != (0 if expected=='PASS' else 2):
            raise RuntimeError(f'Expected {expected} with matching exit code, got {status}/{result.returncode}')
        if mode != 'prove' and not list((out/'proof/engine_0').glob('trace*.vcd')):
            raise RuntimeError('Missing witness trace')
        receipt.update(status='pass',result='proved' if mode=='prove' else 'covered' if mode=='cover' else 'fault-rejected',depth=depth)
        print(f'PASS registered execution {args.variant}: {receipt["result"]}',flush=True)
    except Exception as exc:
        receipt.update(status='failed',error=str(exc))
        raise
    finally:
        (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__': main()

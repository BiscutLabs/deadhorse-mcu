"""All-state transition/output equivalence of the two T32 mapped core trials."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import time
from timing_iterations import ROOT, TOP, sha, write
from tools.timing.usb_boundary import groups


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    original=ROOT/'build/t32/final-fast03/fast/faithful-floating-timing/mapped.json'
    candidate=args.candidate.resolve()
    lib=ROOT/'build/riscay-mcu/.tools/physical/pdk/gf180mcu_fd_sc_mcu7t5v0__ss_125C_3v00.lib'
    receipt=dict(status='running',commands=[],inputs={str(x):sha(x) for x in (original,candidate,lib,Path(__file__),Path(__file__).with_name('timing_iterations.py'))},
        cap_seconds=120,assumptions=[],scope='Arbitrary top inputs and matched cell-state outputs; compare every state-cell input and original output, preserving literal state-cell identity/types/parameters.')
    def run(cmd,label,expect=None):
        start=time.monotonic()
        try:
            r=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
            log=r.stdout+r.stderr;code=r.returncode
        except subprocess.TimeoutExpired as e:
            (out/(label+'.log')).write_bytes((e.stdout or b'')+(e.stderr or b''));raise
        (out/(label+'.log')).write_text(log)
        receipt['commands'].append(dict(command=cmd,returncode=code,seconds=time.monotonic()-start))
        assert code==0,label
        if expect:assert expect in log,label
        return log
    try:
        a=json.loads(original.read_text())['modules'][TOP]
        b=json.loads(candidate.read_text())['modules'][TOP]
        library=dict(groups(lib.read_text(),'cell'))
        sequential={n for n,body in library.items() if any(list(groups(body,k)) for k in ('ff','latch','ff_bank','latch_bank','statetable'))}
        # ICG is stateful even if a Liberty parser represents its internal latch
        # with specialized attributes. Cut every clocked/ICG cell explicitly.
        def cut_cells(m):
            return {n:c for n,c in m['cells'].items() if c['type'] in sequential or 'CLK' in c['connections'] or '__icgt' in c['type']}
        sa,sb=cut_cells(a),cut_cells(b)
        assert set(sa)==set(sb) and sa
        assert a['ports']==b['ports'],'Changed top port identities'
        for n in sa:
            for k in ('type','parameters','port_directions','attributes'):
                assert sa[n][k]==sb[n][k],(n,k)
            assert set(sa[n]['connections'])==set(sb[n]['connections'])
            assert all(len(bs)==1 for bs in sa[n]['connections'].values())
        assert all(c['type'] in library for m in (a,b) for c in m['cells'].values())
        def cut(m):
            model=copy.deepcopy(m)
            for i,n in enumerate(sorted(sa)):
                c=model['cells'].pop(n)
                for pin,bits in sorted(c['connections'].items()):
                    direction='input' if c['port_directions'][pin]=='output' else 'output'
                    name=f'state_{i:05d}_{pin}'
                    assert name not in model['ports']
                    model['ports'][name]=dict(direction=direction,bits=bits)
            return model
        ca,cb=cut(a),cut(b)
        fault=copy.deepcopy(cb)
        fault_pin=next(n for n in fault['ports'] if n.startswith('state_') and n.endswith('_D'))
        old=fault['ports'][fault_pin]['bits'][0]
        fault['ports'][fault_pin]['bits']=['1' if old=='0' else '0']
        models={'before':ca,'after':cb,'wrong-data':fault}
        for name,model in models.items():
            write(out/(name+'.json'),dict(modules={TOP:model}))
            script=out/(name+'.ys')
            script.write_text(f'read_liberty -ignore_miss_func "{lib}"\nread_json "{out}/{name}.json"\nhierarchy -check -top {TOP}\nflatten\nproc\ntechmap\nopt\ncheck -assert\nwrite_blif "{out}/{name}.blif"\n')
            run(['yosys','-Q','-T','-s',str(script)],name+'-export')
        # Yosys may retain undriven, otherwise-unused aliases in BLIF. ABC
        # defaults those to zero; explicitly expose the identical set instead,
        # so no undefined value becomes an implicit environment constraint.
        undefined={}
        for name in models:
            path=out/(name+'.blif');text=path.read_text().replace('\\\n',' ')
            inputs=set();driven=set();used=set()
            for line in text.splitlines():
                words=line.split()
                if not words or words[0].startswith('#'):continue
                if words[0]=='.inputs':inputs.update(words[1:])
                elif words[0]=='.outputs':used.update(words[1:])
                elif words[0]=='.names':driven.add(words[-1]);used.update(words[1:-1])
                elif words[0].startswith('.'):
                    assert words[0] in ('.model','.end'),words[0]
            undefined[name]=used-driven-inputs
        assert undefined['before']==undefined['after']==undefined['wrong-data']
        for name in models:
            path=out/(name+'.blif');text=path.read_text()
            assert text.count('\n.inputs ')==1
            text=text.replace('\n.inputs ','\n.inputs '+' '.join(sorted(undefined[name]))+' ',1)
            path.write_text(text)
        receipt['arbitrary_undriven_aliases']=sorted(undefined['before'])
        run(['yosys-abc','-c',f'cec -T 120 {out}/before.blif {out}/after.blif'],'equivalence','Networks are equivalent')
        run(['yosys-abc','-c',f'cec -T 120 {out}/before.blif {out}/wrong-data.blif'],'negative','Networks are NOT EQUIVALENT')
        receipt.update(status='pass',matched_state_cells=len(sa),comparison_outputs=sum(len(r['bits']) for r in ca['ports'].values() if r['direction']=='output'),
                       wrong_data_rejected=True,proof_kind='Combinational equivalence for all states, preserving transition/reset/clock/output functions; not the deferred SBA composition proof.')
    except Exception as e:
        receipt.update(status='error',error=repr(e));raise
    finally:
        receipt['artifacts']={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='result.json'}
        write(out/'result.json',receipt);print(receipt['status'],flush=True)


if __name__=='__main__':main()

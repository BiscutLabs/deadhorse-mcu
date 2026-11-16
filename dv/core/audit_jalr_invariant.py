"""Required acceptance audit for the focused JALR lemma's raw proof receipt.

Checks retained inputs and actual active retirement witnesses, and rejects a
wrong-opcode monitor through the independent guard-qualification SAT proof.
Does not repeat any sequential proof or grant aggregate ISA acceptance.
"""
import argparse
import copy
import json
from pathlib import Path

from common import ROOT, local, output_dir, run
from jalr_invariant import TOP, digest


def active_witness(text, fault):
    scope=[];names={};values={};time=0;frames=[]
    wanted=['rvfi_testbench.checker_inst.reset','rvfi_testbench.rvfi_valid',
            'rvfi_testbench.rvfi_insn','rvfi_testbench.rvfi_rs1_addr']
    def sample():
        if not all(n in names and names[n] in values for n in wanted): return
        bits=[values[names[n]] for n in wanted]
        if any(set(b)-set('01') for b in bits): return
        reset,valid,insn,reported=[int(b,2) for b in bits]
        expected=(insn>>15)&31
        if reset==0 and valid==1 and insn&127==0x67 and (insn>>12)&7==0 and expected:
            if (reported!=expected)==fault:
                frames.append(dict(time=time,instruction=hex(insn),expected_rs1=expected,reported_rs1=reported))
    for line in text.splitlines():
        p=line.split()
        if not p: continue
        if p[0]=='$scope': scope.append(p[2])
        elif p[0]=='$upscope': scope.pop()
        elif p[0]=='$var': names['.'.join(scope+[p[4]])]=p[3]
        elif line.startswith('#'): sample();time=int(line[1:])
        elif line[0] in 'bB' and len(p)==2: values[p[1]]=p[0][1:]
        elif line[0] in '01xXzZ': values[line[1:]]=line[0]
    sample()
    if not frames: raise ValueError('No active JALR '+('fault' if fault else 'cover')+' witness')
    return frames[0]


def audit(directory):
    out=output_dir(directory);record=out/'audit.json'
    receipt=dict(status='running',scope='focused JALR address proof only; aggregate ISA incomplete')
    record.write_text(json.dumps(receipt))
    try:
        source=out/'result.json';result=json.loads(source.read_text())
        if result['status']!='pass (lemma and original address partition only)':
            raise ValueError('Raw proof jobs incomplete')
        for role,expected in [('prove','PASS'),('cover','PASS'),('fault','FAIL'),('original-source-address','PASS')]:
            actual=(out/role/'work/status').read_text().split()[0]
            if actual!=expected or result['results'][role]['status']!=expected:
                raise ValueError('Unexpected proof status: '+role)
        hashes=result['input_sha256']
        for path,expected in hashes.items():
            if digest(local(path))!=expected: raise ValueError('Stale proof input: '+path)
        witnesses={}
        for role in ('cover','fault'):
            files=list((out/role/'work').glob('engine_*/trace*.vcd'))
            if not files: raise ValueError('Missing '+role+' witness artifact')
            found=[]
            for path in files:
                try: found.append(dict(path=str(path.relative_to(ROOT)),sha256=digest(path),
                                       retirement=active_witness(path.read_text(),role=='fault')))
                except ValueError: continue
            if not found: raise ValueError('No qualifying active '+role+' trace')
            witnesses[role]=found
        original=json.loads((out/'qualification.json').read_text());bad=copy.deepcopy(original)
        targets=[(n,c) for n,c in bad['modules'][TOP]['cells'].items()
                 if n.startswith('__jalr_monitor_') and c['type']=='$eq' and
                 c['connections'].get('B')==list(reversed(format(0x67,'07b')))]
        if len(targets)!=1: raise ValueError('Monitor opcode fault target not unique')
        name,cell=targets[0];cell['connections']['B'][0]='0'  # JALR opcode 0x67 -> 0x66.
        job=output_dir(out/'qualification-negative');model=job/'model.json';model.write_text(json.dumps(bad))
        witness=job/'counterexample.json';ys=job/'check.ys'
        ys.write_text(f'read_json {model}\ncheck -assert\n'
            'sat -prove active_equal 1 -prove violation_equal 1 -prove assumption_enable_equal 1 '
            f'-show-inputs -show-outputs -dump_json {witness}\n')
        before={str(p):digest(p) for p in (source,out/'qualification.json',model,ys,Path(__file__))}
        observed=run(['yosys','-Q','-T','-s',ys],job,'check',timeout=120)
        if 'SAT proof finished - model found: FAIL!' not in observed.stdout or not witness.is_file() or not witness.stat().st_size:
            raise ValueError('Wrong-opcode monitor escaped qualification')
        for path,expected in {**hashes,**before}.items():
            if digest(local(path))!=expected: raise ValueError('Input changed during audit: '+path)
        receipt.update(status='pass',raw_receipt_sha256=digest(source),witnesses=witnesses,
            qualification_negative=dict(status='rejected',cell=name,mutation='opcode 0x67 -> 0x66',
                seconds=observed.elapsed_seconds,counterexample_sha256=digest(witness)),audit_input_sha256=before)
        print('PASS JALR audit: active cover/fault witnesses verified; wrong-opcode qualification rejected')
    except BaseException as exc:
        receipt.update(status='failed',error=str(exc));raise
    finally: record.write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    audit(parser.parse_args().output)

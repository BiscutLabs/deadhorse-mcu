"""Reassociate mapped parity cones, retaining every original boundary signal."""
import argparse
import copy
import csv
import heapq
import itertools
import json
from pathlib import Path
import re
import subprocess
import sys
import time

from timing_iterations import ROOT, PREFIX, TOP, sha, write
from tools.physical.usb_cells import signature
from tools.timing.usb_boundary import groups
from tools.timing.usb_async import boolean_function
from tools.timing.check import electrical_checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--minimum-depth', type=int, default=4)
    args = ap.parse_args()
    base, out = args.base.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    lib = ROOT/'build/riscay-mcu/.tools/physical/pdk/gf180mcu_fd_sc_mcu7t5v0__ss_125C_3v00.lib'
    receipt = dict(status='running', commands=[], producer_sha256=sha(__file__),
        helper_sha256=sha(Path(__file__).with_name('timing_iterations.py')),
        liberty_sha256=sha(lib), base=str(base),
        revision=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip())
    def run(cmd, label):
        start = time.monotonic()
        with (out/(label+'.log')).open('w') as f:
            code = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT).returncode
        receipt['commands'].append(dict(command=cmd, returncode=code, seconds=time.monotonic()-start))
        assert code == 0, label
    try:
        receipt['inputs'] = {str(p):sha(p) for p in (base/'candidate.json',base/'mapped.v',base/'sta.log',base/'timing.tcl',base/'paths.tsv')}
        data = json.loads((base/'candidate.json').read_text())
        original = data['modules'][TOP]
        library = dict(groups(lib.read_text(), 'cell'))
        parity = {}
        for name, body in library.items():
            match = re.fullmatch(re.escape(PREFIX)+r'(xor[23]|xnor2|inv|buf)_[1-4]', name)
            if not match:
                continue
            sig = signature(body)
            assert not sig['ff']
            ins = sorted(p for p,r in sig['pins'].items() if r['direction']=='input')
            outs = [p for p,r in sig['pins'].items() if r['direction']=='output']
            assert len(outs)==1
            invert = match[1] in ('inv','xnor2')
            for values in itertools.product((False,True), repeat=len(ins)):
                actual = boolean_function(sig['pins'][outs[0]]['function'],dict(zip(ins,values)))
                assert actual == bool((sum(values)+invert)%2)
            parity[name] = (ins,outs[0],invert)
        drivers = {}
        for n,c in original['cells'].items():
            for p,bs in c['connections'].items():
                if c['port_directions'][p]=='output':
                    for b in bs:
                        assert b not in drivers
                        drivers[b]=(n,p)
        protected = {b for c in original['cells'].values() for p,bs in c['connections'].items()
                     if p in ('CLK','CLKN','RN','SETN','E','TE') for b in bs}
        while True:
            prev=set(protected)
            for c in original['cells'].values():
                if any(p in c['connections'] for p in ('CLK','CLKN')):continue
                if any(b in protected for p,bs in c['connections'].items() if c['port_directions'][p]=='output' for b in bs):
                    protected.update(b for p,bs in c['connections'].items() if c['port_directions'][p]=='input' for b in bs)
            if prev==protected:break
        def expand(bit, model, active=None):
            active=set() if active is None else active
            assert bit not in active, 'Parity cycle'
            if bit in ('0','1'):return set(),bit=='1',0
            node=drivers.get(bit)
            if node is None or node[0] not in model['cells']:return {bit},False,0
            c=model['cells'][node[0]]
            if c['type'] not in parity:return {bit},False,0
            ins,op,constant=parity[c['type']]
            leaves=set();depth=0
            for pin in ins:
                terms,inv,d=expand(c['connections'][pin][0],model,active|{bit})
                leaves.symmetric_difference_update(terms);constant^=inv;depth=max(depth,d)
            return leaves,constant,depth+1
        # Measured arrivals from the prior full report; absent leaves use zero.
        arrival={}
        for row in csv.DictReader((base/'paths.tsv').open(),delimiter='\t'):
            for item in row['points'].split('; '):
                pin,value=item.rsplit('@',1)
                name,port=pin.rsplit('/',1) if '/' in pin else ('','')
                if name in original['cells'] and port in original['cells'][name]['connections']:
                    bit=original['cells'][name]['connections'][port][0]
                    arrival[bit]=max(arrival.get(bit,0),float(value))
        critical=set();active=False
        for line in (base/'sta.log').read_text().splitlines():
            if line.startswith('Path Type:'):active=line.strip()=='Path Type: max'
            match=re.match(r'\s*[0-9.]+\s+[0-9.]+\s+[\^v]\s+(\S+)/\S+\s+\(',line)
            if active and match:critical.add(match[1])
        targets={}
        for n in sorted(critical):
            c=original['cells'][n]
            if not re.fullmatch(re.escape(PREFIX)+r'(?:xor[23]|xnor2)_[1-4]',c['type']):continue
            bit=c['connections'][parity[c['type']][1]][0]
            leaves,constant,depth=expand(bit,original)
            if bit not in protected and depth>=args.minimum_depth and len(leaves)>=4:
                targets[n]=(bit,leaves,constant,depth)
        assert targets
        after=copy.deepcopy(original)
        nextbit=1+max(b for r in list(original['ports'].values())+list(original['netnames'].values()) for b in r['bits'] if isinstance(b,int))
        nextbit=max(nextbit,1+max(b for c in original['cells'].values() for bs in c['connections'].values() for b in bs if isinstance(b,int)))
        added=[];details={}
        for name,(target,leaves,constant,depth) in targets.items():
            del after['cells'][name]
            queue=[(arrival.get(b,0),b) for b in sorted(leaves)];heapq.heapify(queue)
            local=[]
            while len(queue)>1:
                ta,a=heapq.heappop(queue);tb,b=heapq.heappop(queue)
                last=not queue
                kind=PREFIX+('xnor2_2' if last and constant else 'xor2_2')
                bit=target if last else nextbit
                if not last:nextbit+=1
                newname='t32_parity_'+str(len(added)).zfill(5)
                ins,op,inv=parity[kind]
                after['cells'][newname]=dict(hide_name=0,type=kind,parameters={},attributes={},
                    port_directions={ins[0]:'input',ins[1]:'input',op:'output'},
                    connections={ins[0]:[a],ins[1]:[b],op:[bit]})
                added.append(newname);local.append(newname)
                # Scheduling heuristic only, not an acceptance constraint.
                heapq.heappush(queue,(max(ta,tb)+1.5,bit))
            details[name]=dict(output=target,leaves=sorted(leaves),constant=constant,
                               prior_depth=depth,added=local)
        # Prove substitutions locally against arbitrary boundary leaves, then
        # require the complete remaining graph and aliases to be unchanged.
        newdrivers={c['connections'][parity[c['type']][1]][0]:(n,parity[c['type']][1])
                    for n,c in after['cells'].items() if c['type'] in parity}
        def local_terms(bit, model, names, seen=None):
            seen=set() if seen is None else seen
            assert bit not in seen,'cycle'
            node=newdrivers.get(bit)
            if node is None or node[0] not in names:return {bit},False
            c=model['cells'][node[0]];ins,op,constant=parity[c['type']];result=set()
            for p in ins:
                terms,inv=local_terms(c['connections'][p][0],model,names,seen|{bit})
                result.symmetric_difference_update(terms);constant^=inv
            return result,constant
        for name,row in details.items():
            assert local_terms(row['output'],after,set(row['added']))==(set(row['leaves']),row['constant'])
        restored=copy.deepcopy(after)
        for n in added:del restored['cells'][n]
        for n in targets:restored['cells'][n]=original['cells'][n]
        assert restored==original
        row=next(iter(details.values()));node=row['added'][-1]
        fault=copy.deepcopy(after);fault['cells'][node]['type']=PREFIX+('xor2_2' if row['constant'] else 'xnor2_2')
        # Pin names differ for xor/xnor; construct the actual changed-polarity cell.
        old_output=parity[after['cells'][node]['type']][1];new_output=parity[fault['cells'][node]['type']][1]
        if old_output!=new_output:
            fault['cells'][node]['connections'][new_output]=fault['cells'][node]['connections'].pop(old_output)
        assert local_terms(row['output'],fault,set(row['added']))!=(set(row['leaves']),row['constant'])
        fault=copy.deepcopy(after);fault['cells'][row['added'][0]]['connections']['A1']=[nextbit]
        assert local_terms(row['output'],fault,set(row['added']))!=(set(row['leaves']),row['constant'])
        data['modules'][TOP]=after;write(out/'candidate.json',data)
        write(out/'transform.json',dict(details=details,added=added,wrong_leaf_rejected=True,
             wrong_polarity_rejected=True,exact_unchanged_remainder=True,
             scheduling_increment_ns_estimated=1.5))
        (out/'export.ys').write_text(f'read_json "{out}/candidate.json"\nhierarchy -check -top {TOP}\ncheck -assert\nstat -liberty "{lib}"\nwrite_verilog -noattr -noexpr "{out}/mapped.v"\n')
        run(['yosys','-Q','-T','-s',str(out/'export.ys')],'export')
        (out/'timing.tcl').write_text((base/'timing.tcl').read_text().replace(str(base),str(out)))
        run(['sta','-no_init','-exit',str(out/'timing.tcl')],'sta')
        log=(out/'sta.log').read_text();assert 'TIMING_COMPLETE' in log and not re.search(r'^Error:',log,re.M)
        rows=list(csv.DictReader((out/'paths.tsv').open(),delimiter='\t'));worst=max(rows,key=lambda r:float(r['delay_ns']))
        classes={k:max((r for r in rows if r['class']==k),key=lambda r:float(r['delay_ns'])) for k in {r['class'] for r in rows}}
        gates=list(csv.DictReader((out/'gate_checks.tsv').open(),delimiter='\t'));assert gates
        electrical=electrical_checks(log)
        areas={n:float(re.search(r'\barea\s*:\s*([0-9.]+)',body)[1]) for n,body in library.items() if re.search(r'\barea\s*:',body)}
        delta=sum(areas[after['cells'][n]['type']] for n in added)-sum(areas[original['cells'][n]['type']] for n in targets)
        budget=.6*1000/9;gate=min(float(g['slack_ns']) for g in gates)
        receipt.update(status='pass' if float(worst['delay_ns'])<=budget and electrical['max_capacitance_and_slew_violations']==0 and gate>=0 else 'fail',
            worst=worst,classes=classes,budget_ns=budget,gate_min_slack_ns=gate,electrical=electrical,area_delta_um2=delta,
            targets=len(targets),added=len(added),qualification='Mapped pre-layout diagnostic only; no RTL or acceptance constraint changes.')
    except Exception as error:
        receipt.update(status='error',error=repr(error));raise
    finally:
        receipt['artifacts']={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='result.json'}
        write(out/'result.json',receipt)
        print(json.dumps({k:receipt.get(k) for k in ('status','targets','added','area_delta_um2','error')}),flush=True)


if __name__=='__main__':main()

"""Bind physical implementation to the authenticated T37 inserted graph.

OpenROAD Python only. Build a preservation baseline, or audit a placed/CTS ODB.
No timing qualification is performed here.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
import time

import odb

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).parent))
import chip_inspect
from scan_cells import without_test_cell
from scan_probe import snapshot
from scan_capture import sha


def logical(n):return n.replace(r'\[','[').replace(r'\]',']')


def export(block, constants):
    cells={};unconnected=[]
    for inst in block.getInsts():
        pins={};directions={};name=logical(inst.getName())
        for term in inst.getITerms():
            if str(term.getMTerm().getSigType()) in ('POWER','GROUND'):continue
            pin=term.getMTerm().getName();net=term.getNet()
            if net is None:unconnected.append([name,pin]);continue
            pins[pin]=[constants.get(net.getName(),net.getName())];directions[pin]=str(term.getMTerm().getIoType()).lower()
        cells[name]=dict(type=inst.getMaster().getName(),connections=pins,port_directions=directions)
    ports={logical(p.getName()):dict(bits=[constants.get(p.getNet().getName(),p.getNet().getName())],direction=str(p.getIoType()).lower())
        for p in block.getBTerms() if str(p.getSigType()) not in ('POWER','GROUND')}
    return dict(cells=cells,ports=ports),unconnected


def power(block):
    count=0
    for name in ('VDD','DVDD','VSS','DVSS'):
        term=block.findBTerm(name);rail='VDD' if name in ('VDD','DVDD') else 'VSS'
        kind='POWER' if rail=='VDD' else 'GROUND'
        if term is None or term.getNet() is None or term.getNet().getName()!=rail or str(term.getSigType())!=kind:
            raise ValueError('Wrong package supply '+name)
    for inst in block.getInsts():
        for term in inst.getITerms():
            kind=str(term.getMTerm().getSigType())
            if kind not in ('POWER','GROUND'):continue
            net=term.getNet();expected='VDD' if kind=='POWER' else 'VSS'
            if net is None or net.getName()!=expected or str(net.getSigType())!=kind:
                raise ValueError('Wrong physical supply '+inst.getName()+'/'+term.getMTerm().getName())
            count+=1
    return count


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--baseline',type=Path);p.add_argument('--insert',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    state=json.loads(a.state.read_text());source=Path(state['odb'])
    db=odb.dbDatabase.create();odb.read_db(db,str(source));block=db.getChip().getBlock()
    ins=json.loads((a.insert/'result.json').read_text())
    if ins['status']!='pass_unplaced_insertion':raise ValueError('Unqualified insertion')
    result=dict(status='error',input_sha256={str(q):sha(q) for q in (a.state,source,a.insert/'result.json')},
        source_sha256={str(q):sha(q) for q in (Path(__file__),ROOT/'tools/physical/chip_inspect.py',ROOT/'tools/physical/scan_cells.py',ROOT/'tools/physical/usb_cells.py')})
    if a.baseline is None:
        # This source is the existing supply normalization of insert05.
        normal=json.loads((a.state.parent/'result.json').read_text())
        if normal['status']!='pass':raise ValueError('No power-normalization premise')
        old=json.loads((a.insert/'after.json').read_text());now=snapshot(block)
        if sha(a.insert/'after.json')!=ins['artifacts']['after.json']:raise ValueError('Changed inserted graph')
        if set(old)!=set(now) or any(old[n]['type']!=now[n]['type'] or old[n]['pins']!=now[n]['pins'] for n in old):
            raise ValueError('Normalization changed signal graph')
        design,unconnected=export(block,{ins['controls']['zero']:'0',ins['controls']['one']:'1'})
        (a.output/'physical.json').write_text(json.dumps(dict(modules={'chip_top':design})))
        result.update(status='pass',unconnected=unconnected,
            artifact_sha256={'physical.json':sha(a.output/'physical.json')},power_pins=power(block))
    else:
        premise=json.loads((a.baseline/'result.json').read_text());mapped=a.baseline/'physical.json'
        if premise['status']!='pass' or sha(mapped)!=premise['artifact_sha256']['physical.json']:raise ValueError('Unbound baseline')
        result['input_sha256'].update({str(q):sha(q) for q in (mapped,a.baseline/'result.json')})
        design=json.loads(mapped.read_text())['modules']['chip_top']
        actual={logical(i.getName()):i for i in block.getInsts()}
        for n,pin in premise['unconnected']:
            if actual[n].findITerm(pin).getNet() is not None:raise ValueError('Formerly unconnected pin changed')
        audit=chip_inspect.inspect(design,block)
        # scan Liberty contains nested test_cell groups. The ordinary cell's
        # pins and FF relation are the authority, as in scan_cells qualification.
        original_signature=chip_inspect.signature
        chip_inspect.signature=lambda body:original_signature(without_test_cell(body))
        pairs={(r['old'],r['new']) for r in audit['replacements'].values()}
        buffers=[kind for kind in audit['added_cells'] if any('__'+f+'_' in kind for f in ('buf','clkbuf','inv','clkinv','dlyb'))]
        result['library_sha256']=chip_inspect.qualify_sizes(pairs,False,buffers)
        # Actual pin mutations must break correspondence, including scan order.
        victim=next(i for i in block.getInsts() if '__sdff' in i.getMaster().getName())
        controls=[]
        for label in ('D','SI','CLK'):
            term=victim.findITerm(label);old=term.getNet();other=victim.findITerm('Q').getNet()
            prior=victim.isDoNotTouch();victim.setDoNotTouch(False);term.connect(other)
            try:chip_inspect.inspect(design,block)
            except AssertionError:controls.append(label)
            else:raise ValueError('Changed physical pin accepted '+label)
            finally:term.connect(old);victim.setDoNotTouch(prior)
        supply=block.findBTerm('DVDD');old_type=str(supply.getSigType())
        supply.setSigType('SIGNAL')
        try:power(block)
        except ValueError:controls.append('supply-boundary-type')
        else:raise ValueError('Wrong supply boundary type accepted')
        finally:supply.setSigType(old_type)
        clocks=Counter()
        for name,c in design['cells'].items():
            if '__sdff' in c['type'] or '__dff' in c['type']:
                pin='CLKN' if 'CLKN' in c['connections'] else 'CLK'
                clocks[c['connections'][pin][0]]+=1
        result.update(status='pass_preserved_physical_graph',graph=audit,power_pins=power(block),
            negative_controls=controls,clock_sink_groups=dict(clocks),clock_sinks=sum(clocks.values()),
            scope='All original pin roots/polarities and scan order retained through qualified physical buffers/drive variants; composes with insertion mode certificates. Timing not qualified.')
        added=[]
        for name,inst in actual.items():
            if name in design['cells']:continue
            for term in inst.getITerms():
                if str(term.getMTerm().getSigType()) not in ('POWER','GROUND'):
                    added.append(dict(cell=name,pin=term.getMTerm().getName(),type=inst.getMaster().getName(),
                        status='unresolved_new_physical_site',faults=['SA0','SA1']))
        (a.output/'added-fault-sites.json').write_text(json.dumps(added))
        result['added_physical_SA_faults']=2*len(added)
        result['added_fault_inventory_sha256']=sha(a.output/'added-fault-sites.json')
        control_trees={}
        roots={k:ins['controls'][k] for k in ('mode','enable','reset_n','osc')}
        roots['scan_enable']=next(c['connections']['Z'][0] for n,c in design['cells'].items() if n=='_t37_scan_enable')
        for label,bit in roots.items():
            drivers=[(n,p) for n,c in design['cells'].items() for p,bits in c['connections'].items()
                if bits==[bit] and c['port_directions'][p]=='output']
            if len(drivers)!=1:raise ValueError('Ambiguous control root '+label)
            name,pin=drivers[0];todo=[actual[name].findITerm(pin).getNet()];seen=set();buffers=set();maximum=0;loads=0
            while todo:
                net=todo.pop()
                if net.getName() in seen:continue
                seen.add(net.getName());inputs=[t for t in net.getITerms() if str(t.getMTerm().getIoType())=='INPUT']
                maximum=max(maximum,len(inputs))
                for t in inputs:
                    inst=t.getInst();kind=inst.getMaster().getName()
                    if t.getMTerm().getName()=='I' and re.fullmatch(r'gf180mcu_fd_sc_mcu7t5v0__(?:buf|clkbuf|inv|clkinv|dlyb)_\d+',kind):
                        buffers.add(inst.getName());outpin='ZN' if 'inv_' in kind else 'Z';n=inst.findITerm(outpin).getNet()
                        if n is not None:todo.append(n)
                    else:loads+=1
            control_trees[label]=dict(root=name+'/'+pin,buffers=len(buffers),leaf_loads=loads,max_branch_fanout=maximum)
        result['control_segments']=control_trees
        result['control_segment_scope']='Root through buffers/inverters to first other logic; not complete clock-path timing coverage'
    result['seconds']=time.monotonic()-start
    (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(result['status'],result['seconds'])


if __name__=='__main__':main()

"""Exact assertion partitioning: other assertions are removed, never assumed."""
import copy
import hashlib
import json
from pathlib import Path

TOP='rvfi_testbench'

def assertions(design):
    if set(design['modules'])!={TOP}: raise ValueError('Partition only a flattened checker')
    cells=design['modules'][TOP]['cells']
    if any(cell['type']=='$check' and cell['parameters'].get('FLAVOR') not in ('assert','assume','cover')
           or cell['type'] in ('$live','$fair') for cell in cells.values()):
        raise ValueError('Unsupported property form in instruction checker')
    names=sorted(name for name,cell in cells.items() if cell['type']=='$assert' or
                 cell['type']=='$check' and cell['parameters'].get('FLAVOR')=='assert')
    if not names: raise ValueError('No assertions to partition')
    return names

def validate_partition(original,partition,selected):
    inventory=set(assertions(original));chosen=set(selected)
    if not chosen or len(chosen)!=len(selected) or not chosen<=inventory:
        raise ValueError('Empty, duplicate or unknown assertion selection')
    # Check every non-assertion byte of the model, including all assumptions,
    # state, clocks, inputs and source attributes; no rewritten peer assertion.
    expected=copy.deepcopy(original)
    for name in inventory-chosen: del expected['modules'][TOP]['cells'][name]
    if partition!=expected: raise ValueError('Partition changed more than unselected assertions')

def partition(original,selected):
    result=copy.deepcopy(original);chosen=set(selected)
    for name in set(assertions(original))-chosen: del result['modules'][TOP]['cells'][name]
    validate_partition(original,result,selected)
    return result

def validate_union(inventory,groups):
    flat=[name for group in groups for name in group]
    if len(flat)!=len(set(flat)) or set(flat)!=set(inventory) or any(not group for group in groups):
        raise ValueError('Partition inventory has missing, duplicate or unexpected assertions')

def stabilize_generated_names(original):
    # Reloading JSON restarts Yosys's automatic-ID counter. Later setundef
    # would collide with these already-created arbitrary-input cells. Rename
    # only their private cell identifiers; every connection/parameter survives.
    result=copy.deepcopy(original);cells=result['modules'][TOP]['cells'];mapping={}
    occupied=set(cells)|set(result['modules'][TOP]['netnames'])|set(result['modules'][TOP]['ports'])
    for index,name in enumerate(sorted(cells)):
        if not name.startswith('$auto$setundef.'): continue
        stable=f'__t13_snapshot_any_{index}'
        if stable in occupied: raise ValueError('Snapshot-name collision')
        mapping[name]=stable;cells[stable]=cells.pop(name)
    restored=copy.deepcopy(result);back=restored['modules'][TOP]['cells']
    for old,new in mapping.items(): back[old]=back.pop(new)
    if restored!=original: raise ValueError('Snapshot naming changed model semantics')
    return result,mapping


def run_split(directory,source,depth,timeout,prove,run,status):
    directory.mkdir(parents=True,exist_ok=True)
    receipt=dict(status='running',depth=depth,timeout_seconds=timeout,results=[],
                 semantics='same startup-window checker; no peer assertions assumed')
    record=directory/'partitions.json';record.write_text(json.dumps(receipt)+'\n')
    try:
        prepared=directory/'complete.json';raw=directory/'raw.json';script=directory/'prepare.ys'
        script.write_text(source+f'\nwrite_json {raw}\n')
        run(['yosys','-Q','-T','-s',script],directory,'prepare',timeout=120)
        original,renames=stabilize_generated_names(json.loads(raw.read_text()))
        prepared.write_text(json.dumps(original))
        inventory=assertions(original)
        groups=[[name] for name in inventory];validate_union(inventory,groups)
        receipt.update(raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),renamed_generated_cells=renames,model_sha256=hashlib.sha256(prepared.read_bytes()).hexdigest(),
            preparation_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
            assertions={name:original['modules'][TOP]['cells'][name] for name in inventory},groups=groups)
        record.write_text(json.dumps(receipt,indent=2)+'\n')
        # Fail fast. Never queue an ISA-wide sweep or run later partitions after
        # an unresolved obligation. Existing covers/faults remain later gates.
        for index,group in enumerate(groups):
            job=directory/f'part-{index:02d}';job.mkdir(exist_ok=True)
            model=job/'model.json';model.write_text(json.dumps(partition(original,group)))
            config=job/'check.sby';mode='prove' if prove else 'bmc'
            config.write_text(f'[options]\nmode {mode}\ndepth {depth}\nmulticlock on\ntimeout {timeout}\n'
                '[engines]\n'+('abc pdr' if prove else 'btor btormc')+'\n[script]\n'+
                f'read_json {model}\nopt_clean\n')
            hashes={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (raw,prepared,script,model,config)}
            result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=timeout+30)
            if any(hashlib.sha256(p.read_bytes()).hexdigest()!=digest for p,digest in hashes.items()):
                raise ValueError('Proof inputs changed during partition execution')
            observed=(job/'work/status').read_text().split()[0]
            receipt['results'].append(dict(assertions=group,status=observed,
                model_sha256=hashes[model],
                config_sha256=hashes[config],seconds=result.elapsed_seconds))
            record.write_text(json.dumps(receipt,indent=2)+'\n')
            if status(job/'work',result.returncode)!='PASS': raise RuntimeError('Assertion partition failed: '+group[0])
            print(f'PASS assertion partition {index+1}/{len(groups)}',flush=True)
        validate_union(inventory,[r['assertions'] for r in receipt['results']])
        receipt['status']='pass'
        return 'PASS'
    except BaseException as exc:
        receipt.update(status='failed',error=str(exc));raise
    finally: record.write_text(json.dumps(receipt,indent=2)+'\n')

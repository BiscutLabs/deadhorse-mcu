"""Rebind existing local formal receipts to fresh T41 emission, without assumptions.

Byte-identical models need no solver. Otherwise compare every state transition,
clock/reset/control/init and every property predicate/enable by one-step induction.
This does not establish the production gated-main DMI reset composition.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'dv/core'))
from state_equiv import prepare

CASES={
    'owner':('build/t41/boot-control-proof01','owner/emit','BootOwnerFormal',('correct','owner','cover'),'result.json'),
    'dmi':('build/t41/dmi-proof01','emit','DebugTransportFormal',('correct','corrupt','stale','cover'),'result.json'),
    'epoch':('build/t41/epoch-proof02','emit','CdcEpochFormal',('correct','early','delayed','corrupt','cover'),'qualification.json'),
    'divider':('build/plan04/divider-formal03','emit','DividerFormal',('correct','fault'),'result.json'),
    'power':('build/t33/power-reset-formal02','emit','PowerResetFormal',('selector','selector-fault'),'result.json'),
    'reset_demand':('build/t33/power-reset-formal02','emit','ResetDemandFormal',('demand','demand-fault'),'result.json'),
}
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emission',required=True)
    parser.add_argument('--output',required=True)
    producer=parser.add_mutually_exclusive_group(required=True)
    producer.add_argument('--emit',action='store_true',
        help='Produce fresh models with sealed source/configuration inputs before comparing')
    producer.add_argument('--reuse-emission',help='Reuse a hash-bound successful emission from a prior comparison receipt')
    parser.add_argument('--aliases',help='JSON case -> exact gold net name -> candidate net name')
    a=parser.parse_args()
    out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    fresh=(ROOT/a.emission).resolve();fresh.relative_to(ROOT/'build')
    assert fresh.exists() if a.reuse_emission else not fresh.exists()
    aliases=json.loads((ROOT/a.aliases).read_text(encoding='utf-8')) if a.aliases else {}
    receipt=dict(status='running',cases={},commands=[],source_sha256={},input_sha256={},
        scope='Local/default formal-model correspondence only; no production DMI composition claim',
        assumptions=[])
    for p in (Path(__file__),ROOT/'dv/core/state_equiv.py',ROOT/'tools/env/lock.json'):
        receipt['source_sha256'][p.relative_to(ROOT).as_posix()]=digest(p)
    if a.aliases:receipt['source_sha256'][a.aliases]=digest(ROOT/a.aliases)
    files=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
    emission_sources=[ROOT/p for p in files if (p.startswith('hw/') and p.endswith('.scala')
        and '/src/test/' not in p) or p.startswith('project/')]
    emission_sources += [ROOT/p for p in ('build.sbt','tools/sbt.py','tools/formal.py','tools/env/lock.json',
        'build/t28/boot_control/boot_control_regs.json')]
    for p in emission_sources:receipt['source_sha256'][p.relative_to(ROOT).as_posix()]=digest(p)

    def run(lines,path,negative=False):
        script=path.with_suffix('.ys');script.write_text('\n'.join(lines)+'\n',encoding='utf-8')
        start=time.monotonic()
        with path.with_suffix('.log').open('w',encoding='utf-8') as log:
            result=subprocess.run(['yosys','-Q','-T','-s',str(script)],cwd=ROOT,stdout=log,
                stderr=subprocess.STDOUT,timeout=120)
        receipt['commands'].append(dict(script=script.relative_to(out).as_posix(),
            returncode=result.returncode,seconds=time.monotonic()-start))
        log=path.with_suffix('.log').read_text(encoding='utf-8')
        if negative:assert result.returncode and 'proof did fail' in log,'Intended property fault not rejected'
        else:assert result.returncode==0,(path,log[-2000:])

    def expose(design,top):
        m=design['modules'][top];properties={}
        for name,c in list(m['cells'].items()):
            if c['type'] in ('$check','$assert','$assume','$cover'):
                assert {'A','EN'}<=set(c['connections']),(name,c)
                assert all(v=='input' for v in c['port_directions'].values()),(name,c)
                assert len(c['connections']['A'])==len(c['connections']['EN'])==1
                # Raw edge-triggered $check is deliberately not lowered: match
                # its complete parameter/trigger interface, including polarity.
                # This preserves clock semantics without async2sync.
                properties[name]=dict(type=c['type'],parameters=c['parameters'],
                    directions=c['port_directions'],widths={p:len(b) for p,b in c['connections'].items()})
                for pin,bits in c['connections'].items():
                    if not bits:continue
                    port='__property_'+name+'_'+pin
                    assert port not in m['ports']
                    m['ports'][port]=dict(direction='output',bits=bits)
                del m['cells'][name]
            elif c['type'] in ('$live','$fair','$anyseq','$anyconst','$allseq','$allconst'):
                raise ValueError('Unhandled formal/nondeterministic cell '+name)
        assert properties,'No properties found'
        return properties

    try:
        commands=['python','tools/sbt.py',
            'set hw / Compile / unmanagedSourceDirectories ++= Seq(file("/work/hw/ip/boot_control/formal"), file("/work/hw/ip/debug/formal"), file("/work/hw/lib/formal"), file("/work/hw/ip/osc_ctrl/formal"), file("/work/hw/ip/power_reset/formal"))',
            f'hw/runMain deadhorse.boot_control.EmitBootOwnerFormal {fresh}/owner',
            f'hw/runMain deadhorse.debug.EmitDebugTransportFormal {fresh}/dmi',
            f'hw/runMain deadhorse.lib.EmitCdcEpochFormal {fresh}/epoch',
            f'hw/runMain deadhorse.osc_ctrl.EmitDividerFormal {fresh}/divider',
            f'hw/runMain deadhorse.power_reset.EmitPowerResetFormal unused {fresh}/power']
        if a.reuse_emission:
            previous=ROOT/a.reuse_emission;bound=json.loads(previous.read_text(encoding='utf-8'))
            assert bound['emission']['returncode']==0 and bound['emission']['command']==commands
            for p in emission_sources:
                assert bound['source_sha256'][p.relative_to(ROOT).as_posix()]==digest(p),(p,'Emission source changed')
            actual={p.relative_to(ROOT).as_posix():digest(p) for p in fresh.rglob('*.sv')}
            assert actual==bound['emission_sha256'],'Emitted models changed'
            receipt['input_sha256'][a.reuse_emission]=digest(previous)
            receipt['emission']=bound['emission']
            receipt['emission_reused_from']=a.reuse_emission
        else:
            start=time.monotonic()
            with (out/'emit.log').open('w',encoding='utf-8') as log:
                code=subprocess.run(commands,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=180).returncode
            receipt['emission']=dict(command=commands,returncode=code,seconds=time.monotonic()-start)
            assert code==0,'Fresh emission failed'
        receipt['emission_sha256']={p.relative_to(ROOT).as_posix():digest(p) for p in fresh.rglob('*.sv')}
        receipt['input_sha256'].update(receipt['emission_sha256'])
        for case,(prior,sub,top,variants,receipt_name) in CASES.items():
            oldroot=ROOT/prior;reference=oldroot/receipt_name
            oldreceipt=json.loads(reference.read_text(encoding='utf-8'))
            assert oldreceipt['status']=='pass',(case,'Historical proof not PASS')
            evidence=oldreceipt.get('artifact_sha256',oldreceipt.get('qualification_sha256',{}))
            if 'base_receipt' in oldreceipt:
                base=(oldroot/oldreceipt['base_receipt']).resolve();base.relative_to(oldroot)
                assert evidence[base.relative_to(ROOT).as_posix()]==digest(base),'Qualified base receipt changed'
                base_record=json.loads(base.read_text(encoding='utf-8'))
                evidence=base_record['artifact_sha256'] | evidence
                receipt['input_sha256'][base.relative_to(ROOT).as_posix()]=digest(base)
            row=dict(prior_receipt=reference.relative_to(ROOT).as_posix(),prior_sha256=digest(reference),variants={})
            receipt['input_sha256'][reference.relative_to(ROOT).as_posix()]=digest(reference)
            # Preserve the exact proof initialization/lowering recipes. They
            # are not assumptions in this stronger unconditional comparison.
            for key,value in evidence.items():
                if key.endswith('.sby'):
                    p=ROOT/key if key.startswith('build/') else oldroot/key
                    assert digest(p)==value,(p,'Archived proof recipe changed')
                    receipt['input_sha256'][p.relative_to(ROOT).as_posix()]=value
            receipt['cases'][case]=row
            for variant in variants:
                goldfiles={p.name:p for p in (oldroot/sub/variant).glob('*.sv')}
                emission_case='power' if case=='reset_demand' else case
                newfiles={p.name:p for p in (fresh/emission_case/variant).glob('*.sv')}
                assert goldfiles and newfiles,(case,variant,'Missing emission')
                for p in goldfiles.values():
                    recorded=evidence.get(p.relative_to(oldroot).as_posix(),evidence.get(p.relative_to(ROOT).as_posix()))
                    assert recorded==digest(p),(p,'Archived model hash mismatch')
                vrow=dict(gold_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in goldfiles.values()},
                          candidate_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in newfiles.values()})
                row['variants'][variant]=vrow
                receipt['input_sha256'].update(vrow['gold_sha256'])
                receipt['input_sha256'].update(vrow['candidate_sha256'])
                if {n:digest(p) for n,p in goldfiles.items()}=={n:digest(p) for n,p in newfiles.items()}:
                    vrow['status']='byte_identical';continue
                work=out/case/variant;work.mkdir(parents=True)
                properties=[]
                for role,files in [('gold',goldfiles),('candidate',newfiles)]:
                    dest=work/(role+'.json')
                    run([f'read_slang --top {top} '+' '.join(str(files[n]) for n in sorted(files)),
                        f'prep -top {top} -flatten','memory_map','opt_clean',
                        f'write_json {dest}'],work/(role+'-prepare'))
                    design=json.loads(dest.read_text(encoding='utf-8'))
                    properties.append(expose(design,top))
                    dest.write_text(json.dumps(design),encoding='utf-8')
                assert properties[0]==properties[1],(case,variant,'Property kind/identity differs')
                vrow['properties']=properties[0]

                def prove(candidate,directory,negative=False):
                    directory.mkdir()
                    g,c,record=prepare(work/'gold.json',candidate,top,directory,aliases.get(case,{}))
                    run([f'read_json {g}',f'rename {top} gold',f'read_json {c}',f'rename {top} gate',
                        'miter -equiv -flatten gold gate miter','hierarchy -top miter','opt_expr','opt_clean',
                        'sat -verify -prove trigger 0 -show-inputs -show-outputs'],directory/'compare',negative)
                    return record

                vrow['correspondence']=prove(work/'candidate.json',work/'positive')
                bad=json.loads((work/'candidate.json').read_text(encoding='utf-8'));m=bad['modules'][top]
                pin='__property_'+sorted(properties[0])[0]+'_A'
                used=[b for c in m['cells'].values() for bs in c['connections'].values() for b in bs]
                used += [b for group in ('ports','netnames') for n in m[group].values() for b in n['bits']]
                bit=1+max(b for b in used if isinstance(b,int))
                m['cells']['property_fault']=dict(type='$not',parameters=dict(A_SIGNED=0,A_WIDTH=1,Y_WIDTH=1),
                    attributes={},port_directions=dict(A='input',Y='output'),connections=dict(A=m['ports'][pin]['bits'],Y=[bit]))
                m['ports'][pin]['bits']=[bit]
                fault=work/'fault.json';fault.write_text(json.dumps(bad),encoding='utf-8')
                prove(fault,work/'negative',True)
                vrow.update(status='proved_one_step',negative='Exposed property predicate inverted; mismatch rejected')
            print(case,'PASS',flush=True)
        for hashes in (receipt['source_sha256'],receipt['input_sha256']):
            for name,value in hashes.items():assert digest(ROOT/name)==value,('Input changed during run',name)
        receipt['status']='pass'
    except Exception as e:receipt.update(status='failed',error=str(e));print(str(e),flush=True)
    receipt['artifact_sha256']={p.relative_to(out).as_posix():digest(p) for p in out.rglob('*') if p.is_file()}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return receipt['status']!='pass'


if __name__=='__main__':sys.exit(main())

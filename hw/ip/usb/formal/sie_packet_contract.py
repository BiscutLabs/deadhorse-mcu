"""Check the real SIE/engine packet producer, without cutpoints or assumptions."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from packet_decompose import ROOT, digest, execute, save
from packet_partition import lemma_job, selected_model
from packet_receipt import checked_job


def run(output):
    output=output.resolve();output.relative_to(ROOT/'build');output.mkdir(parents=True,exist_ok=False)
    sources=list((ROOT/'hw/ip/usb/src/main').rglob('*.scala'))
    sources += [ROOT/'hw/ip/usb/formal/UsbSiePacketContract.scala',ROOT/'hw/lib/src/main/scala/deadhorse/lib/Cdc.scala',
                Path(__file__),Path(__file__).with_name('packet_partition.py'),Path(__file__).with_name('packet_decompose.py'),
                ROOT/'tools/formal.py', ROOT/'build.sbt']
    sources += [p for p in (ROOT/'hw/vendor/usb').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    bound={str(p.relative_to(ROOT)):digest(p) for p in sources}
    receipt=dict(status='running',source_sha256=bound,jobs=[],assumptions='Initial reset; all later resets and inputs arbitrary.',
                 cutpoints=[],ci='not run by user instruction',
                 commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip())
    (output/'runner.py').write_bytes(Path(__file__).read_bytes());save(output/'result.json',receipt)
    try:
        command=[sys.executable,'tools/sbt.py',f'runMain deadhorse.usb.EmitUsbSiePacketContract {output}/emit']
        execute(command,output/'emit.log',600).check_returncode();receipt['emission_command']=command
        hdl=sorted((output/'emit').glob('*.sv'))+sorted((output/'emit').glob('*.v'))
        receipt['emitted_sha256']={str(p):digest(p) for p in hdl}
        top='UsbSiePacketContract';canonical=output/'canonical.json';script=output/'prepare.ys'
        script.write_text('\n'.join(['read_slang --top '+top+' '+' '.join(map(str,hdl)),
            f'prep -top {top} -flatten',"fminit -seq reset_n 0,'z",'async2sync','chformal -lower',
            'select -assert-count 4 t:$assert',f'write_json {canonical}'])+'\n')
        execute(['yosys','-Q','-T','-s',script],output/'prepare.log').check_returncode()
        model=json.loads(canonical.read_text());receipt['canonical_sha256']=digest(canonical)
        assertions={n for n,c in model['modules'][top]['cells'].items() if c['type']=='$assert'}
        for label,names in [('routing',assertions-{'assert__chisel3_builtin_1'}),
                            ('valid-read',{'assert__chisel3_builtin_1'})]:
            job=lemma_job(output/label,model,top,names,engine='abc pdr\nsmtbmc z3')
            receipt['jobs'].append(dict(property=label,positive=job));save(output/'result.json',receipt)
            print(label,job['solver_status'],flush=True)
        # A successful safety proof alone is not a complete acceptance receipt:
        # real traffic witnesses and a reachable planted fault remain mandatory.
        receipt['status']='safety-proved' if all(j['positive']['result']=='proved' for j in receipt['jobs']) else 'unresolved'
    except Exception as error:receipt.update(status='failed',error=str(error))
    finally:
        if any(digest(ROOT/p)!=h for p,h in bound.items()):receipt.update(status='failed',error='Sources changed during proof')
        if any(digest(p)!=h for p,h in receipt.get('emitted_sha256',{}).items()):
            receipt.update(status='failed',error='Emitted source changed')
        if receipt.get('canonical_sha256') and digest(output/'canonical.json')!=receipt['canonical_sha256']:
            receipt.update(status='failed',error='Canonical model changed')
        save(output/'result.json',receipt)
    return receipt


def bind_wrapper(output, proof, regmap, simulate=False):
    """Bind the proved engine interface to the freshly emitted USB wrapper."""
    output=output.resolve();output.relative_to(ROOT/'build');output.mkdir(parents=True,exist_ok=False)
    prior=json.loads(proof.read_text());receipt=dict(status='running',proof_sha256=digest(proof),bindings={},
        binder_sha256=digest(Path(__file__)))
    bound={p:digest(ROOT/p) for p in prior['source_sha256']}
    bound[str(regmap.resolve().relative_to(ROOT))]=digest(regmap)
    for name in ('UsbSieCompositionSpec.scala','UsbWireHost.scala'):
        path=ROOT/'hw/ip/usb/src/test/scala/deadhorse/usb'/name;bound[str(path.relative_to(ROOT))]=digest(path)
    receipt['current_source_sha256']=bound
    try:
        if prior['status']!='safety-proved':raise ValueError('Missing SIE safety proof')
        for p,h in prior['source_sha256'].items():
            path=proof.parent/'runner.py' if p==str(Path(__file__).relative_to(ROOT)) else ROOT/p
            if digest(path)!=h:raise ValueError('Changed engine proof input: '+p)
        for path,h in prior['emitted_sha256'].items():
            if digest(path)!=h:raise ValueError('Changed SIE proof emission')
        canonical=proof.parent/'canonical.json'
        if digest(canonical)!=prior['canonical_sha256']:raise ValueError('Changed SIE canonical')
        model=json.loads(canonical.read_text());top='UsbSiePacketContract'
        expected={'routing':{'assert__chisel3_builtin','assert__chisel3_builtin_0','assert__chisel3_builtin_2'},
                  'valid-read':{'assert__chisel3_builtin_1'}}
        if len(prior['jobs'])!=2 or {j['property'] for j in prior['jobs']}!=set(expected):
            raise ValueError('Wrong SIE proof inventory')
        for job in prior['jobs']:
            if checked_job(job['positive'],'proof')!=selected_model(model,top,expected[job['property']],set()):
                raise ValueError('SIE solver changed transition system or assumptions')
        command=[sys.executable,'tools/sbt.py',f'runMain deadhorse.usb.EmitUsb {output}/emit {regmap.resolve()}']
        execute(command,output/'emit.log',600).check_returncode();receipt['emission_command']=command
        hdl=sorted((output/'emit/usb').glob('*.sv'))+sorted((output/'emit/usb').glob('*.v'))
        receipt['emitted_sha256']={str(p):digest(p) for p in hdl};receipt['regmap_sha256']=digest(regmap)
        script=output/'prepare.ys';modelpath=output/'wrapper.json'
        script.write_text('\n'.join(['read_slang --top Usb '+' '.join(map(str,hdl)),
            'prep -top Usb -flatten',f'write_json {modelpath}'])+'\n')
        execute(['yosys','-Q','-T','-s',script],output/'prepare.log').check_returncode()
        model=json.loads(modelpath.read_text())['modules']['Usb'];nets=model['netnames'];cells=model['cells']
        equal=[('engine.clk','usbClock'),('engine.cadence.clk','usbClock'),
               ('engine.cadence.reset_n','engine.release_0.released'),
               ('engine.in.bitEnable','engine.cadence.enable'),('engine.out.bitEnable','engine.cadence.enable'),
               ('engine.in.reset_n','engine.inRelease.released'),('engine.out.reset_n','engine.outRelease.released'),
               ('engine.inRelease.clk','usbClock'),('engine.outRelease.clk','usbClock'),
               ('engine.in.memory.reset_n','engine.in.reset_n'),('engine.out.memory.reset_n','engine.out.reset_n'),
               ('engine.in.appData','tx.out'),('engine.in.appValid','tx.valid'),('engine.out.appReady','rx.ready')]
        for left,right in equal:
            if nets[left]['bits']!=nets[right]['bits']:raise ValueError('Wrong wrapper composition: '+left+' != '+right)
            receipt['bindings'][left]=dict(equal=right,bits=nets[left]['bits'])
        def factors(bits,seen=()):
            key=tuple(bits)
            if key in seen:raise ValueError('Cyclic reset cone')
            drivers=[c for c in cells.values() if c['connections'].get('Y')==bits and c['type'] in ('$and','$logic_and')]
            if not drivers:return {key}
            if len(drivers)!=1:raise ValueError('Ambiguous reset cone')
            c=drivers[0]['connections'];return factors(c['A'],(*seen,key))|factors(c['B'],(*seen,key))
        for block in ('in','out'):
            pin='engine.'+block+'Release.reset_n';root=tuple(nets['engine.release_0.released']['bits'])
            if root not in factors(nets[pin]['bits']):raise ValueError('Buffer reset can outlive engine reset')
            receipt['bindings'][pin]=dict(required_factor='engine.release_0.released')
        for block in ('in','out'):
            if len(nets['engine.'+block+'.memory.readAddress']['bits'])!=5:
                raise ValueError('Wrapper is not the proved 16-byte production geometry')
        # Bind each actually retained patched vendor file, not the pristine pin.
        for name in ('sie.v','phy_rx.v','phy_tx.v'):
            if digest(output/'emit/usb'/name)!=prior['emitted_sha256'][str(proof.parent/'emit'/name)]:
                raise ValueError('Wrapper vendor differs from SIE proof: '+name)
        receipt.update(status='pass',wrapper_sha256=digest(modelpath),source_sha256=prior['source_sha256'],
            qualification='Exact production wrapper bindings. Packet inputs may be arbitrary; no CDC spacing or application epoch assumption.')
        if simulate:
            command=[sys.executable,'tools/sbt.py','testOnly deadhorse.usb.UsbSieCompositionSpec']
            process=execute(command,output/'simulation.log',600);process.check_returncode()
            log=(output/'simulation.log').read_text()
            if 'Tests: succeeded 4, failed 0' not in log or 'All tests passed.' not in log:
                raise ValueError('Incomplete focused traffic/fault suite')
            artifacts={}
            for scenario in ('positive','fault-1','fault-2','fault-3'):
                directory=ROOT/'build/t19/sie-composition-simulation'/scenario
                files=[p for p in directory.rglob('*') if p.is_file() and p.suffix in ('.sv','.v','.log','.txt')]
                if not any(p.suffix=='.sv' for p in files):raise ValueError('Missing real simulation emission: '+scenario)
                artifacts.update({str(p):digest(p) for p in files})
            receipt['simulation']=dict(command=command,returncode=process.returncode,log_sha256=digest(output/'simulation.log'),
                                       artifact_sha256=artifacts,status='pass')
    except Exception as error:receipt.update(status='failed',error=str(error))
    finally:
        if any(digest(ROOT/p)!=h for p,h in bound.items()):receipt.update(status='failed',error='Wrapper proof/simulation source changed')
        if any(digest(p)!=h for p,h in receipt.get('emitted_sha256',{}).items()):receipt.update(status='failed',error='Wrapper emission changed')
    save(output/'result.json',receipt);return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--bind-proof',type=Path);p.add_argument('--regmap',type=Path)
    p.add_argument('--simulate',action='store_true')
    a=p.parse_args()
    if a.bind_proof and not a.regmap:p.error('--regmap required for wrapper binding')
    r=bind_wrapper(a.output,a.bind_proof.resolve(),a.regmap,a.simulate) if a.bind_proof else run(a.output)
    print(r['status'].upper()+' SIE packet contract',flush=True)
    sys.exit(0 if r['status'] in ('safety-proved','pass') else 1)

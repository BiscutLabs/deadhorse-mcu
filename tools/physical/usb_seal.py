"""Seal the completed physical diagnostic, including failures, for review.

Does not run hardware tools or CI. --verify fails if any bound file has changed.
"""
import argparse
import json
from pathlib import Path
import sys
from usb_prepare import ROOT,sha
from usb_validate import audit_hashes,number,rows,require_complete,class_coverage,replacement_arguments,audit_queries
from usb_graph import equivalent,reset_chains
from usb_sdc_audit import compare
sys.path.insert(0,str(ROOT/'tools/timing'))
from usb_boundary import characterize,contract,groups

def seal(physical,validation,sdc_audit,netlist_audit,output):
    inputs=json.loads((physical/'inputs.json').read_text())
    audit_hashes(inputs['source_sha256'])
    result=json.loads((validation/'result.json').read_text())
    baseline=next(ROOT/n for n in inputs['input_sha256'] if n.endswith('/timing/usb/result.json'))
    before=json.loads((baseline.parent/'mapped.json').read_text())['modules']['Usb']
    after=json.loads((physical/'routed.json').read_text())['modules']['Usb']
    result['graph']=dict(connectivity=equivalent(before,after,**replacement_arguments(inputs)),rdc=reset_chains(before))
    audit_hashes(json.loads((netlist_audit/'result.json').read_text())['sha256'])
    sdc=json.loads((sdc_audit/'result.json').read_text())
    if len(sdc)!=15 or any(x['status']!='pass' for x in sdc):raise ValueError('Incomplete SDC audit')
    result['sdc_audit']=sdc
    for entry in sdc:
        if sha(sdc_audit/entry['corner']/'effective.sdc')!=entry['effective_sha256']:raise ValueError('Stale effective SDC')
        compare((physical/'full.sdc').read_text(),(physical/'timing'/entry['corner']/'boundary.sdc').read_text(),(sdc_audit/entry['corner']/'effective.sdc').read_text())
    setup=[]
    for c in result['corners']:
        name=c['corner']
        require_complete((validation/name/'run.log').read_text(),'USB_DIAGNOSTICS_COMPLETE')
        class_coverage(json.loads((validation/name/'corrected-paths.json').read_text()),json.loads(baseline.read_text()))
        setup += [dict(r,corner=name,slack_ns=number(r['slack_ns'])) for r in rows(validation/name/'setup.tsv')]
    result['worst_period_setup']=min(setup,key=lambda r:r['slack_ns'])
    result['period_setup_violations']=[r for r in setup if r['slack_ns']<0]
    result['delay_interpretation']='Worst observed endpoint-enumerated CLK-to-Q plus data delay, with actual launch CLK arrival removed; absolute-arrival path selection may differ from data-delay ordering. Raw full-period setup slack checked separately.'
    if json.loads((physical/'extraction-inputs.json').read_text()).get('path_metric')=='launch-relative-data-v3-fixed-launch-enumeration':
        for c in result['corners']:
            source=physical/'timing'/c['corner']
            audit=audit_queries(rows(source/'paths.tsv'),rows(source/'paths.tsv.expected.tsv'),rows(source/'paths.tsv.queries.tsv'))
            if c.get('query_audit')!=audit:raise ValueError('Changed timing query audit')
        result['delay_interpretation']='Worst data delay from exhaustive fixed-register-launch/endpoint/polarity queries, retaining CLK-to-Q and subtracting cached propagated launch insertion. Inputs retain absolute boundary arrival. Every query and no-timed-path pair accounted; full-period slack remains separate.'
    pdk=ROOT/'build/physical/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0'
    # Correct descriptive metadata only; all original numeric scripts/reports
    # remain intact and hashes bind them. Old metadata hard-coded SS prose.
    contracts={};pulse={};library_paths=[]
    for corner in sorted({c['corner'].rsplit('-',1)[0] for c in result['corners']}):
        lib=pdk/'lib'/('gf180mcu_fd_sc_mcu7t5v0__'+corner+'.lib');library_paths.append(lib)
        c=contract('Usb',characterize(lib))
        c['characterization']['method']=c['characterization']['method'].replace('pinned SS corner only','pinned '+corner+' corner')
        c['reset_basis']='Per-corner dffrnq_1 rising CLK-to-Q with unchanged slew/load envelope. Arbitrary peer phase and asynchronous assertion remain unqualified.'
        c['limitations']='Standalone diagnostic; no approved upstream reset, pad, board or analog metastability implementation.'
        contracts[corner]=c
        cell=next(b for n,b in groups(lib.read_text(),'cell') if n=='gf180mcu_fd_sc_mcu7t5v0__dffrnq_1')
        rn=next(b for n,b in groups(cell,'pin') if n=='RN')
        import re
        pulse[corner]=dict(scalar_min_low_ns=float(re.search(r'min_pulse_width_low\s*:\s*([\d.]+)',rn)[1]),
            qualification='Library scalar requirement only; transition-dependent pulse-width tables and actual upstream pulse/glitch freedom remain unqualified. No reset waveform signoff.')
    result['corner_contracts']=contracts;result['reset_pulse_requirements']=pulse
    # Cell area is measured Liberty area sum, not die/core or power-grid area.
    ss=pdk/'lib/gf180mcu_fd_sc_mcu7t5v0__ss_125C_3v00.lib'
    import re
    areas={n:float(re.search(r'\barea\s*:\s*([\d.]+)',b)[1]) for n,b in groups(ss.read_text(),'cell')}
    mapped=json.loads((physical/'routed.json').read_text())['modules']['Usb']['cells']
    original=result['graph']['connectivity']['original_cells']
    result['area_um2']=dict(routed_cell_sum=sum(areas[c['type']] for c in mapped.values()),cells=len(mapped),original_cells=original,
        meaning='Measured sum of pinned Liberty cell area; includes CTS/ties, excludes PDN/pads/fillers')
    files=set(library_paths)
    files.update(p for p in physical.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.resolve()!=output.resolve())
    files.update(p for p in (ROOT/'tools/physical').glob('*') if p.is_file())
    files.update(ROOT/n for n in inputs['source_sha256'])
    files.update(ROOT/n for n in inputs['input_sha256'] if not n.startswith('tools/physical/'))
    # Generated constraint/certificate dependencies are included explicitly.
    baseline=next(ROOT/n for n in inputs['input_sha256'] if n.endswith('/timing/usb/result.json'))
    files.update(p for p in baseline.parent.iterdir() if p.is_file())
    result['file_sha256']={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)}
    output.write_text(json.dumps(result,indent=2)+'\n')
    print('SEALED diagnostic failures and source/artifact hashes; CI not run')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('physical','validation','sdc-audit','netlist-audit','output','verify'):p.add_argument('--'+flag,type=Path)
    a=p.parse_args()
    if a.verify:
        audit_hashes(json.loads(a.verify.read_text())['file_sha256']);print('PASS sealed physical evidence unchanged')
    else:
        if not all((a.physical,a.validation,a.sdc_audit,a.netlist_audit,a.output)):p.error('physical, validation, audits and output required')
        for path in (a.physical,a.validation,a.sdc_audit,a.netlist_audit,a.output):path.resolve().relative_to(ROOT/'build')
        if a.output.exists():raise ValueError('Preserve existing receipt')
        seal(a.physical.resolve(),a.validation.resolve(),a.sdc_audit.resolve(),a.netlist_audit.resolve(),a.output.resolve())

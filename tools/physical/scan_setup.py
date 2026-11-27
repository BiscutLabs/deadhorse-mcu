"""Prepare T37 placement/CTS construction inputs, not timing acceptance SDC.

Run in the pinned physical environment. Reuse the reviewed T38 pad/macro/PDN
configuration; retain all clock mux legs and create clocks at the actual scan
groups. Functional, shift and capture timing need separate mode constraints.
"""
import argparse
import json
from pathlib import Path
import time

from scan_capture import sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','insert','manifest','header','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--exclude-delay-cells',action='store_true',
                   help='Exclude only dlyb_1/2/4 from electrical repair; other delay families remain eligible')
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    ins=json.loads((a.insert/'result.json').read_text());m=json.loads(a.manifest.read_text())
    if ins['status']!='pass_unplaced_insertion':raise ValueError('Unqualified insertion')
    for name in ('after.json','scan.v'):
        if sha(a.insert/name)!=ins['artifacts'][name]:raise ValueError('Changed inserted artifact')
    if sha(a.manifest) not in ins['input_sha256'].values():raise ValueError('Wrong scan manifest')
    g=json.loads((a.insert/'after.json').read_text());c=ins['controls']
    drivers={}
    for name,cell in g.items():
        for pin,net in cell['pins'].items():
            if pin in c['output_pins'][cell['type']] and net is not None:
                if net in drivers:raise ValueError('Ambiguous physical driver')
                drivers[net]=(name,pin)
    roots={g[row['cells'][0]]['pins']['CLK'] for row in m['lanes']}
    roots.update(c['clock_muxes']);roots.update((c['tck'],c['osc'],g['i_chip_core.soc.lf']['pins']['clock']))
    sdc=['set_units -time ns -capacitance pF','# CTS construction only; timings are intentionally not qualified.']
    for i,net in enumerate(sorted(roots)):
        name,pin=drivers[net]
        if any(x in name+pin for x in '{}\n\r'):raise ValueError('Unsafe Tcl pin identifier')
        sdc.append('create_clock -name physical_'+str(i)+' -period 20.833333333333333 [get_pins {'+name+'/'+pin+'}]')
    sdc.extend(['set_clock_uncertainty 0.25 [all_clocks]','set_clock_transition 0.15 [all_clocks]'])
    (out/'construction.sdc').write_text('\n'.join(sdc)+'\n')
    cfg=json.loads(a.config.read_text());cfg['VERILOG_FILES']=[str((a.insert/'scan.v').resolve())]
    for k in ('PNR_SDC_FILE','SIGNOFF_SDC_FILE','FALLBACK_SDC'):cfg[k]=str(out/'construction.sdc')
    cfg['PL_TIMING_DRIVEN']=False;cfg['RUN_POST_CTS_RESIZER_TIMING']=False
    if a.exclude_delay_cells:
        cfg['EXTRA_EXCLUDED_CELLS']=sorted(set(cfg.get('EXTRA_EXCLUDED_CELLS') or []) |
            {'gf180mcu_fd_sc_mcu7t5v0__dlyb_'+str(drive) for drive in (1,2,4)})
    (out/'config.json').write_text(json.dumps(cfg,indent=2))
    (out/'initial.json').write_text(json.dumps(dict(nl=str((a.insert/'scan.v').resolve()),sdc=str(out/'construction.sdc'),json_h=str(a.header.resolve()))))
    (out/'roots.json').write_text(json.dumps({n:drivers[n] for n in sorted(roots)},indent=2))
    result=dict(status='construction_inputs_only',seconds=time.monotonic()-start,
        inputs={str(q):sha(q) for q in (Path(__file__),a.config,a.manifest,a.header,a.insert/'result.json',a.insert/'after.json',a.insert/'scan.v')},
        artifacts={q.name:sha(q) for q in out.iterdir() if q.is_file()},root_count=len(roots),
        assumptions=['All construction roots use the existing fastest48MHz period; artificial independent roots are not valid STA acceptance constraints',
            'No mode case removes a functional/test clock leg; original pin-root preservation audits bind all20392 FF clock sinks',
            'Post-CTS timing repair, routing and signoff are outside this stage'])
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print('Prepared',len(roots),'construction roots; no timing acceptance')


if __name__=='__main__':main()

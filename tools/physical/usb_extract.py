"""Prepare corner-specific routed RC extraction and timing with unchanged limits."""
import argparse
import json
from pathlib import Path
import sys
from usb_prepare import ROOT,linux,sha
sys.path.insert(0,str(ROOT/'tools/timing'))
from usb_boundary import characterize,contract,tcl_rows

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--physical',type=Path,required=True);p.add_argument('--snapshot',type=Path,required=True)
    a=p.parse_args();out=a.physical.resolve();src=a.snapshot.resolve();out.relative_to(ROOT/'build');src.relative_to(ROOT/'build')
    if 'USB_DETAIL_ROUTE_COMPLETE' not in (out/'run.log').read_text(encoding='utf-8-sig'):raise ValueError('Detailed route incomplete')
    pdk=ROOT/'build/physical/pdk/gf180mcuD';sc=pdk/'libs.ref/gf180mcu_fd_sc_mcu7t5v0';block=src/'timing/usb'
    for rc in ('min','nom','max'):
        target=out/('extract-'+rc);target.mkdir(exist_ok=False)
        script=f'read_db {{{linux(out/"routed.odb")}}}\ndefine_process_corner -ext_model_index 0 {rc}\nset_extraction_rules_file {{{linux(pdk/"libs.tech/librelane"/f"rules.openrcx.gf180mcuD.{rc}")}}}\nextract_parasitics\nwrite_spef {{{linux(target/"routed.spef")}}}\nputs USB_EXTRACTION_COMPLETE\n'
        (target/'run.tcl').write_text(script)
    analysis=(ROOT/'tools/timing/analyze.tcl').read_text()
    analysis=analysis.replace('link_design $top\n','link_design $top\nread_spef $spef\n')
    analysis=analysis.replace('set data_inputs [get_ports','set_propagated_clock [all_clocks]\nset data_inputs [get_ports',1)
    # Physical source-clock insertion delay is not combinational data delay.
    # Preserve absolute arrival and real setup/hold checks in the detailed logs.
    analysis=analysis.replace('set delay [get_property $last arrival]', '''set launch 0.0
            set start [get_property $path startpoint]
            if {![get_property $start is_port]} {
                set cp [get_pins [file dirname [get_full_name $start]]/CLK]
                if {[llength $cp]!=1 || [llength [get_property $cp clocks]]!=1} {error "Ambiguous launch clock"}
                # This flow admits only a single rising clock and preserves
                # original direct clock connectivity through a buffer tree.
                set launch [get_property $cp arrival_max_rise]
            }
            set delay [expr {[get_property $last arrival] - $launch}]''')
    analysis+='\nreport_parasitic_annotation -report_unannotated\nreport_clock_skew\nreport_check_types -min_pulse_width -violators -digits 6\nputs USB_PHYSICAL_TIMING_COMPLETE\n'
    (out/'physical-analyze.tcl').write_text(analysis)
    for corner in ('ss_125C_3v00','ss_n40C_3v00','ff_125C_3v60','ff_n40C_3v60','tt_025C_3v30'):
        lib=sc/'lib'/('gf180mcu_fd_sc_mcu7t5v0__'+corner+'.lib')
        c=contract('Usb',characterize(lib))
        c['characterization']['method']=c['characterization']['method'].replace('pinned SS corner only','pinned '+corner+' corner')
        c['reset_basis']='Upstream dffrnq_1 synchronized deassertion; per-corner rising CLK-to-Q and transition values in inputs/characterization. Same assumed slew/load envelope; asynchronous assertion and arbitrary peer phase retained.'
        c['limitations']='Standalone routed diagnostic; upstream implementation, pads, board and analog reset qualification remain open.'
        for rc in ('min','nom','max'):
            target=out/'timing'/f'{corner}-{rc}';target.mkdir(parents=True,exist_ok=False)
            text=(out/'load.tcl').read_text()
            text=text.replace(linux(out/'mapped-ties.v'),linux(out/'routed.v'))
            old=next(line for line in text.splitlines() if line.startswith('set liberty '))
            text=text.replace(old,f'set liberty {{{linux(lib)}}}')
            old=next(line for line in text.splitlines() if line.startswith('set usb_input_contract '))
            text=text.replace(old,'set usb_input_contract {'+tcl_rows(c['inputs'])+'}')
            text=text.replace(linux(out/'prelayout'),linux(target)).replace('/work/tools/timing/analyze.tcl',linux(out/'physical-analyze.tcl'))
            text=f'set spef {{{linux(out/("extract-"+rc)/"routed.spef")}}}\n'+text
            (target/'run.tcl').write_text(text)
            (target/'contract.json').write_text(json.dumps(dict(corner=corner,contract=c),indent=2)+'\n')
    receipt=dict(routed_db_sha256=sha(out/'routed.odb'),routed_netlist_sha256=sha(out/'routed.v'),
        path_metric='launch-relative-data-v2',
        analysis_sha256=sha(out/'physical-analyze.tcl'),generator_sha256=sha(Path(__file__)),
        assumption='Same input slew/load and reset source-flop envelope, characterized separately at each PVT; board/upstream implementation unqualified')
    (out/'extraction-inputs.json').write_text(json.dumps(receipt,indent=2)+'\n');print('PREPARED three RC and five PVT corners')

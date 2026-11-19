# Variables and pinned constraints are supplied by check.py. Fail closed: OpenSTA
# may return success after a Tcl error, so the caller also requires COMPLETE.
read_liberty $liberty
read_verilog $netlist
link_design $top
set_units -time ns -capacitance pF
if {![info exists combinational]} {set combinational 0}
if {![info exists gate_path_report]} {set gate_path_report [file join [file dirname $path_report] gate_checks.tsv]}
set clocks {}
set clock_names {block_clock}
if {[info exists domain_periods]} {
    set clock_names [dict keys $domain_periods]
    foreach {name domain_period} $domain_periods {
        set port [get_ports $name]
        if {[llength $port]!=1} {error "Missing wrapper clock"}
        lappend clocks {*}$port
        create_clock -name $name -period $domain_period $port
    }
    set_clock_groups -asynchronous -group appClock -group usbClock -group aonClock
} elseif {$combinational} {
    create_clock -name block_clock -period $period
} else {
    set clocks [get_ports $clock_port]
    if {[llength $clocks] != 1} {error "Expected one clock port"}
    create_clock -name block_clock -period $period $clocks
}
set data_inputs [get_ports -filter "direction == input" *]
if {!$combinational} {
    foreach clock $clocks {set data_inputs [lsearch -all -inline -not -exact $data_inputs $clock]}
}
if {[llength $data_inputs]} {
    foreach name $clock_names {set_input_delay 0 -clock $name -add_delay $data_inputs}
    set_input_transition $input_transition $data_inputs
}
set outputs [get_ports -filter "direction == output" *]
if {[llength $outputs]} {
    foreach name $clock_names {set_output_delay 0 -clock $name -add_delay $outputs}
    set_load $output_load $outputs
}
set regs [all_registers]
if {$combinational && [llength $regs]} {error "Sequential cell in combinational timing mode"}
if {!$combinational && ![llength $regs]} {error "No clocked registers found"}
if {[llength [all_registers -level_sensitive]]} {error "Unsupported latch timing"}
foreach pin [all_registers -clock_pins] {
    set pin_clocks [get_property $pin clocks]
    if {[llength $pin_clocks] != 1} {
        error "Missing clock: [get_full_name $pin]"
    }
    if {[get_full_name [lindex $pin_clocks 0]] ni $clock_names} {
        error "Unexpected clock: [get_full_name $pin]"
    }
}
set rising_regs {}
foreach name $clock_names {lappend rising_regs {*}[all_registers -rise_clock $name]}
if {[llength $rising_regs] != [llength $regs]} {
    error "Unsupported falling-edge or generated clock timing"
}
check_setup -verbose
set groups [list RR [list [all_registers -clock_pins] [all_registers -data_pins]] \
                 IR [list $data_inputs [all_registers -data_pins]] \
                 RO [list [all_registers -clock_pins] $outputs] \
                 IO [list $data_inputs $outputs]]
if {[info exists certified_q]} {
    foreach name {certified_q certified_d certified_clock full_q full_d reset_pins} {
        set raw [set $name]
        set $name [get_pins $raw]
        if {[llength [set $name]] != [llength $raw]} {error "Missing D45 $name pin"}
    }
    if {[llength $certified_d]+[llength $full_d] != [llength [all_registers -data_pins]]} {
        error "Incomplete D45 register partition"
    }
    set_multicycle_path 4 -setup -from $certified_clock -to $certified_d
    set_multicycle_path 3 -hold -from $certified_clock -to $certified_d
    set groups [list CC [list $certified_q $certified_d] CF [list $certified_q $full_d] \
                     FC [list $full_q $certified_d] FF [list $full_q $full_d] \
                     IR [list $data_inputs [all_registers -data_pins]] \
                     RO [list [all_registers -clock_pins] $outputs] IO [list $data_inputs $outputs]]
    set safety [open [file join [file dirname $path_report] short_reset_checks.tsv] w]
    puts $safety "check\tstart\tend\tslack_ns"
    foreach {kind targets modes} [list hold [all_registers -data_pins] {min_rise min_fall} \
        reset $reset_pins {min_rise min_fall max_rise max_fall}] {
        if {![llength $targets]} {continue}
        foreach mode $modes {
            foreach path [find_timing_paths -to $targets -path_delay $mode -group_path_count [expr {2*[llength $targets]}] -endpoint_path_count 1] {
                set slack [get_property $path slack]
                puts $safety "$kind/$mode\t[get_full_name [get_property $path startpoint]]\t[get_full_name [get_property $path endpoint]]\t$slack"
                # Keep all violations in the receipt instead of stopping before
                # the remaining classes are measured. Python rejects negatives.
            }
        }
    }
    close $safety
}
if {[info exists domain_periods]} {
    # Enumerate every destination domain separately; cross-domain physical skew
    # belongs to shared CDC qualification, not synchronous setup/hold STA.
    set groups {}
    foreach name $clock_names {
        set dq {};set dd {};set cq {};set cd {};set fq {};set fd {}
        foreach cell [all_registers -rise_clock $name] {
            set base [get_full_name $cell]
            set q [get_pins $base/Q];set d [get_pins $base/D]
            if {[llength $q]!=1 || [llength $d]!=1} {error "Unsupported wrapper register pins"}
            lappend dq {*}$q;lappend dd {*}$d
            if {[lindex $d 0] in $certified_d} {
                if {$name!="usbClock"} {error "Certified register outside USB domain"}
                lappend cq {*}$q;lappend cd {*}$d
            } else {lappend fq {*}$q;lappend fd {*}$d}
        }
        lappend groups $name.CC [list $cq $cd] $name.CF [list $cq $fd] \
            $name.FC [list $fq $cd] $name.FF [list $fq $fd] \
            $name.IR [list $data_inputs $dd] $name.RO [list $dq $outputs] $name.IO [list $data_inputs $outputs]
    }
}
if {[info exists clock_gate_pins] && [llength $clock_gate_pins]} {
    set gate_enables [get_pins $clock_gate_pins]
    if {[llength $gate_enables] != [llength $clock_gate_pins]} {error "Missing clock-gate enable pin"}
    # Root and gated clocks retain the existing ideal pre-CTS convention.
    # Enable setup/hold is characterized by the actual ICG Liberty arcs.
    set gate_report [open $gate_path_report w]
    puts $gate_report "pin\tcheck\tslack_ns"
    foreach pin $gate_enables {
        foreach polarity {max_rise max_fall min_rise min_fall} {
            set paths [find_timing_paths -to $pin -path_delay $polarity -group_path_count 1]
            if {[llength $paths] != 1} {error "Missing clock-gate enable path"}
            set slack [get_property [lindex $paths 0] slack]
            puts $gate_report "[get_full_name $pin]\t$polarity\t$slack"
            flush $gate_report
            if {$slack < 0} {close $gate_report; error "Clock-gate enable setup/hold violation"}
        }
    }
    close $gate_report
    lappend groups RG [list [all_registers -clock_pins] $gate_enables] IG [list $data_inputs $gate_enables]
}
set f [open $path_report w]
puts $f "class\tdelay_ns\tstart\tend\tcell_depth\tlogic_depth\tpoints"
foreach {kind ends} $groups {
    lassign $ends from to
    if {![llength $from] || ![llength $to]} {continue}
    # Enumerate every endpoint and both transition polarities. A single worst
    # slack path can miss the worst arrival when endpoint setup times differ.
    foreach polarity {max_rise max_fall} {
        set paths [find_timing_paths -from $from -to $to -path_delay $polarity \
            -group_path_count [expr {2 * [llength $to]}] -endpoint_path_count 1]
        foreach path $paths {
            set points [get_property $path points]
            set last [lindex $points end]
            # OpenSTA get_property returns times in the selected command units.
            # The first point can be Q, whose arrival already includes clock-to-Q.
            # All supported launches are at ideal rising edge zero (or zero IO
            # delay); use endpoint arrival, never subtract the first point.
            set delay [get_property $last arrival]
            set cells {}
            set trace {}
            foreach point $points {
                set pin [get_property $point pin]
                lappend trace "[get_full_name $pin]@[get_property $point arrival]"
                if {![get_property $pin is_port]} {
                    set name [get_full_name $pin]
                    dict set cells [file dirname $name] 1
                }
            }
            set depth [dict size $cells]
            foreach reg $regs {
                if {[dict exists $cells [get_full_name $reg]]} {incr depth -1}
            }
            puts $f "$kind\t$delay\t[get_full_name [get_property $path startpoint]]\t[get_full_name [get_property $path endpoint]]\t[dict size $cells]\t$depth\t[join $trace {; }]"
        }
    }
}
close $f
report_checks -path_delay max -group_path_count 4 -format full_clock_expanded -digits 6
report_checks -path_delay min -group_path_count 4 -format full_clock_expanded -digits 6
puts "ELECTRICAL_BEGIN"
report_check_types -max_slew -max_capacitance -violators -digits 6
puts "ELECTRICAL_END"
puts "TIMING_COMPLETE"

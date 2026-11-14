# Variables and pinned constraints are supplied by check.py. Fail closed: OpenSTA
# may return success after a Tcl error, so the caller also requires COMPLETE.
read_liberty $liberty
read_verilog $netlist
link_design $top
set_units -time ns -capacitance pF
set clocks [get_ports $clock_port]
if {[llength $clocks] != 1} {error "Expected one clock port"}
create_clock -name block_clock -period $period $clocks
set data_inputs [get_ports -filter "direction == input" *]
set data_inputs [lsearch -all -inline -not -exact $data_inputs [lindex $clocks 0]]
if {[llength $data_inputs]} {
    set_input_delay 0 -clock block_clock $data_inputs
    set_input_transition $input_transition $data_inputs
}
set outputs [get_ports -filter "direction == output" *]
if {[llength $outputs]} {
    set_output_delay 0 -clock block_clock $outputs
    set_load $output_load $outputs
}
set regs [all_registers]
if {![llength $regs]} {error "No clocked registers found"}
if {[llength [all_registers -level_sensitive]]} {error "Unsupported latch timing"}
foreach pin [all_registers -clock_pins] {
    if {[llength [get_property $pin clocks]] != 1} {
        error "Missing clock: [get_full_name $pin]"
    }
}
if {[llength [all_registers -rise_clock block_clock]] != [llength $regs]} {
    error "Unsupported falling-edge or generated clock timing"
}
check_setup -verbose
set groups [list RR [list [all_registers -clock_pins] [all_registers -data_pins]] \
                 IR [list $data_inputs [all_registers -data_pins]] \
                 RO [list [all_registers -clock_pins] $outputs] \
                 IO [list $data_inputs $outputs]]
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
puts "TIMING_COMPLETE"

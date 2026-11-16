read_liberty $liberty
read_verilog $source
link_design ClockGate
set_units -time ns -capacitance pF
create_clock -name root_clock -period $period [get_ports clk_i]
set_clock_transition $transition [get_clocks root_clock]
set_input_delay 0 -clock root_clock [get_ports {en_i test_en_i}]
set_input_transition $transition [get_ports {en_i test_en_i}]
set_output_delay 0 -clock root_clock [get_ports clk_o]
set_load $load [get_ports clk_o]
set_propagated_clock [get_clocks root_clock]
set f [open $metrics w]
puts $f "metric\tvalue_ns"
foreach polarity {max_rise max_fall} {
    set paths [find_timing_paths -from [get_ports clk_i] -to [get_ports clk_o] -path_delay $polarity -group_path_count 1]
    if {[llength $paths] != 1} {error "Missing clock propagation path $polarity"}
    set points [get_property [lindex $paths 0] points]
    # Both endpoints are clock ports: subtract the launch-edge offset to
    # measure CLK-to-Q delay, including the full cell propagation delay.
    set delay [expr {[get_property [lindex $points end] arrival]-[get_property [lindex $points 0] arrival]}]
    puts $f "clock_${polarity}\t$delay"
}
foreach port {en_i test_en_i} {
    set pin [expr {$port == "en_i" ? "cell_0/E" : "cell_0/TE"}]
    foreach type {max_rise max_fall min_rise min_fall} {
        set paths [find_timing_paths -from [get_ports $port] -to [get_pins $pin] -path_delay $type -group_path_count 1]
        if {[llength $paths] != 1} {error "Missing enable setup/hold path $port $type"}
        puts $f "${port}_${type}_slack\t[get_property [lindex $paths 0] slack]"
    }
}
close $f
report_checks -path_delay max -group_path_count 10 -format full_clock_expanded -digits 6
report_checks -path_delay min -group_path_count 10 -format full_clock_expanded -digits 6
puts "ELECTRICAL_BEGIN"
report_check_types -max_slew -max_capacitance -violators -digits 6
puts "ELECTRICAL_END"
puts "CLOCK_GATE_TIMING_COMPLETE"

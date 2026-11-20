# Inputs: liberty, netlist, spef, boundary_sdc, diagnostic_dir, reset_chains.
# Full SDC retains protocol exceptions; per-corner SDC reapplies the same
# boundary contract characterized at this PVT. Reset-chain/RN checks are full-rate.
read_liberty $liberty
read_verilog $netlist
link_design Usb
read_spef $spef
read_sdc $full_sdc
read_sdc $boundary_sdc
set_propagated_clock [all_clocks]
set f [open $diagnostic_dir/clocks.tsv w]
puts $f "pin\tmax_rise_ns\tmin_rise_ns"
foreach pin [all_registers -clock_pins] {
    if {[llength [get_property $pin clocks]]!=1} {error "Ambiguous clock"}
    puts $f "[get_full_name $pin]\t[get_property $pin arrival_max_rise]\t[get_property $pin arrival_min_rise]"
}
close $f
set f [open $diagnostic_dir/rdc.tsv w]
puts $f "kind\tcheck\tstart\tend\tslack_ns"
foreach pair $reset_chains {
    lassign $pair first second
    foreach mode {max_rise max_fall min_rise min_fall} {
        set paths [find_timing_paths -from [get_pins $first/Q] -to [get_pins $second/D] -path_delay $mode -group_path_count 1]
        if {[llength $paths]!=1} {error "Missing reset interstage path"}
        foreach path $paths {puts $f "interstage\t$mode\t[get_full_name [get_property $path startpoint]]\t[get_full_name [get_property $path endpoint]]\t[get_property $path slack]"}
        report_checks -from [get_pins $first/Q] -to [get_pins $second/D] -path_delay $mode -group_path_count 1 -format full_clock_expanded -digits 6
        # Active-low RN has rising-edge recovery/removal, no falling-edge
        # deassertion check. Asynchronous assertion remains in the source model.
        if {$mode in {max_fall min_fall}} {continue}
        set paths [find_timing_paths -from [get_pins $second/Q] -to [get_pins */RN] -path_delay $mode -group_path_count 5000 -endpoint_path_count 1]
        if {![llength $paths]} {error "Missing downstream reset path"}
        foreach path $paths {puts $f "downstream\t$mode\t[get_full_name [get_property $path startpoint]]\t[get_full_name [get_property $path endpoint]]\t[get_property $path slack]"}
    }
}
close $f
set f [open $diagnostic_dir/setup.tsv w]
puts $f "start\tend\tslack_ns"
foreach path [find_timing_paths -path_delay max -group_path_count 10000 -endpoint_path_count 1] {
    puts $f "[get_full_name [get_property $path startpoint]]\t[get_full_name [get_property $path endpoint]]\t[get_property $path slack]"
}
close $f
puts USB_DIAGNOSTICS_COMPLETE

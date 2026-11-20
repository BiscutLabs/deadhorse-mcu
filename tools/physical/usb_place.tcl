# Standalone USB physical diagnostic; constraints are inherited without waivers.
set_thread_count 4
read_lef $techlef
read_lef $celllef
source $out/load.tcl
write_sdc $out/full.sdc
initialize_floorplan -utilization 55 -aspect_ratio 1 -core_space 10 -site GF018hv5v_mcu_sc7
make_tracks
place_pins -hor_layers Metal3 -ver_layers Metal2
# Values from the pinned PDK's LibreLane config: kohm/um and pF/um.
foreach {layer resistance capacitance} {
    Metal2 3.85861e-4 1.35357e-4
    Metal3 2.06673e-4 1.46141e-4
    Metal4 1.68609e-4 1.50688e-4
    Metal5 7.92778e-5 1.55595e-4
} {
    set_layer_rc -layer $layer -resistance [sta::resistance_sta_ui [expr {1000*$resistance}]] \
        -capacitance [sta::capacitance_sta_ui [expr {1e-12*$capacitance}]]
}
set_wire_rc -signal -layer Metal3
set_wire_rc -clock -layer Metal4
repair_tie_fanout -separation 1 gf180mcu_fd_sc_mcu7t5v0__tieh/Z
repair_tie_fanout -separation 1 gf180mcu_fd_sc_mcu7t5v0__tiel/ZN
global_placement -density 0.60
detailed_placement
check_placement -verbose
estimate_parasitics -placement
write_db $out/placed.odb
write_def $out/placed.def
puts "USB_PLACEMENT_COMPLETE"
clock_tree_synthesis -root_buf gf180mcu_fd_sc_mcu7t5v0__clkbuf_16 \
    -buf_list {gf180mcu_fd_sc_mcu7t5v0__clkbuf_2 gf180mcu_fd_sc_mcu7t5v0__clkbuf_4 gf180mcu_fd_sc_mcu7t5v0__clkbuf_8}
detailed_placement
check_placement -verbose
set_propagated_clock [all_clocks]
estimate_parasitics -placement
report_cts -out_file $out/cts.txt
write_db $out/clock.odb
write_def $out/clock.def
puts "USB_CTS_COMPLETE"
set_routing_layers -signal Metal2-Metal5 -clock Metal2-Metal5
global_route -guide_file $out/route.guide
estimate_parasitics -global_routing
write_db $out/global.odb
write_def $out/global.def
write_verilog $out/global.v
write_sdc $out/propagated.sdc
puts "USB_GLOBAL_ROUTE_COMPLETE"
# OpenDB can retain an unused synthetic constant net after tie insertion.
# Never delete a connected supply or signal; only the empty tool artifact.
foreach net [[ord::get_db_block] getNets] {
    if {[$net getSigType] in {POWER GROUND} && ![llength [$net getITerms]] && ![llength [$net getBTerms]]} {
        puts "USB_EMPTY_CONSTANT_NET_REMOVED [$net getName]"
        odb::dbNet_destroy $net
    }
}
detailed_route -output_drc $out/route.drc -output_maze $out/maze.log -verbose 0
write_db $out/routed.odb
write_def $out/routed.def
write_verilog $out/routed.v
puts "USB_DETAIL_ROUTE_COMPLETE"

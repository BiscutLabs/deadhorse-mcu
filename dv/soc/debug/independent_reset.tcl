proc verify_reg {name value} {
    set actual [dict get [get_reg -force [list $name]] $name]
    if {$actual != $value} {error "register $name: expected $value, got $actual"}
}
targets deadhorse.perf
halt
set_reg {fp 0x24681357 pc 0x20000000}
targets deadhorse.lite
halt
set_reg {fp 0x13572468 pc 0x30000000}
# The simulator changes only mainClock/mainCoreReset_n: a short reset entirely
# inside a stopped interval. Lite remains selected and must retain its state.
set control [open $sim_control w]
puts $control "perf-reset-stopped"
close $control
verify_reg fp 0x13572468
verify_reg pc 0x30000000
echo "PASS surviving lite state across stopped-main performance reset"
targets deadhorse.perf
halt
verify_reg pc 0x80
set_reg {fp 0x11223344}
verify_reg fp 0x11223344
targets deadhorse.lite
verify_reg fp 0x13572468
echo "PASS T32 INDEPENDENT RESET"
shutdown

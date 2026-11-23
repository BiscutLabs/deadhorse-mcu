source dv/soc/debug/pins.tcl
poll off
# OpenOCD examination may already have acquired lite. Release that ownership
# before the external loader begins; subsequent I2C frames allow teardown time.
riscv dmi_write 0x10 0
# The loader begins a real serial write and stops AON while it is busy.
pins loader-prepare
# Request lite halt through the actual TAP while its clock is stopped.
riscv dmi_write 0x10 0x80000001
pins aon-run
targets deadhorse.lite
poll on
halt
riscv set_mem_access sysbus
set value [read_memory 0x30000000 32 1]
if {[lindex $value 0] != 0x6f} {error "debug ownership overtook accepted loader write"}
pins loader-check-owned
# Debug-only entry must not manufacture a loader START. Detach releases the
# still-not-started lite hart; the loader then finishes and explicitly starts it.
poll off
riscv dmi_write 0x10 0
pins loader-finish
riscv dmi_write 0x10 0x80000001
poll on
halt
set pc [dict get [get_reg -force {pc}] pc]
if {$pc != 0x30000000} {error "loader image did not execute at its entry"}
echo "PASS T32 LOADER OWNERSHIP"
shutdown

proc check_pc {expected} {
    set actual [dict get [get_reg -force {pc}] pc]
    if {$actual != $expected} {error "reset PC: expected $expected got $actual"}
}
targets deadhorse.lite
halt
targets deadhorse.perf
halt
# OpenOCD's global reset-halt waits for both harts to leave reset before
# returning. PLAN05 intentionally keeps lite held until performance releases
# it; drive the same real reset pin and service the harts in boot order.
source dv/soc/debug/pins.tcl
pins pin-reset
targets deadhorse.perf
wait_halt 5000
check_pc 0x80
echo "PASS performance reset-halt"
# Whole-chip reset holds lite. Execute the authorized release on performance;
# the pending debug halt request then catches lite at its retained entry.
riscv set_mem_access progbuf
set held [lindex [read_memory 0x40000300 32 1] 0]
if {($held & 7) != 1} {error "lite not boot-held after reset"}
mww 0x40000304 0x50455246
targets deadhorse.lite
wait_halt 5000
check_pc 0x30000000
echo "PASS lite reset-halt after explicit boot release"
targets deadhorse.perf
riscv set_mem_access progbuf
set released [lindex [read_memory 0x40000300 32 1] 0]
if {($released & 7) != 2} {error "pending halt blocked explicit release"}
if {![catch {mww 0x30000000 0x00000013}]} {error "performance program write succeeded after release"}
# Actual debug ownership protects both boot-control commands.
foreach command {0x4000030c 0x40000304} key {0x484f4c44 0x50455246} {
    mww 0x40000308 1
    mww $command $key
    set event [lindex [read_memory 0x40000308 32 1] 0]
    set state [lindex [read_memory 0x40000300 32 1] 0]
    if {($event & 1) != 1 || ($state & 7) != 2} {error "debug ownership did not reject boot command"}
}
riscv set_mem_access sysbus
set image [lindex [read_memory 0x30000000 32 1] 0]
if {$image != 0x0000006f} {error "denied performance write changed program"}
if {![catch {read_memory 0x40010000 32 1}]} {error "forbidden SBA MMIO succeeded"}
echo "PASS forbidden SBA address"
echo "PASS T32 RESET"
shutdown

proc check_pc {expected} {
    set actual [dict get [get_reg -force {pc}] pc]
    if {$actual != $expected} {error "reset PC: expected $expected got $actual"}
}
targets deadhorse.lite
halt
targets deadhorse.perf
halt
reset halt
targets deadhorse.lite
wait_halt 5000
check_pc 0x30000000
echo "PASS lite reset-halt"
targets deadhorse.perf
wait_halt 5000
check_pc 0x80
echo "PASS performance reset-halt"
riscv set_mem_access sysbus
if {![catch {read_memory 0x40010000 32 1}]} {error "forbidden SBA MMIO succeeded"}
echo "PASS forbidden SBA address"
echo "PASS T32 RESET"
shutdown

proc verify_reg {name value} {
    set actual [dict get [get_reg -force [list $name]] $name]
    if {$actual != $value} {error "register $name: expected $value, got $actual"}
}
targets deadhorse.lite
halt
set_reg {fp 0x13572468 pc 0x30000000}
verify_reg fp 0x13572468
verify_reg pc 0x30000000
echo "PASS lite register access"
riscv set_mem_access sysbus
if {![catch {mww 0x30000000 0x00000013}]} {error "SBA program write succeeded"}
set image [read_memory 0x30000000 32 1]
if {[lindex $image 0] != 0x0000006f} {error "SBA denial changed lite program"}
mww 0x30000400 0x0000006f
set value [read_memory 0x30000400 32 1]
if {[lindex $value 0] != 0x0000006f} {error "retained SBA readback"}
resume
halt
verify_reg pc 0x30000000
echo "PASS lite resume/halt and retained SBA"
targets deadhorse.perf
halt
set_reg {fp 0x24681357 pc 0x20000000}
verify_reg fp 0x24681357
verify_reg pc 0x20000000
riscv set_mem_access sysbus
mww 0x20000000 0x00128293
mww 0x20000004 0x0000006f
set value [read_memory 0x20000000 32 2]
if {[lindex $value 0] != 0x00128293 || [lindex $value 1] != 0x0000006f} {error "performance SBA readback"}
set_reg {t0 41}
step
verify_reg pc 0x20000004
verify_reg t0 42
echo "PASS performance exact single-step"
resume
halt
verify_reg pc 0x20000004
verify_reg t0 42
echo "PASS performance resume/halt"
targets deadhorse.lite
verify_reg fp 0x13572468
echo "PASS hart isolation"
echo "PASS T32 BASIC"
shutdown



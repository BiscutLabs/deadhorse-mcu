# Every DMI access still travels through OpenOCD's real JTAG scans.
proc abstract_result {} {
    for {set i 0} {$i < 100} {incr i} {
        set status [riscv dmi_read 0x16]
        if {($status & 0x1000) == 0} {return [expr {($status >> 8) & 7}]}
    }
    error "abstract command did not finish"
}
targets deadhorse.lite
halt
targets deadhorse.perf
halt
# Background target polling selects a hart; keep it out of raw-selector probes.
poll off
# Debug 0.13.2 section 3.3: discover implemented HARTSELLEN first. The
# two-hart module has one WARL selector bit; no nonexistent index is encodable.
riscv dmi_write 0x10 0x03ffffc1
set control [riscv dmi_read 0x10]
if {($control & 0x03ffffc0) != 0x00010000} {error "unexpected hart selection width"}
foreach requested {0x00020001 0x00030001} {
    riscv dmi_write 0x10 $requested
    set control [riscv dmi_read 0x10]
    if {($control & 0x03ffffc0) != ($requested & 0x00010000)} {error "invalid hart index violated WARL readback: requested=$requested actual=$control"}
    set status [riscv dmi_read 0x11]
    if {($status & 0xc000) != 0 || ($status & 0x300) != 0x300} {error "invalid selection changed hart status"}
}
echo "PASS invalid hart WARL selection and unchanged halted status"
riscv dmi_write 0x10 1
riscv dmi_write 0x16 0x700
riscv dmi_write 0x17 0xff000000
if {[abstract_result] != 2} {error "unsupported command did not report not-supported"}
echo "PASS unsupported abstract command"
riscv dmi_write 0x16 0x700
# RV32E lite has no x16; execution-based abstract access must trap.
riscv dmi_write 0x17 0x00221010
if {[abstract_result] != 3} {error "lite x16 did not report exception"}
riscv dmi_write 0x16 0x700
echo "PASS lite unsupported register"
riscv dmi_write 0x10 0x00010001
poll on
targets deadhorse.perf
riscv set_mem_access sysbus
proc healthy_sba {} {
    mww 0x20000100 0x5a9132e7
    set value [read_memory 0x20000100 32 1]
    if {[lindex $value 0] != 0x5a9132e7} {error "SBA did not recover after error"}
}
healthy_sba
foreach address {0x20004000 0x30000800 0x40010000} {
    if {![catch {read_memory $address 32 1}]} {error "invalid SBA address succeeded: $address"}
    healthy_sba
}
# ROM is readable but not writable by SBA.
if {![catch {mww 0x00000000 0xdeadbeef}]} {error "SBA ROM write succeeded"}
healthy_sba
echo "PASS native and retained SBA errors"
echo "PASS T32 ERRORS"
shutdown

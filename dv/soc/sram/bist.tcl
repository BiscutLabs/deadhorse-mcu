# Actual production TAP, custom DMI CSRs, ordinary DM, and public reset/clocks.
source dv/soc/debug/pins.tcl
poll off
targets deadhorse.perf
proc bist_status {} {return [riscv dmi_read 0x71]}
proc reset_ack {} {
    for {set i 0} {$i < 40} {incr i} {
        if {([bist_status] & 16) != 0} {return}
    }
    error "BIST did not observe both service resets"
}
if {([riscv dmi_read 0x11] & 15) != 2} {error "ordinary DM identity changed"}
riscv dmi_write 0x70 0
if {([bist_status] & 9) != 8} {error "wrong key admitted destructive test"}
riscv dmi_write 0x70 0x42535431
if {([bist_status] & 9) != 8} {error "start without ndmreset was admitted"}
riscv dmi_write 0x10 3
reset_ack
pins aon-stop
riscv dmi_write 0x70 0x42535431
if {([bist_status] & 3) != 1} {error "authorized test did not become busy"}
# DM deactivation clears its ndmreset, but cannot release test ownership.
riscv dmi_write 0x10 0
if {([bist_status] & 19) != 17} {error "DM deactivation released test ownership"}
pathmove RESET IDLE
if {([bist_status] & 19) != 17} {error "TAP reset released or completed test"}
riscv dmi_write 0x10 1
# New SBA requests remain ungranted while the functional system is reset.
# Existing DebugSba errors cancel an already-admitted transaction, not this one.
riscv dmi_write 0x38 0x140000
riscv dmi_write 0x39 0x20000000
for {set i 0} {$i < 2} {incr i} {
    set sba [riscv dmi_read 0x38]
    if {($sba & 0x607000) != 0x200000} {error "functional SBA escaped BIST reset ownership: $sba"}
    if {([bist_status] & 19) != 17} {error "SBA released BIST reset ownership"}
}
pins aon-run
set finished 0
for {set i 0} {$i < 200} {incr i} {
    set status [bist_status]
    if {($status & 1) == 0} {
        if {($status & 6) != 2} {error "BIST failed or completed without done: $status"}
        set finished 1
        break
    }
}
if {!$finished} {error "BIST progress timeout"}
if {[riscv dmi_read 0x72] != 0} {error "successful test left failing address"}
# The pending functional read may be admitted only after port relinquishment.
set complete 0
for {set i 0} {$i < 40} {incr i} {
    set sba [riscv dmi_read 0x38]
    if {($sba & 0x200000) == 0} {set complete 1; break}
}
if {!$complete || ($sba & 0x407000) != 0} {error "SBA did not recover after BIST: $sba"}
if {[riscv dmi_read 0x3c] != 0} {error "post-BIST read missed the final March pattern"}
# The custom owner must still behave after another system reset. Pin reset
# aborts with AON stopped, and delayed remote activity must not restart the test.
riscv dmi_write 0x10 3
reset_ack
pins aon-stop
riscv dmi_write 0x70 0x42535431
if {([bist_status] & 1) == 0} {error "second test did not start"}
pins pin-reset
if {([bist_status] & 15) != 0} {error "external pin reset did not clear test epoch"}
pins aon-run
if {([bist_status] & 15) != 0} {error "remote test replayed after abort"}
riscv dmi_write 0x10 1
if {([riscv dmi_read 0x11] & 15) != 2} {error "ordinary DM failed after BIST abort"}
echo "PASS T32 T35 SRAM BIST OWNERSHIP"
shutdown

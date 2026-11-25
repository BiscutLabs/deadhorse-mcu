source dv/soc/debug/pins.tcl
targets deadhorse.lite
halt
targets deadhorse.perf
halt
riscv set_mem_access sysbus
mww 0x30000500 0x91827364
mww 0x30000504 0x5a6bc7d8
poll off
foreach reset {main-service-reset aon-reset} {
    # Freeze the real destination domain to force retained-path backpressure.
    pins aon-stop
    riscv dmi_write 0x38 0x140000
    riscv dmi_write 0x39 0x30000500
    set busy [riscv dmi_read 0x38]
    if {($busy & 0x200000) == 0} {error "SBA request did not remain outstanding under backpressure"}
    pins $reset
    pins aon-run
    set status [riscv dmi_read 0x38]
    if {($status & 0x200000) != 0 || ($reset eq "main-service-reset" && ($status & 0x7000) == 0)} {
        error "in-flight $reset did not produce a completed SBA error: $status"
    }
    # AON was stopped before bridge admission. Its reset may precede acceptance,
    # in which case the original request can legally complete after restart.
    if {$reset eq "aon-reset" && ($status & 0x7000) == 0} {
        if {[riscv dmi_read 0x3c] != 0x91827364} {error "pre-admission AON reset corrupted the original request"}
    }
    # Clear the prior error and demand data from a distinct request/address.
    # An old response cannot satisfy this operation with the old sentinel.
    riscv dmi_write 0x38 0x547000
    riscv dmi_write 0x39 0x30000504
    set status [riscv dmi_read 0x38]
    if {($status & 0x607000) != 0} {error "new SBA request did not recover: $status"}
    set value [riscv dmi_read 0x3c]
    if {$value != 0x5a6bc7d8} {error "stale or corrupted SBA completion after $reset: $value"}
    echo "PASS backpressured $reset and fresh response"
}
echo "PASS T32 INFLIGHT RESET"
shutdown

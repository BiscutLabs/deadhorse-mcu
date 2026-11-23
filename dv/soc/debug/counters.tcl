proc value {name} {return [dict get [get_reg -force [list $name]] $name]}
targets deadhorse.lite
halt
set original [value dcsr]
if {($original & 0x400) != 0} {error "unexpected lite stopcount"}
set_reg [list dcsr [expr {$original | 0x400}]]
if {([value dcsr] & 0x400) != 0} {error "lite stopcount WARL readback"}
set_reg {mcountinhibit 0}
set before [value minstret]
set_reg {fp 0x13572468}
set after [value minstret]
if {$after <= $before} {error "debug instructions did not increment uninhibited minstret"}
set_reg {mcountinhibit 5}
set retired [value minstret]
set cycles [value mcycle]
set_reg {fp 0x24681357}
if {[value minstret] != $retired || [value mcycle] != $cycles} {error "inhibited counters changed"}
set_reg {mcountinhibit 0}
echo "PASS T32 COUNTERS"
shutdown

# Sideband controls change only external clock/reset pins.
set pin_sequence 0
proc pins {action} {
    global sim_control pin_sequence
    incr pin_sequence
    set request "$pin_sequence $action"
    set out [open $sim_control w]
    puts $out $request
    close $out
    for {set i 0} {$i < 1000} {incr i} {
        if {[file exists "$sim_control.done"]} {
            set in [open "$sim_control.done" r]
            set answer [string trim [read $in]]
            close $in
            if {$answer eq $request} {return}
        }
        sleep 10
    }
    error "external pin scenario did not complete: $action"
}

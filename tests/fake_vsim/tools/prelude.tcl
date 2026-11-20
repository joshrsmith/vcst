# Stubs of the simulator commands used by the scripts VUnit generates. vsim records how the design is loaded, and run
# runs a stand-in for cocotb with the environment of the simulation, using the Python interpreter given to it.
set fake_load_args {}

proc vsim {args} {
    global fake_load_args
    set fake_load_args $args
}

proc run {args} {
    global fake_load_args
    exec $::env(PYGPI_PYTHON_BIN) @FAKE_COCOTB@ {*}$fake_load_args >@ stdout 2>@ stderr
}

proc quit {args} {
    if {[lsearch $args "-sim"] >= 0} {
        return
    }
    set code 0
    set i [lsearch $args "-code"]
    if {$i >= 0} {
        set code [lindex $args [expr {$i + 1}]]
    }
    exit $code
}

proc echo {args} {
    puts [join $args " "]
}

# Other simulator commands have no effect
proc unknown {args} {
    return ""
}

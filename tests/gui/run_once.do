# Runs the test in the GUI that VUnit loaded, has the simulator show a signal inside the design, as a user debugging
# does, and closes the GUI. VCST_GUI_TOP is the language of the top level.
vunit_run
set top [expr {$::env(VCST_GUI_TOP) eq "verilog" ? "gui_dut_verilog" : "gui_dut"}]
if {[catch {examine /$top/not_d} value]} {
    puts "VCST_GUI_EXAMINE_FAILED $value"
} else {
    puts "VCST_GUI_EXAMINED $value"
}
quit -force

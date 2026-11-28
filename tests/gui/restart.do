# Runs the test, restarts the simulation as a user of the GUI does with vunit_restart, which compiles what changed,
# restarts the simulation and runs the test again, and closes the GUI
vunit_run
vunit_restart
quit -force

"""
Fake executables of Riviera-PRO and ModelSim/Questa, enough for VUnit to compile and simulate with them. vsim runs
the tcl script VUnit gives it with tclsh, with the simulator commands stubbed (prelude.tcl).

Usage: fake_tool.py <executable name> [arguments], with FAKE_FLAVOR set to rivierapro or modelsim.
"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

tool, args = sys.argv[1], sys.argv[2:]

if "-version" in args:
    if os.environ.get("FAKE_FLAVOR") == "rivierapro":
        print("Aldec, Inc. VHDL Compiler, build 2023.04.112")
    else:
        print("Questa Sim-64 vcom 2023.4 Compiler")
elif tool == "vlib":
    Path(args[-1]).mkdir(parents=True, exist_ok=True)
elif tool == "vsim":
    # The script to run is either a file or a command
    do = args[args.index("-do") + 1]
    prelude = (HERE / "prelude.tcl").read_text().replace("@FAKE_COCOTB@", str(HERE / "fake_cocotb.py"))
    script = prelude + (f"source {{{do}}}\n" if os.path.isfile(do) else do + "\n")
    if "-c" not in args:
        # The graphical user interface, in which the user starts the simulation with vunit_run
        script += "vunit_run\n"
    file_descriptor, script_name = tempfile.mkstemp(prefix="fake_vsim_", suffix=".tcl")
    with os.fdopen(file_descriptor, "w") as script_file:
        script_file.write(script)
    os.execvp("tclsh", ["tclsh", script_name])

# Runs a cocotb test in the GUI of the simulator, as check.py tells: VCST_GUI_INIT is the Tcl file the GUI sources once
# the design is loaded, VCST_GUI_TOP the language of the top level (vhdl or verilog), and VCST_GUI_FLAGS, if set, are
# given to the simulator as its vsim_flags.gui.
import os
from pathlib import Path

from vcst import VCST

root = Path(os.path.abspath(Path(__file__).parent))

ui = VCST.from_argv(compile_builtins=False)
lib = ui.add_library("lib")
if os.environ.get("VCST_GUI_TOP", "vhdl") == "verilog":
    lib.add_source_files(root / "hdl" / "*.v")
    ui.add_cocotb_testbench(root / "test_gui_verilog")
else:
    lib.add_source_files(root / "hdl" / "*.vhd", vhdl_standard="2008")
    ui.add_cocotb_testbench(root / "test_gui")

simulator = ui.get_simulator_name()
ui.set_sim_option(f"{simulator}.init_file.gui", os.environ["VCST_GUI_INIT"])
if os.environ.get("VCST_GUI_FLAGS"):
    ui.set_sim_option(f"{simulator}.vsim_flags.gui", os.environ["VCST_GUI_FLAGS"].split())
ui.main()

# Adds a cocotb module with two tests of the same name (cocotb 2.x), which VCST refuses
import os
from pathlib import Path

from vcst import VCST

root = Path(os.path.abspath(Path(__file__).parent))

ui = VCST.from_argv(compile_builtins=False)
lib = ui.add_library("lib")
lib.add_source_files(root / "hdl" / "*.vhd", vhdl_standard="2008")
ui.add_cocotb_testbench(root / "cocotb2" / "test_duplicate_names")
ui.main()

# Adds two cocotb modules with the same file name in different directories, for different top levels
import os
from pathlib import Path

from vcst import VCST

root = Path(os.path.abspath(Path(__file__).parent)) / "same_names"

ui = VCST.from_argv(compile_builtins=False)
lib = ui.add_library("lib")
lib.add_source_files(root / "hdl" / "*.vhd", vhdl_standard="2008")
ui.add_cocotb_testbench(root / "dir1" / "test_same")
ui.add_cocotb_testbench(root / "dir2" / "test_same")
ui.main()

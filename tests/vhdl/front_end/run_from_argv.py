#Adds the VHDL builtins explicitly, as VUnit 5 requires, rather than letting VCST add them
from pathlib import Path
import os
from vcst import VCST
from vcst.utils.compat import COCOTB2

root = Path(os.path.abspath(Path(__file__).parent))
cocotb_tests = root / ("cocotb2" if COCOTB2 else "cocotb1")

ui = VCST.from_argv(compile_builtins=False)
ui.add_vhdl_builtins()
lib = ui.add_library("lib")
lib.add_source_files(root / "hdl" / "*.vhd", vhdl_standard="2008")
ui.add_cocotb_testbench(cocotb_tests / "test_front_end")
ui.main()

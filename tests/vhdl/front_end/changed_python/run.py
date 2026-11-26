# Two cocotb test benches whose tests use the same Python package, to see which tests --changed selects when a Python
# file changes.
from pathlib import Path

from vcst import VCST

root = Path(__file__).resolve().parent
ui = VCST.from_argv(compile_builtins=False)
ui.add_library("lib").add_source_files(root / "hdl" / "*.vhd", vhdl_standard="2008")
ui.add_cocotb_testbench(root / "test_a")
ui.add_cocotb_testbench(root / "test_b")
ui.main()

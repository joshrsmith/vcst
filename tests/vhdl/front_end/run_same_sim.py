# Sets run_all_in_same_sim on a cocotb test bench, which VCST ignores with a warning, in the ways VUnit allows, turns it
# off, which is passed on, and adds a configuration afterwards, which it made VUnit drop; then runs the tests
import os
from pathlib import Path

from vcst import VCST

root = Path(os.path.abspath(Path(__file__).parent))

ui = VCST.from_argv(compile_builtins=False)
ui.add_vhdl_builtins()
lib = ui.add_library("lib")
lib.add_source_files(root / "hdl" / "*.vhd", vhdl_standard="2008")
test_bench = ui.add_cocotb_testbench(root / "test_front_end")

test_bench.set_attribute("run_all_in_same_sim", None)
test_bench.set_attribute("run_all_in_same_sim", True)
test_bench.add_config(name="same_sim", attributes={"run_all_in_same_sim": None})
test_bench.add_config(name="after")
ui.main()

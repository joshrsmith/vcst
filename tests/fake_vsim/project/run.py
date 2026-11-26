# Runs the tests of this directory, to be run with the fake simulators of check.py
import os
from pathlib import Path

from vcst import VCST
from vcst.utils.compat import COCOTB2

root = Path(os.path.abspath(Path(__file__).parent))
cocotb_tests = root / ("cocotb2" if COCOTB2 else "cocotb1")

ui = VCST.from_argv(compile_builtins=False)
lib = ui.add_library("lib")
lib.add_source_files(root / "hdl" / "*.vhd", vhdl_standard="2008")
lib.add_source_files(root / "hdl" / "*.sv")

names = ui.add_cocotb_testbench(cocotb_tests / "test_names")
names.add_config(
    name="generics",
    generics={
        "WIDTH": 16,
        "LABEL": "hello",
        "FILE_NAME": "data/file.txt",
        "INIT": 'x"00FF"',
        "BIT": "'1'",
        "MODE": "FAST",
        "MODES": ["SLOW", "FAST"],
        "MORE_MODES": "(FAST,SLOW)",
        "ADDRS": ['x"0000"', 'X"0100"', '16x"ab"'],
    },
)
verilog = ui.add_cocotb_testbench(root / "test_verilog")
verilog.add_config(name="parameters", generics={"NAME": "hello", "COUNT": 3})

# Flags used instead of vsim_flags in GUI mode, which check.py looks for
simulator = os.environ.get("VUNIT_SIMULATOR")
if simulator in ("rivierapro", "modelsim"):
    ui.set_sim_option(f"{simulator}.vsim_flags.gui", ["-fake_gui_flag"])
ui.main()

#Runs cocotb tests of a Verilog top level. Needs a simulator with Verilog support, so it isn't run in CI.
from pathlib import Path
import os
import sys
from vcst import VCST
from vcst.utils.compat import COCOTB2

root = Path(os.path.abspath(Path(__file__).parent))
#Tests written for the installed version of cocotb
cocotb_tests = root / ("cocotb2" if COCOTB2 else "cocotb1")

ui = VCST.from_argv(compile_builtins=False)

#GHDL and NVC are VHDL simulators, and VCST loads cocotb on ModelSim/Questa through FLI, which supports VHDL only
if ui.get_simulator_name() != "rivierapro":
    sys.exit(f"The Verilog tests need Riviera-PRO, not {ui.get_simulator_name()}")

lib = ui.add_library("lib")
lib.add_source_files(root / "hdl" / "*.sv")

params = ui.add_cocotb_testbench(cocotb_tests / "test_params")
params.add_config(name="defaults")
params.add_config(name="hello", generics={"WIDTH": 16, "NAME": "hello"})
params.add_config(name="path", generics={"WIDTH": 4, "NAME": "data/file.txt"})

ui.main()

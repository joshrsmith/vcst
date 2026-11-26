# Runs cocotb tests of a Verilog top level with an integer and a string parameter, checking that the parameters of each
# configuration reach the simulation. Needs Riviera-PRO, as the other simulators VCST supports are VHDL only, so it
# isn't run in CI.
import os
import sys
from pathlib import Path

from vcst import VCST

root = Path(os.path.abspath(Path(__file__).parent))

ui = VCST.from_argv(compile_builtins=False)

# GHDL and NVC are VHDL simulators, and VCST loads cocotb on ModelSim/Questa through FLI, which supports VHDL only
if ui.get_simulator_name() != "rivierapro":
    sys.exit(f"The Verilog tests need Riviera-PRO, not {ui.get_simulator_name()}")

lib = ui.add_library("lib")
lib.add_source_files(root / "hdl" / "*.sv")

params = ui.add_cocotb_testbench(root / "test_params")
params.add_config(name="defaults")
params.add_config(name="hello", generics={"WIDTH": 16, "NAME": "hello"})
params.add_config(name="path", generics={"WIDTH": 4, "NAME": "data/file.txt"})

ui.main()

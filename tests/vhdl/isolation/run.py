#Runs the tests of two top levels in several configurations, best with -p, each test checking that it simulates with
#its own environment and the one set by the user.
from pathlib import Path
import os
import sys
from vcst import VCST
from vcst.utils.compat import COCOTB2

root = Path(os.path.abspath(Path(__file__).parent))
cocotb_tests = root / ("cocotb2" if COCOTB2 else "cocotb1")

#Environment of the user, which the simulations must keep. The PYTHONPATH also needs to be in sys.path, as VCST
#imports the cocotb modules here too.
python_path = [str(root / "python_path")] + ([os.environ["PYTHONPATH"]] if "PYTHONPATH" in os.environ else [])
os.environ["PYTHONPATH"] = os.pathsep.join(python_path)
sys.path.append(str(root / "python_path"))
os.environ["COCOTB_RESOLVE_X"] = "VALUE_ERROR"
os.environ["VCST_ISOLATION_USER_VARIABLE"] = "kept"

ui = VCST.from_argv(compile_builtins=False)
lib = ui.add_library("lib")
lib.add_source_files(root / "hdl" / "*.vhd", vhdl_standard="2008")

for top_level in ("iso_a", "iso_b"):
    test_bench = ui.add_cocotb_testbench(cocotb_tests / f"test_{top_level}")
    for id in range(4):
        test_bench.add_config(name=f"id_{id}", generics={"ID": id})

ui.main()

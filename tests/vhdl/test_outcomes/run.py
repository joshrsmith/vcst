#Runs tests with known outcomes, including failures, and passes only if every test has its expected outcome.
from pathlib import Path
import os
import sys
from vcst import VCST
from vcst.utils.compat import COCOTB2
from vcst.utils.mod_utils import import_mod
from vunit.test.suites import TestRun

root = Path(os.path.abspath(Path(__file__).parent))
sys.path.append(str(root.parent / "common"))
from expected_outcomes import main_checking_outcomes

#Tests written for the installed version of cocotb
cocotb_tests = root / ("cocotb2" if COCOTB2 else "cocotb1")
#VUnit 5 gives every test a seed, which it passes to pre_config
VUNIT_HAS_SEEDS = hasattr(TestRun, "get_seed")

ui = VCST.from_argv(compile_builtins=False)
lib = ui.add_library("lib")
lib.add_source_files(root / "hdl" / "*.vhd", vhdl_standard="2008")

#The outcomes are expected by the cocotb module, as they depend on the cocotb version
outcomes = import_mod(str(cocotb_tests / "test_outcomes"))
ui.add_cocotb_testbench(cocotb_tests / "test_outcomes", cocotb_module=outcomes)
expected = {f"lib.outcomes_dut.{name}": outcome for name, outcome in outcomes.EXPECTED_OUTCOMES.items()}

def pre_config(output_path, seed=None):
    (Path(output_path) / "pre_config.txt").write_text(str(seed))
    return seed is not None if VUNIT_HAS_SEEDS else True

def post_check(output_path):
    return (Path(output_path) / "pre_config.txt").exists()

hooks = ui.add_cocotb_testbench(root / "test_hooks")
hooks.add_config(name="hooks_pass", pre_config=pre_config, post_check=post_check)
hooks.add_config(name="pre_config_fails", pre_config=lambda: False)
hooks.add_config(name="post_check_fails", post_check=lambda: False)
expected.update({
    "lib.hooks_dut.hooks_pass.hooked": "passed",
    "lib.hooks_dut.pre_config_fails.hooked": "failed",
    "lib.hooks_dut.post_check_fails.hooked": "failed",
})

main_checking_outcomes(ui, expected)

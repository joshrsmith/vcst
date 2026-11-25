"""
Checks that a cocotb test simulates with the environment of its own test, while tests of other modules, top levels
and configurations simulate at the same time.

This module is only found through the PYTHONPATH set by run.py, so importing it checks that VCST keeps it.
"""
import os


def check_environment(dut, module_name, top_level, cocotb2):
    """Checks the environment of a test of module_name, with top level top_level, in configuration id_<ID generic>."""
    if cocotb2:
        module_variable, top_level_variable = "COCOTB_TEST_MODULES", "COCOTB_TOPLEVEL"
    else:
        module_variable, top_level_variable = "MODULE", "TOPLEVEL"
    assert os.environ[module_variable] == module_name, f"{module_variable}={os.environ[module_variable]}"
    assert os.environ[top_level_variable].lower() == top_level, f"{top_level_variable}={os.environ[top_level_variable]}"
    assert dut._name.lower() == top_level, f"top level is {dut._name}"

    # VUnit names the output directory of a test after the test, including its configuration
    results_file = os.environ["COCOTB_RESULTS_FILE"]
    own_test = f"lib.{top_level}.id_{int(dut.ID.value)}."
    assert own_test in results_file, f"COCOTB_RESULTS_FILE={results_file} is not in the output of {own_test}*"

    # Set by the user, so VCST must leave them as they are
    assert os.environ["COCOTB_RESOLVE_X"] == "VALUE_ERROR", f"COCOTB_RESOLVE_X={os.environ['COCOTB_RESOLVE_X']}"
    assert os.environ["VCST_ISOLATION_USER_VARIABLE"] == "kept"

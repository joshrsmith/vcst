"""
Helpers giving what VCST needs from cocotb (1.8 and 1.9).
"""
import os
import sys

import cocotb.config as cocotb_config
from cocotb.decorators import test as _CocotbTest

class CocotbTestName:
    """
    The names of a cocotb test. name is the name used to select the test, which is also the name of the VUnit test,
    and result_name the name of the test in the cocotb results file.
    """
    def __init__(self, name, result_name=None):
        self.name = name
        self.result_name = name if result_name is None else result_name

def find_cocotb_tests(module):
    """
    Returns (test_object, test_names) for every module level object which cocotb would run as test(s), in definition
    order. test_object is the object found in the module, test_names the CocotbTestNames of the tests it expands to.
    """
    found = []
    for attr_name, obj in vars(module).items():
        if isinstance(obj, _CocotbTest):
            # cocotb selects tests by their name in the module, but reports them by their __qualname__
            found.append((obj, [CocotbTestName(attr_name, obj.__qualname__)]))
    return found

def test_selection_environ(module_name, test_names, top_level, seed):
    """
    Returns the environment variables selecting the module, tests (names used to select tests), top level and
    random seed (None to let cocotb choose) of a cocotb run.
    """
    environ = {
        "MODULE": module_name,
        # cocotb looks up these names in the module, so only these tests run
        "TESTCASE": ",".join(test_names),
        "TOPLEVEL": top_level,
    }
    if "COCOTB_RESOLVE_X" not in os.environ:
        # Resolve X and Z to 0 rather than failing when reading values, as done by VCST since the beginning
        environ["COCOTB_RESOLVE_X"] = "ZEROS"
    if seed is not None:
        environ["RANDOM_SEED"] = str(seed)
    return environ

def seed_variable():
    """Returns the name of the environment variable a user sets to choose the cocotb random seed."""
    return "RANDOM_SEED"

def gpi_environ(environ):
    """
    Returns the environment variables needed by the GPI to embed the Python interpreter running VCST.
    Variables already present in environ are respected.
    """
    gpi_env = {"PYGPI_PYTHON_BIN": sys.executable}
    if "VIRTUAL_ENV" not in environ and sys.prefix != sys.base_prefix:
        # cocotb finds the Python interpreter of a virtual environment only through VIRTUAL_ENV, which is not set when
        # the interpreter of the virtual environment is run without activating it
        gpi_env["VIRTUAL_ENV"] = sys.prefix

    libpython = environ.get("LIBPYTHON_LOC")
    if libpython is None:
        import find_libpython  # A cocotb dependency
        libpython = find_libpython.find_libpython()
        if libpython is None:
            raise RuntimeError("Unable to find libpython, please make sure the appropriate libpython is installed")
    gpi_env["LIBPYTHON_LOC"] = libpython

    return gpi_env

def gpi_lib(interface, simulator):
    """
    Returns the cocotb GPI library to load for a cocotb simulator name and interface (vpi, vhpi or fli).
    """
    return str(cocotb_config.lib_name_path(interface, simulator)).replace("\\", "/")

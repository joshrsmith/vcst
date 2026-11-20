"""
Helpers hiding the differences between the supported versions of cocotb (1.8 and later).
"""
import os
import re
import sys

import cocotb

#: The major and minor version of the cocotb installed
COCOTB_VERSION = tuple(int(part) for part in re.findall(r"\d+", cocotb.__version__)[:2])
#: True when the cocotb installed is 2.0 or later
COCOTB2 = COCOTB_VERSION >= (2, 0)

if COCOTB2:
    import cocotb.triggers  # cocotb 2.0 fails to import cocotb.regression first because of a circular import
    import cocotb.regression
    import cocotb_tools.config as cocotb_config

    # cocotb 2.0 calls the object created by @cocotb.parametrize Parameterized, cocotb 2.1 calls it TestGenerator
    # and also uses it for unparameterized tests.
    _TEST_GENERATOR_TYPES = tuple(
        getattr(cocotb.regression, name) for name in ("TestGenerator", "Parameterized") if hasattr(cocotb.regression, name)
    )
else:
    import cocotb.config as cocotb_config
    from cocotb.decorators import test as _Cocotb1Test

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
        if COCOTB2:
            if isinstance(obj, cocotb.regression.Test):
                found.append((obj, [CocotbTestName(obj.name)]))
            elif isinstance(obj, _TEST_GENERATOR_TYPES):
                found.append((obj, [CocotbTestName(test.name) for test in obj.generate_tests()]))
        elif isinstance(obj, _Cocotb1Test):
            # cocotb 1.x selects tests by their name in the module, but reports them by their __qualname__
            found.append((obj, [CocotbTestName(attr_name, obj.__qualname__)]))
    return found

def test_selection_environ(module_name, test_names, top_level, seed):
    """
    Returns the environment variables selecting the module, tests (names used to select tests), top level and
    random seed (None to let cocotb choose) of a cocotb run.
    """
    if COCOTB2:
        environ = {
            "COCOTB_TEST_MODULES": module_name,
            "COCOTB_TEST_FILTER": "|".join(
                f"^{re.escape(module_name)}\\.{re.escape(name)}$" for name in test_names
            ),
            "COCOTB_TOPLEVEL": top_level,
        }
        if seed is not None:
            environ["COCOTB_RANDOM_SEED"] = str(seed)
    else:
        environ = {
            "MODULE": module_name,
            # cocotb 1.x looks up these names in the module, so only these tests run
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
    return "COCOTB_RANDOM_SEED" if COCOTB2 else "RANDOM_SEED"

def gpi_environ(environ):
    """
    Returns the environment variables needed by the GPI to embed the Python interpreter running VCST.
    Variables already present in environ are respected.
    """
    gpi_env = {"PYGPI_PYTHON_BIN": sys.executable}
    if not COCOTB2 and "VIRTUAL_ENV" not in environ and sys.prefix != sys.base_prefix:
        # cocotb 1.x finds the Python interpreter of a virtual environment only through VIRTUAL_ENV, which is not set
        # when the interpreter of the virtual environment is run without activating it
        gpi_env["VIRTUAL_ENV"] = sys.prefix
    has_pygpi_entry_point = hasattr(cocotb_config, "pygpi_entry_point")

    if has_pygpi_entry_point and "GPI_USERS" in environ:
        return gpi_env

    libpython = environ.get("LIBPYTHON_LOC")
    if libpython is None:
        import find_libpython  # A cocotb dependency
        libpython = find_libpython.find_libpython()
        if libpython is None:
            raise RuntimeError("Unable to find libpython, please make sure the appropriate libpython is installed")

    if has_pygpi_entry_point:
        # cocotb 2.1 and later
        gpi_env["GPI_USERS"] = f"{libpython};{cocotb_config.pygpi_entry_point()}"
    else:
        gpi_env["LIBPYTHON_LOC"] = libpython

    return gpi_env

def gpi_lib(interface, simulator):
    """
    Returns the cocotb GPI library to load for a cocotb simulator name and interface (vpi, vhpi or fli), including
    the entry function where the simulator needs it.
    """
    if hasattr(cocotb_config, "lib_entry"):
        return cocotb_config.lib_entry(interface, simulator)
    return str(cocotb_config.lib_name_path(interface, simulator)).replace("\\", "/")

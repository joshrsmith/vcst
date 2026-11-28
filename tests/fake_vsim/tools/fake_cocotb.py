"""
Stand-in for cocotb in a fake simulation: checks what a cocotb simulation needs and reports the selected tests as
passed, or failed with the problems found. Run with the Python interpreter given to the simulation
(PYGPI_PYTHON_BIN) and the arguments of the vsim command loading the design.
"""

import importlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

load_args = sys.argv[1:]
env = os.environ
problems = []
flavor = env.get("FAKE_FLAVOR", "rivierapro")


def check(condition, problem):
    if not condition:
        problems.append(problem)


def existing_file(path, what):
    check(path and Path(path).is_file(), f"{what} {path!r} does not exist")


# cocotb version of the environment
cocotb2 = "COCOTB_TEST_MODULES" in env
check(cocotb2 != ("MODULE" in env), "exactly one of COCOTB_TEST_MODULES and MODULE must be set")


# The GPI library loaded by the simulator
def flag_value(flag):
    return load_args[load_args.index(flag) + 1] if flag in load_args else None


# The language of the top level, from the design loaded (the project's Verilog top level is verilog_dut), rather than
# from TOPLEVEL_LANG, which VCST sets and which is checked against it
language = "verilog" if any("verilog_dut" in arg for arg in load_args) else "vhdl"
check(
    env.get("TOPLEVEL_LANG") == language,
    f"TOPLEVEL_LANG={env.get('TOPLEVEL_LANG')!r} for a {language} top level",
)
if flavor == "rivierapro":
    flag = "-loadvhpi" if language == "vhdl" else "-pli"
    library = flag_value(flag)
    check(library is not None, f"{flag} not given to vsim: {load_args}")
    if library:
        path, _, entry = library.partition(":")
        existing_file(path, "GPI library")
        import cocotb

        version = tuple(int(part) for part in re.findall(r"\d+", cocotb.__version__)[:2])
        if version >= (2, 1) and language == "vhdl":
            check(
                entry == "vhpi_startup_routines_bootstrap",
                f"VHPI entry point {entry!r} given with cocotb 2.1",
            )
    for access in ("+access", "+w"):
        check(access in load_args, f"{access} not given to vsim")
elif language == "vhdl":
    foreign = flag_value("-foreign")
    check(
        foreign is not None and foreign.startswith("cocotb_init "),
        f"-foreign cocotb_init not given: {load_args}",
    )
    if foreign:
        existing_file(foreign.split(" ", 1)[1], "FLI library")
else:
    # FLI supports VHDL only, so a Verilog top level loads the VPI library
    check("-foreign" not in load_args, f"-foreign (FLI) given for a Verilog top level: {load_args}")
    library = flag_value("-pli")
    check(library is not None, f"-pli not given to vsim: {load_args}")
    existing_file(library and library.strip("{}"), "VPI library")
if flavor == "modelsim":
    # Access to the signals inside the design, which Questa's optimization would remove otherwise
    check(
        "-voptargs=-access=rw+/." in load_args,
        f"-voptargs=-access=rw+/. not given to vsim: {load_args}",
    )

# The Python interpreter and library embedded by the GPI
existing_file(env.get("PYGPI_PYTHON_BIN"), "PYGPI_PYTHON_BIN")
if "GPI_USERS" in env:
    users = env["GPI_USERS"].split(";")
    check(
        len(users) == 2,
        f"GPI_USERS={env['GPI_USERS']!r} should give libpython and the pygpi entry point",
    )
    existing_file(users[0], "libpython in GPI_USERS")
    existing_file(users[-1].rsplit(",", 1)[0], "pygpi entry point in GPI_USERS")
else:
    existing_file(env.get("LIBPYTHON_LOC"), "LIBPYTHON_LOC")

# cocotb 1.x finds the Python interpreter of a virtual environment only through VIRTUAL_ENV
if not cocotb2 and sys.prefix != sys.base_prefix:
    check(
        env.get("VIRTUAL_ENV") == sys.prefix,
        f"VIRTUAL_ENV={env.get('VIRTUAL_ENV')!r}, but the interpreter is in {sys.prefix}",
    )

# The top level
top_level = env.get("COCOTB_TOPLEVEL" if cocotb2 else "TOPLEVEL", "")
check(
    top_level and any(top_level.lower() in arg.lower() for arg in load_args),
    f"top level {top_level!r} is not loaded: {load_args}",
)

# ModelSim/Questa names the root of a VHDL design in lower case, and cocotb looks it up by the name it is given
if flavor == "modelsim" and language == "vhdl":
    check(top_level == top_level.lower(), f"top level {top_level!r} is not in lower case")

# cocotb 2.x refuses to run when both are set
if cocotb2:
    check("COCOTB_TESTCASE" not in env, "COCOTB_TESTCASE is set as well as COCOTB_TEST_FILTER")

# The tests selected, as cocotb selects them
module_name = env.get("COCOTB_TEST_MODULES" if cocotb2 else "MODULE", "")
selected = []
try:
    module = importlib.import_module(module_name)
    if cocotb2:
        # isort: off
        import cocotb.triggers  # cocotb 2.0 can't import cocotb.regression first
        import cocotb.regression

        # isort: on

        generators = tuple(
            getattr(cocotb.regression, n)
            for n in ("TestGenerator", "Parameterized")
            if hasattr(cocotb.regression, n)
        )
        tests = []
        for obj in vars(module).values():
            if isinstance(obj, cocotb.regression.Test):
                tests.append(obj)
            elif isinstance(obj, generators):
                tests.extend(obj.generate_tests())
        test_filter = re.compile(env.get("COCOTB_TEST_FILTER", ""))
        selected = [test.name for test in tests if test_filter.search(test.fullname)]
    else:
        from cocotb.decorators import test as Test

        for name in env.get("TESTCASE", "").split(","):
            test = getattr(module, name, None)
            check(isinstance(test, Test), f"TESTCASE {name!r} is not a test of {module_name}")
            if isinstance(test, Test):
                selected.append(test.__qualname__)
except Exception as exc:  # pylint: disable=broad-except
    check(False, f"cocotb would fail to find the tests: {exc!r}")
check(len(selected) == 1, f"one test should be selected, {selected} were")

# The results, as cocotb writes them
log = env.get("FAKE_LOG")
if log:
    with open(log, "a") as f:
        f.write(
            json.dumps(
                {
                    "load": load_args,
                    "env": {
                        k: v
                        for k, v in env.items()
                        if "COCOTB" in k
                        or k
                        in (
                            "MODULE",
                            "TESTCASE",
                            "TOPLEVEL",
                            "TOPLEVEL_LANG",
                            "RANDOM_SEED",
                            "GPI_USERS",
                            "LIBPYTHON_LOC",
                            "PYGPI_PYTHON_BIN",
                            "VIRTUAL_ENV",
                        )
                    },
                    "selected": selected,
                    "problems": problems,
                }
            )
            + "\n"
        )
root = ET.Element("testsuites")
suite = ET.SubElement(root, "testsuite", name="all")
for name in selected or ["no_test_selected"]:
    testcase = ET.SubElement(suite, "testcase", name=name, classname=module_name)
    if problems:
        ET.SubElement(testcase, "failure", message="; ".join(problems))
ET.ElementTree(root).write(env["COCOTB_RESULTS_FILE"])
for problem in problems:
    print(f"FAKE COCOTB PROBLEM: {problem}")

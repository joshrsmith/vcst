"""
Checks the VCST command line and run script interface, which differs between VUnit 4.7 and 5, by running the run
scripts of this directory with different arguments.

Usage: python check.py [-p N] [--output-path DIR]

Runs with the simulator selected by VUNIT_SIMULATOR, like the run scripts, and exits with 1 if a check fails. The
output of the runs is written to DIR, by default a new temporary directory.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from vunit import VUnit
from vunit.test.suites import TestRun

from vcst.utils.compat import COCOTB2, COCOTB_SUPPORTS_NVC

ROOT = Path(__file__).resolve().parent
# VUnit 5 gives every test a seed, see --seed
VUNIT_HAS_SEEDS = hasattr(TestRun, "get_seed")

ALL_TESTS = {
    "lib.tb_front_end.vhdl_test",
    "lib.front_end_dut.tagged",
    "lib.front_end_dut.untagged",
    "lib.front_end_dut.random_values",
}

parser = argparse.ArgumentParser(
    description="Checks the VCST command line and run script interface"
)
parser.add_argument("-p", "--num-threads", type=int, default=1, help="threads of the runs")
parser.add_argument("--output-path", type=Path, help="directory of the output of the runs")
options = parser.parse_args()

failures = []
work = options.output_path or Path(tempfile.mkdtemp(prefix="vcst_front_end_"))
work.mkdir(parents=True, exist_ok=True)
parallel = ["-p", str(options.num_threads)]


def run(name, script, *args, env=None):
    """
    Runs a run script, returns (exit code, output, {test name: (outcome, output)} from its xunit report). env gives
    environment variables to set, or to remove with the value None.
    """
    output_path = work / name
    xunit = output_path / "xunit.xml"
    # Not to read the report of an earlier check with the same output path
    xunit.unlink(missing_ok=True)
    command = [
        sys.executable,
        str(ROOT / script),
        "--output-path",
        str(output_path),
        "--xunit-xml",
        str(xunit),
        *parallel,
        *args,
    ]
    run_env = {**os.environ, **(env or {})}
    run_env = {key: value for key, value in run_env.items() if value is not None}
    proc = subprocess.run(command, capture_output=True, text=True, env=run_env, check=False)
    tests = {}
    if xunit.exists():
        for testcase in ET.parse(xunit).getroot().iter("testcase"):
            tags = {child.tag for child in testcase}
            outcome = (
                "failed"
                if tags & {"failure", "error"}
                else "skipped"
                if "skipped" in tags
                else "passed"
            )
            system_out = testcase.find("system-out")
            tests[f"{testcase.get('classname')}.{testcase.get('name')}"] = (
                outcome,
                system_out.text if system_out is not None else "",
            )
    return proc.returncode, proc.stdout + proc.stderr, tests


def check(description, condition, details=""):
    print(f"{'pass' if condition else 'FAIL'} {description}")
    if not condition:
        failures.append(description)
        if details:
            print(details[-3000:])


def random_values(tests):
    """Returns the cocotb random seed and first random value logged by the random_values test, None if not run."""
    output = tests.get("lib.front_end_dut.random_values", ("", ""))[1] or ""
    match = re.search(r"VCST_RANDOM_SEED=(\S+) VCST_RANDOM_VALUE=(\S+)", output)
    return match.groups() if match else None


if os.environ.get("VUNIT_SIMULATOR") == "nvc" and not COCOTB_SUPPORTS_NVC:
    # Nothing runs, but the reason is given
    rc, output, tests = run("nvc_unsupported", "run_from_argv.py")
    check(
        "NVC with cocotb before 1.9 is refused with a clear error",
        rc != 0 and "NVC needs cocotb 1.9 or later" in output and not tests,
        output,
    )
    sys.exit(1 if failures else 0)

# Adding the VHDL builtins explicitly after from_argv(compile_builtins=False)
rc, output, tests = run("from_argv", "run_from_argv.py")
check(
    "from_argv(compile_builtins=False) and add_vhdl_builtins(): all tests pass",
    rc == 0 and set(tests) == ALL_TESTS and all(o == "passed" for o, _ in tests.values()),
    output,
)

# VUnitCLI with an argument of its own, from_args and adding the builtins again
rc, output, tests = run("from_args", "run_from_args.py", "--require-custom")
check(
    "VUnitCLI, from_args and add_vhdl_builtins(): all tests pass",
    rc == 0 and set(tests) == ALL_TESTS and all(o == "passed" for o, _ in tests.values()),
    output,
)

# Arguments VUnit doesn't know are rejected, also with VUnit 5 which parses them again when selecting the simulator
rc, output, tests = run("unknown_option", "run_from_argv.py", "--no-such-option")
check(
    "an unknown option is rejected",
    rc != 0 and "unrecognized arguments" in output and not tests,
    output,
)

# Selecting tests by attribute
rc, output, tests = run("with_attributes", "run_from_argv.py", "--with-attributes", ".tagged")
check(
    "--with-attributes selects the tests with the attribute",
    rc == 0 and set(tests) == {"lib.front_end_dut.tagged"},
    output,
)
rc, output, tests = run("without_attributes", "run_from_argv.py", "--without-attributes", ".tagged")
check(
    "--without-attributes leaves out the tests with the attribute",
    rc == 0 and set(tests) == ALL_TESTS - {"lib.front_end_dut.tagged"},
    output,
)
rc, output, tests = run("cocotb_attribute", "run_from_argv.py", "--with-attributes", ".cocotb")
check(
    "--with-attributes .cocotb selects the cocotb tests",
    rc == 0 and set(tests) == ALL_TESTS - {"lib.tb_front_end.vhdl_test"},
    output,
)

# Modes without simulation
rc, output, _ = run("list", "run_from_argv.py", "--list")
check(
    "--list lists the cocotb tests", rc == 0 and all(name in output for name in ALL_TESTS), output
)

json_file = work / "export.json"
json_file.unlink(missing_ok=True)
rc, output, _ = run("export_json", "run_from_argv.py", "--export-json", str(json_file))
exported = {}
if json_file.exists():
    exported = {
        test["name"]: test["attributes"] for test in json.loads(json_file.read_text())["tests"]
    }
check(
    "--export-json exports the cocotb tests and their attributes",
    rc == 0
    and set(exported) == ALL_TESTS
    and ".tagged" in exported.get("lib.front_end_dut.tagged", {})
    and ".cocotb" in exported.get("lib.front_end_dut.untagged", {}),
    output,
)

rc, output, tests = run("elaborate", "run_from_argv.py", "--elaborate")
check("--elaborate elaborates all tests", rc == 0 and set(tests) == ALL_TESTS, output)

# Running the Python interpreter of a virtual environment without activating it
if sys.prefix != sys.base_prefix:
    rc, output, tests = run(
        "venv_not_activated",
        "run_from_argv.py",
        "lib.front_end_dut.untagged",
        env={"VIRTUAL_ENV": None},
    )
    check(
        "the virtual environment is used without activating it",
        rc == 0 and tests.get("lib.front_end_dut.untagged", ("",))[0] == "passed",
        output,
    )
else:
    print("skip check of an unactivated virtual environment: not run in a virtual environment")

# cocotb 2.x refuses to run if COCOTB_TESTCASE is set as well as COCOTB_TEST_FILTER, which VCST selects tests with
if COCOTB2:
    rc, output, tests = run(
        "cocotb_testcase",
        "run_from_argv.py",
        "lib.front_end_dut.untagged",
        env={"COCOTB_TESTCASE": "tagged"},
    )
    check(
        "a COCOTB_TESTCASE set by the user doesn't change which test runs",
        rc == 0 and tests.get("lib.front_end_dut.untagged", ("",))[0] == "passed",
        output,
    )

# Tests with the same name, which cocotb 2.x allows
if COCOTB2:
    rc, output, tests = run("duplicate_names", "run_duplicate_names.py")
    check(
        "cocotb tests with the same name are refused with a clear error",
        rc != 0 and "tests named 'duplicate'" in output and not tests,
        output,
    )

# Modules with the same file name in different directories are different modules
rc, output, tests = run("same_names", "run_same_names.py")
check(
    "cocotb modules with the same file name in different directories both run",
    rc == 0
    and {name: result[0] for name, result in tests.items()}
    == {"lib.dut_a.test_one": "passed", "lib.dut_b.test_two": "passed"},
    output,
)

# One cocotb module can be added for a top level
rc, output, tests = run("two_modules", "run_two_modules.py")
check(
    "a second cocotb module for a top level is refused with a clear error",
    rc != 0 and "has the cocotb module" in output and "test_other" in output and not tests,
    output,
)

# Random seeds
seed_variable = "COCOTB_RANDOM_SEED" if COCOTB2 else "RANDOM_SEED"
_, output, tests = run(
    "user_seed", "run_from_argv.py", "lib.front_end_dut.random_values", env={seed_variable: "12345"}
)
# cocotb.RANDOM_SEED itself is derived from the test name within tests with cocotb 2.1, so check what cocotb seeds with
test_output = tests.get("lib.front_end_dut.random_values", ("", ""))[1] or ""
check(
    f"a seed set with {seed_variable} is used by cocotb",
    re.search(r"Seeding Python random module with (supplied seed )?12345\b", test_output)
    is not None,
    output,
)

if VUNIT_HAS_SEEDS:
    results = []
    seeds = (
        ("seed_a", "0123456789abcdef"),
        ("seed_a_again", "0123456789abcdef"),
        ("seed_b", "fedcba9876543210"),
    )
    for name, seed in seeds:
        _, output, tests = run(
            name, "run_from_argv.py", "--seed", seed, "lib.front_end_dut.random_values"
        )
        results.append(random_values(tests))
    check(
        "the same VUnit --seed gives the same cocotb random values",
        results[0] is not None and results[0] == results[1],
        str(results),
    )
    check(
        "a different VUnit --seed gives different cocotb random values",
        results[0] is not None and results[2] is not None and results[0][1] != results[2][1],
        str(results),
    )
    test_output = tests.get("lib.front_end_dut.random_values", ("", ""))[1] or ""
    check(
        "the VUnit seed of a cocotb test is printed, as for VUnit tests",
        "Seed for lib.front_end_dut.random_values: fedcba9876543210" in test_output,
        output,
    )

    # The seed simulation option can be any string
    results = []
    for name, seed in (
        ("seed_option_a", "any seed"),
        ("seed_option_a_again", "any seed"),
        ("seed_option_b", "other"),
    ):
        _, output, tests = run(
            name,
            "run_from_args.py",
            "--require-custom",
            "--seed-option",
            seed,
            "lib.front_end_dut.random_values",
        )
        results.append(random_values(tests))
    check(
        "the same seed simulation option gives the same cocotb random values",
        results[0] is not None and results[0] == results[1],
        str(results),
    )
    check(
        "a different seed simulation option gives different cocotb random values",
        results[0] is not None and results[2] is not None and results[0][1] != results[2][1],
        str(results),
    )
    # A decimal seed, e.g. one reported by cocotb, is given to cocotb as it is
    _, output, tests = run(
        "seed_option_decimal",
        "run_from_args.py",
        "--require-custom",
        "--seed-option",
        "12345",
        "lib.front_end_dut.random_values",
    )
    test_output = tests.get("lib.front_end_dut.random_values", ("", ""))[1] or ""
    check(
        "a decimal seed simulation option is the cocotb seed",
        re.search(r"Seeding Python random module with (supplied seed )?12345\b", test_output)
        is not None,
        output,
    )

    # --seed repeat repeats the seeds of the previous run, kept by VUnit in the output path
    _, output, tests = run("seed_repeat", "run_from_argv.py", "lib.front_end_dut.random_values")
    first = random_values(tests)
    _, output, tests = run(
        "seed_repeat", "run_from_argv.py", "--seed", "repeat", "lib.front_end_dut.random_values"
    )
    check(
        "--seed repeat gives the cocotb random values of the previous run",
        first is not None and random_values(tests) == first,
        f"{first} {random_values(tests)}\n{output}",
    )
else:
    print("skip --seed checks: VUnit before 5 has no --seed")

# --changed (VUnit 5) selects the tests whose HDL or Python files changed since they last ran
if hasattr(VUnit, "_get_test_list_depending_on_change"):
    project = work / "changed_python"
    shutil.rmtree(project, ignore_errors=True)
    shutil.copytree(ROOT / "changed_python", project, ignore=shutil.ignore_patterns("__pycache__"))
    changed_script = str(project / "run.py")
    test_a, test_b = "lib.changed_a.a_test", "lib.changed_b.b_test"

    def changed_selected():
        """The tests --changed selects"""
        _, output, _ = run("changed", changed_script, "--changed", "--list")
        return {line for line in output.splitlines() if line.startswith("lib.")}, output

    def modify(path):
        # Modified after the tests last ran, which was at least a second ago
        os.utime(project / path, None)

    rc, output, tests = run("changed", changed_script)
    check(
        "changed: both tests pass in the first run",
        rc == 0 and set(tests) == {test_a, test_b},
        output,
    )
    selected, output = changed_selected()
    check("--changed selects nothing when nothing has changed", selected == set(), output)

    # As in VUnit, the run script isn't something the tests depend on
    modify("run.py")
    selected, output = changed_selected()
    check("--changed selects nothing when only the run script changed", selected == set(), output)

    modify("test_a.py")
    selected, output = changed_selected()
    check(
        "--changed selects the tests of a cocotb module whose file changed, and no others",
        selected == {test_a},
        output,
    )
    _, output, tests = run("changed", changed_script, "--changed")
    selected, _ = changed_selected()
    check(
        "--changed runs them, and then selects nothing",
        set(tests) == {test_a} and selected == set(),
        output,
    )

    modify("driver/regs.py")
    selected, output = changed_selected()
    check(
        "--changed selects the tests of all cocotb modules when a Python file they import changed",
        selected == {test_a, test_b},
        output,
    )
    _, output, tests = run("changed", changed_script, "--changed")
    selected, _ = changed_selected()
    check(
        "--changed runs them, and then selects nothing again",
        set(tests) == {test_a, test_b} and selected == set(),
        output,
    )

    with (project / "hdl" / "changed_duts.vhd").open("a") as hdl:
        hdl.write("-- changed\n")
    selected, output = changed_selected()
    check(
        "--changed still selects the tests of an HDL file that changed",
        selected == {test_a, test_b},
        output,
    )
else:
    print("skip --changed checks: VUnit before 5 has no --changed")

print("=" * 70)
if failures:
    print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("All checks passed.")

"""
Runs the tests of project/ with Riviera-PRO and ModelSim/Questa replaced by fake simulators (tools/), checking that
VCST, through VUnit's interfaces to these simulators, gives a cocotb simulation what it needs, both when the simulator
process is reused for several tests (VUnit's default) and when every test has a process of its own, and in GUI mode with
vsim_flags.gui set, and that ModelSim/Questa elaborates without the cocotb library (--elaborate). The fake simulators
run the tcl VUnit sends to the simulator with tclsh, and the checks cover what the cocotb simulation gets: the cocotb
library and its loading, the Python environment, the top level, the selected test and the generics, and that VUnit's run
script finds the test suite done. This doesn't show that the real simulators work with cocotb, but needs neither of
them.

Usage: python check.py [-p N] [--output-path DIR]

N is the number of threads of the runs with several threads (default 3). The output of the runs is written to DIR, by
default a new temporary directory which is removed if all checks pass.

Needs tclsh. Exits with 1 if a check fails.
"""

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOOLS = ROOT / "tools"
failures = []


def create_fake_simulator(directory, flavor):
    """Creates the installation of a fake simulator of the flavor, returns the directory of its executables."""
    bin_dir = directory / flavor / "bin"
    bin_dir.mkdir(parents=True)
    for tool in ("vsim", "vsimsa", "vcom", "vlog", "vlib", "vmap", "vlist"):
        script = bin_dir / tool
        script.write_text(
            f'#!/bin/sh\nFAKE_FLAVOR={flavor} exec "{sys.executable}" "{TOOLS / "fake_tool.py"}" {tool} "$@"\n'
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
    if flavor == "rivierapro":
        (directory / flavor / "vlib").mkdir()
        (directory / flavor / "vlib" / "library.cfg").write_text("")
    else:
        (directory / flavor / "modelsim.ini").write_text("[Library]\n")
    return bin_dir


def simulator_env(flavor, bin_dir):
    """Returns the environment selecting the fake simulator."""
    return {**os.environ, "VUNIT_SIMULATOR": flavor, f"VUNIT_{flavor.upper()}_PATH": str(bin_dir)}


def check(description, condition, details=""):
    print(f"{'pass' if condition else 'FAIL'} {description}")
    if not condition:
        failures.append(description)
        if details:
            print(details[-4000:])


def run(work, flavor, bin_dir, name, *args):
    """
    Runs project/run.py, returns (exit code, output, {test: outcome}, log entries of the fake cocotb, output of the
    tests).
    """
    output_path = work / f"{flavor}_{name}"
    xunit = output_path / "xunit.xml"
    log = output_path / "fake.log"
    output_path.mkdir()
    # COCOTB_TESTCASE as left by running cocotb's makefiles, which VCST must not pass on to cocotb 2.x
    env = {**simulator_env(flavor, bin_dir), "FAKE_LOG": str(log), "COCOTB_TESTCASE": "plain"}
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "project" / "run.py"),
            "--output-path",
            str(output_path),
            "--xunit-xml",
            str(xunit),
            *args,
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    tests = {}
    if xunit.exists():
        for testcase in ET.parse(xunit).getroot().iter("testcase"):
            failed = any(child.tag in ("failure", "error") for child in testcase)
            tests[f"{testcase.get('classname')}.{testcase.get('name')}"] = (
                "failed" if failed else "passed"
            )
    entries = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    # The entries of the fake cocotb, leaving out those of the fake tools
    entries = [entry for entry in entries if "load" in entry]
    test_output = "".join(
        path.read_text() for path in sorted((output_path / "test_output").glob("*/output.txt"))
    )
    return proc.returncode, proc.stdout + proc.stderr, tests, entries, test_output


def main():
    parser = argparse.ArgumentParser(
        description="Checks VCST with fake Riviera-PRO and ModelSim/Questa simulators"
    )
    parser.add_argument(
        "-p", "--num-threads", type=int, default=3, help="threads of the runs with several threads"
    )
    parser.add_argument("--output-path", type=Path, help="directory of the output of the runs")
    options = parser.parse_args()
    if shutil.which("tclsh") is None:
        sys.exit("tclsh is needed to run the fake simulators")
    if options.output_path:
        work = options.output_path
        work.mkdir(parents=True, exist_ok=True)
    else:
        work = Path(tempfile.mkdtemp(prefix="vcst_fake_vsim_"))
    threads = str(options.num_threads)

    for flavor in ("rivierapro", "modelsim"):
        bin_dir = create_fake_simulator(work, flavor)

        listed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "project" / "run.py"),
                "--list",
                "--output-path",
                str(work / f"{flavor}_list"),
            ],
            capture_output=True,
            text=True,
            env=simulator_env(flavor, bin_dir),
            check=False,
        )
        all_tests = {line for line in listed.stdout.splitlines() if line.startswith("lib.")}
        check(f"{flavor}: tests are listed", len(all_tests) > 2, listed.stdout + listed.stderr)

        for name, args in (
            ("persistent_one_thread", ["-p", "1"]),
            ("persistent", ["-p", threads]),
            ("unique_sim", ["-p", threads, "--unique-sim"]),
            ("gui", ["-g"]),
        ):
            rc, output, tests, entries, test_output = run(work, flavor, bin_dir, name, *args)
            problems = [problem for entry in entries for problem in entry["problems"]]
            check(
                f"{flavor} ({name}): every test passes with what it needs",
                rc == 0
                and set(tests) == all_tests
                and all(outcome == "passed" for outcome in tests.values())
                and not problems,
                "\n".join(problems) + "\n" + output,
            )
            check(
                f"{flavor} ({name}): every test is loaded once",
                len(entries) == len(all_tests),
                output,
            )
            # VUnit's vunit_run reads VUnit's results file, and reports the run as failed unless the file says the
            # test suite is done
            check(
                f"{flavor} ({name}): VUnit's run script finds the test suite done",
                "Test Run Failed!" not in test_output and "vunit_results" not in test_output,
                test_output[-3000:],
            )
            if name == "gui":
                check(
                    f"{flavor} ({name}): the vsim_flags.gui of the user are given to vsim",
                    entries and all("-fake_gui_flag" in entry["load"] for entry in entries),
                    output,
                )
            if flavor == "rivierapro":
                # Generics of a VHDL top level are passed on as written, as VUnit does, with lists becoming aggregates.
                # Strings given to a Verilog top level are quoted.
                generic_args = {
                    arg for entry in entries for arg in entry["load"] if arg.startswith("-g/")
                }
                expected = {
                    "-g/names_dut/width=16",
                    "-g/names_dut/label=hello",
                    "-g/names_dut/file_name=data/file.txt",
                    '-g/names_dut/init=x"00FF"',
                    "-g/names_dut/bit='1'",
                    "-g/names_dut/mode=FAST",
                    "-g/names_dut/modes=(SLOW,FAST)",
                    "-g/names_dut/more_modes=(FAST,SLOW)",
                    '-g/names_dut/addrs=(x"0000",X"0100",16x"ab")',
                    '-g/verilog_dut/name="hello"',
                    "-g/verilog_dut/count=3",
                }
                check(
                    f"{flavor} ({name}): generics are formatted for VHDL and Verilog",
                    generic_args == expected,
                    str(generic_args ^ expected),
                )

        if flavor == "modelsim":
            # cocotb isn't loaded to only elaborate on ModelSim/Questa, as cocotb 2's FLI library crashes Questa when it
            # quits before a test ran
            rc, output, tests, _, test_output = run(
                work, flavor, bin_dir, "elaborate", "--elaborate"
            )
            loads = [
                line for line in test_output.splitlines() if line.startswith("FAKE_VSIM_LOAD ")
            ]
            check(
                f"{flavor} (elaborate): every design is elaborated, without the cocotb library",
                rc == 0
                and set(tests) == all_tests
                and len(loads) == len(all_tests)
                and not any("-foreign" in load or "-pli" in load for load in loads),
                "\n".join(loads) + "\n" + output,
            )

    print("=" * 70)
    if failures:
        print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
        sys.exit(1)
    print("All checks passed.")
    if not options.output_path:
        shutil.rmtree(work)


if __name__ == "__main__":
    main()

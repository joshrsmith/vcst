"""
Runs the tests of project/ with Riviera-PRO and ModelSim/Questa replaced by fake simulators (tools/), checking that
VCST, through VUnit's interfaces to these simulators, gives a cocotb simulation what it needs, both when the
simulator process is reused for several tests (VUnit's default) and when every test has a process of its own.

Usage: python check.py

Needs tclsh. Exits with 1 if a check fails.
"""
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
    """Runs project/run.py, returns (exit code, output, {test: outcome}, log entries of the fake cocotb)."""
    output_path = work / f"{flavor}_{name}"
    xunit = output_path / "xunit.xml"
    log = output_path / "fake.log"
    output_path.mkdir()
    env = {**simulator_env(flavor, bin_dir), "FAKE_LOG": str(log)}
    proc = subprocess.run([sys.executable, str(ROOT / "project" / "run.py"), "--output-path", str(output_path),
                           "--xunit-xml", str(xunit), *args], capture_output=True, text=True, env=env)
    tests = {}
    if xunit.exists():
        for testcase in ET.parse(xunit).getroot().iter("testcase"):
            failed = any(child.tag in ("failure", "error") for child in testcase)
            tests[f"{testcase.get('classname')}.{testcase.get('name')}"] = "failed" if failed else "passed"
    entries = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    #The entries of the fake cocotb, leaving out those of the fake tools
    entries = [entry for entry in entries if "load" in entry]
    return proc.returncode, proc.stdout + proc.stderr, tests, entries


def main():
    if shutil.which("tclsh") is None:
        sys.exit("tclsh is needed to run the fake simulators")
    work = Path(tempfile.mkdtemp(prefix="vcst_fake_vsim_"))

    for flavor in ("rivierapro", "modelsim"):
        bin_dir = create_fake_simulator(work, flavor)

        listed = subprocess.run([sys.executable, str(ROOT / "project" / "run.py"), "--list", "--output-path",
                                 str(work / f"{flavor}_list")], capture_output=True, text=True,
                                env=simulator_env(flavor, bin_dir))
        all_tests = {line for line in listed.stdout.splitlines() if line.startswith("lib.")}
        check(f"{flavor}: tests are listed", len(all_tests) > 2, listed.stdout + listed.stderr)

        for name, args in (("persistent_one_thread", ["-p", "1"]), ("persistent", ["-p", "3"]),
                           ("unique_sim", ["-p", "3", "--unique-sim"])):
            rc, output, tests, entries = run(work, flavor, bin_dir, name, *args)
            problems = [problem for entry in entries for problem in entry["problems"]]
            check(f"{flavor} ({name}): every test passes with what it needs", rc == 0 and set(tests) == all_tests
                  and all(outcome == "passed" for outcome in tests.values()) and not problems,
                  "\n".join(problems) + "\n" + output)
            check(f"{flavor} ({name}): every test is loaded once", len(entries) == len(all_tests), output)
            if flavor == "rivierapro":
                #Generics of a VHDL top level are passed on as written, as VUnit does, with lists becoming aggregates.
                #Strings given to a Verilog top level are quoted.
                generic_args = {arg for entry in entries for arg in entry["load"] if arg.startswith("-g/")}
                expected = {"-g/names_dut/width=16", "-g/names_dut/label=hello", "-g/names_dut/file_name=data/file.txt",
                            '-g/names_dut/init=x"00FF"', "-g/names_dut/bit='1'", "-g/names_dut/mode=FAST",
                            "-g/names_dut/modes=(SLOW,FAST)", "-g/names_dut/more_modes=(FAST,SLOW)",
                            '-g/names_dut/addrs=(x"0000",X"0100",16x"ab")', '-g/verilog_dut/name="hello"',
                            "-g/verilog_dut/count=3"}
                check(f"{flavor} ({name}): generics are formatted for VHDL and Verilog", generic_args == expected,
                      str(generic_args ^ expected))

    print("=" * 70)
    if failures:
        print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
        sys.exit(1)
    print("All checks passed.")
    shutil.rmtree(work)



if __name__ == "__main__":
    main()

"""
Runs the test suites of this repository with the supported combinations of VUnit and cocotb, on the simulator selected
by VUNIT_SIMULATOR, and reports which runs passed. CI runs it too, one combination per job, so the versions and suites
tested are listed here only.

Usage: python tests/run_matrix.py [--output DIR] [-p N] [--quick | --vunit VERSION... --cocotb VERSION...]

Every combination is installed in a virtual environment of its own, DIR/venvs/<combination>, created with the Python
running this script: the versions of VUnit and cocotb, from PyPI or the index pip is configured with, and the VCST of
this checkout. The virtual environments are kept for later runs with the same DIR, VCST being reinstalled each time.
Each run of a suite writes its VUnit output and its console output (console.log) to DIR/<combination>/<suite>-p<N>.
The results of all runs are summarized in DIR/report.md and DIR/summary.json. Exits with 1 if a run failed.
"""
import argparse
import itertools
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#The versions of VUnit and cocotb VCST supports. Each VUnit version is tested with each cocotb version.
VUNIT_VERSIONS = ["4.7.1", "5.0.0.dev16"]
COCOTB_VERSIONS = ["1.8.1", "1.9.2", "2.0.1", "2.1.0"]
#Fewer combinations, run with --quick, still covering each version. cocotb versions differ in how cocotb is loaded
#into the simulator.
QUICK = [("4.7.1", "1.8.1"), ("5.0.0.dev16", "1.9.2"), ("4.7.1", "2.0.1"), ("5.0.0.dev16", "2.1.0")]

#Simulators running all tests of a thread in one simulator process, unless --unique-sim is given
REUSING_SIMULATORS = ["rivierapro", "modelsim"]

#The simulator with which the suites not using the simulator are run by default, as CI has it
INDEPENDENT_SUITES_SIMULATOR = "ghdl"

@dataclass
class Suite:
    """A test suite, a script exiting with 0 if all of its tests had their expected outcomes"""
    name: str
    #Path relative to the tests directory
    script: str
    #Further arguments of the script
    args: list = field(default_factory=list)
    #Whether the suite is also run with one thread, besides -p N
    one_thread: bool = True
    #The simulators the suite is run with, None for all
    simulators: list = None
    #Whether the suite doesn't use the simulator selected, so that running it once is enough. It is run by default only
    #with INDEPENDENT_SUITES_SIMULATOR, so that the runs with a simulator needing a license take only what needs it, and
    #with any simulator if selected with --suite
    independent: bool = False
    #Executables the suite needs, the suite is skipped if one isn't found
    requires: list = field(default_factory=list)

SUITES = [
    Suite("cocotb_examples", "vhdl/cocotb_examples/run.py"),
    Suite("vunit_and_cocotb", "vhdl/vunit_and_cocotb/run.py"),
    Suite("parameterize_test", "vhdl/parameterize_test/run.py"),
    Suite("test_outcomes", "vhdl/test_outcomes/run.py"),
    Suite("isolation", "vhdl/isolation/run.py"),
    Suite("isolation_unique_sim", "vhdl/isolation/run.py", ["--unique-sim"], one_thread=False,
          simulators=REUSING_SIMULATORS),
    Suite("front_end", "vhdl/front_end/check.py", one_thread=False),
    #VCST loads cocotb on ModelSim/Questa through FLI, which supports VHDL only
    Suite("verilog", "verilog/run.py", simulators=["rivierapro"]),
    #Riviera-PRO and ModelSim/Questa replaced by fake simulators, which need tclsh
    Suite("fake_vsim", "fake_vsim/check.py", one_thread=False, independent=True, requires=["tclsh"]),
]

#Commands printing the version of a simulator, the executable being looked for in VUNIT_<SIMULATOR>_PATH or PATH
VERSION_COMMANDS = {
    "ghdl": ["ghdl", "--version"],
    "nvc": ["nvc", "--version"],
    "rivierapro": ["vsim", "-version"],
    "modelsim": ["vsim", "-version"],
}

def unsupported(simulator, cocotb):
    """Returns why the cocotb version can't be used with the simulator, None if it can"""
    if simulator == "nvc" and version_tuple(cocotb) < (1, 9):
        return "NVC needs cocotb 1.9 or later"
    return None

def version_tuple(version):
    return tuple(int(part) for part in re.findall(r"\d+", version)[:2])

def short_version(version):
    """Returns the major and minor version, e.g. 5.0 for 5.0.0.dev16"""
    return ".".join(str(part) for part in version_tuple(version))

def combination_name(vunit, cocotb):
    return f"vunit{vunit}-cocotb{cocotb}"

def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    parser.add_argument("--output", type=Path, default=Path("matrix_out"), metavar="DIR",
                        help="directory of the virtual environments and results (default: matrix_out)")
    parser.add_argument("-p", "--num-threads", type=int, default=4, metavar="N",
                        help="threads, i.e. simulator processes, of the parallel runs (default: 4)")
    parser.add_argument("--quick", action="store_true", help=f"only run {len(QUICK)} combinations covering each version")
    parser.add_argument("--vunit", nargs="+", metavar="VERSION",
                        help="VUnit versions to run, instead of the supported ones (any version on PyPI)")
    parser.add_argument("--cocotb", nargs="+", metavar="VERSION",
                        help="cocotb versions to run, instead of the supported ones (any version on PyPI)")
    parser.add_argument("--suite", nargs="+", choices=[suite.name for suite in SUITES], metavar="NAME",
                        help=f"only run these suites: {', '.join(suite.name for suite in SUITES)}")
    parser.add_argument("--timeout", type=float, default=1800, metavar="SECONDS", help="seconds a run may take (default: 1800)")
    parser.add_argument("--show-logs", action="store_true", help="print the end of the console log of failed runs")
    parser.add_argument("--github-matrix", nargs="+", metavar="SIMULATOR",
                        help="print the combinations to run with these simulators as a GitHub Actions matrix, and exit")
    options = parser.parse_args()
    if options.quick and (options.vunit or options.cocotb):
        parser.error("--quick can't be combined with --vunit or --cocotb")
    return options

def combinations(options):
    if options.quick:
        return list(QUICK)
    return list(itertools.product(options.vunit or VUNIT_VERSIONS, options.cocotb or COCOTB_VERSIONS))

def planned_runs(simulator, threads, suite_names):
    """Returns the (name, suite, threads) of the runs of each combination"""
    runs = []
    for suite in SUITES:
        if suite_names and suite.name not in suite_names:
            continue
        if suite.simulators is not None and simulator not in suite.simulators:
            continue
        if suite.independent and not suite_names and simulator != INDEPENDENT_SUITES_SIMULATOR:
            continue
        for n in ([1] if suite.one_thread and threads != 1 else []) + [threads]:
            runs.append((f"{suite.name}-p{n}", suite, n))
    return runs

def simulator_version(simulator):
    """Returns the first line the simulator prints as its version, and its executable, or "unknown" """
    command = VERSION_COMMANDS.get(simulator)
    if command is None:
        return "unknown", None
    executable = shutil.which(command[0], path=os.environ.get(f"VUNIT_{simulator.upper()}_PATH") or None)
    if executable is None:
        return "unknown", None
    try:
        proc = subprocess.run([executable, *command[1:]], capture_output=True, text=True, timeout=60,
                              stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return "unknown", executable
    lines = [line.strip() for line in (proc.stdout + proc.stderr).splitlines() if line.strip()]
    return (lines[0] if lines else "unknown"), executable

def vcst_revision():
    """Returns the git revision of the checkout, marked dirty if it has changes, or "unknown" """
    try:
        proc = subprocess.run(["git", "-C", str(ROOT), "describe", "--always", "--dirty"], capture_output=True,
                              text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"

def duration(seconds):
    minutes, seconds = divmod(round(seconds), 60)
    return f"{minutes}:{seconds:02}"

def copy_vcst(destination):
    """
    Copies what is needed to install VCST, so that building it leaves the checkout unchanged, and the same VCST is
    installed for every combination, even if the checkout is changed in the meantime
    """
    shutil.rmtree(destination, ignore_errors=True)
    shutil.copytree(ROOT / "vcst", destination / "vcst", ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("pyproject.toml", "README.md", "LICENSE"):
        shutil.copy2(ROOT / name, destination)

def install(venv_dir, vunit, cocotb, vcst_source, log_path):
    """Installs a combination in a virtual environment, created if needed, returns its Python or None if it failed"""
    python = venv_dir / ("Scripts" if os.name == "nt" else "bin") / "python"
    pip = [str(python), "-m", "pip", "install", "--disable-pip-version-check"]
    commands = [] if python.exists() else [[sys.executable, "-m", "venv", str(venv_dir)]]
    commands += [pip + [f"vunit-hdl=={vunit}", f"cocotb=={cocotb}"],
                 pip + ["--no-deps", "--force-reinstall", str(vcst_source)]]
    with open(log_path, "w") as log:
        for command in commands:
            log.write(f"$ {' '.join(command)}\n")
            log.flush()
            if subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL).returncode:
                return None
    return python

def run(command, log_path, cwd, env, timeout):
    """Runs a command with its output written to log_path, returns "pass", "FAIL" or "TIMEOUT" """
    with open(log_path, "w") as log:
        log.write(f"$ {' '.join(command)}\n")
        log.flush()
        #In a session of its own, so that the simulators started by the script can be stopped with it
        proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, cwd=cwd,
                                env=env, start_new_session=True)
        try:
            return "pass" if proc.wait(timeout) == 0 else "FAIL"
        except subprocess.TimeoutExpired:
            stop(proc)
            log.write(f"\nStopped after {timeout:g} seconds\n")
            return "TIMEOUT"
        except KeyboardInterrupt:
            stop(proc)
            raise

def stop(proc):
    """
    Stops a script and the simulators it started. It is interrupted first, as VUnit then stops its simulators, which
    run in process groups of their own, and killed if it hasn't stopped after 30 seconds.
    """
    if hasattr(os, "killpg"):
        try:
            os.killpg(proc.pid, signal.SIGINT)
            proc.wait(30)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            pass
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        proc.kill()
    proc.wait()

def table(rows):
    """Formats rows, the first being the header, as columns aligned for the console"""
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    return "\n".join("  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip() for row in rows)

def markdown_table(rows):
    lines = ["| " + " | ".join(row) + " |" for row in rows]
    lines.insert(1, "|" + "---|" * len(rows[0]))
    return "\n".join(lines)

def results_grid(summary, runs):
    """Returns rows of the runs against the combinations, the first row being the header"""
    rows = [["Run"] + [f"{short_version(c['vunit'])}/{short_version(c['cocotb'])}" for c in summary["combinations"]]]
    for name, _, _ in runs:
        row = [name]
        for combination in summary["combinations"]:
            results = {run["name"]: run["result"] for run in combination["runs"]}
            if combination["status"] == "unsupported":
                row.append("n/a")
            elif combination["status"] == "install failed":
                row.append("-")
            else:
                row.append(results.get(name, "-"))
        rows.append(row)
    return rows

def problems(summary):
    """Returns lines describing the combinations which weren't run and the runs which failed"""
    lines = []
    for combination in summary["combinations"]:
        title = f"VUnit {combination['vunit']}, cocotb {combination['cocotb']}"
        if combination["status"] == "unsupported":
            lines.append(f"{title}: not run, {combination['reason']}")
        elif combination["status"] == "install failed":
            lines.append(f"{title}: installation failed, see {combination['install_log']}")
        for run in combination["runs"]:
            if run["result"] == "skip":
                lines.append(f"{title}, {run['name']}: skipped, {run['reason']}")
            elif run["result"] != "pass":
                lines.append(f"{title}, {run['name']}: {run['result']}, see {run['log']}")
    return lines

def write_report(output, summary, runs):
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = [
        "# VCST test matrix",
        "",
        f"- Simulator: {summary['simulator']}, {summary['simulator_version']}",
        f"- OS: {summary['os']}",
        f"- Python: {summary['python']}",
        f"- VCST: {summary['vcst']}",
        f"- Parallel runs: -p {summary['threads']}",
        f"- Date: {summary['date']}",
    ]
    if summary.get("interrupted"):
        lines.append("- Interrupted, the runs shown as - weren't run")
    lines += [
        "",
        "Columns: VUnit/cocotb.",
        "",
        markdown_table(results_grid(summary, runs)),
    ]
    issues = problems(summary)
    if issues:
        lines += ["", "Not run or failed:", ""] + [f"- {line}" for line in issues]
    (output / "report.md").write_text("\n".join(lines) + "\n")

def print_log_end(log, lines=40):
    print(f"\n----- {log} (last {lines} lines)")
    print("\n".join(Path(log).read_text(errors="replace").splitlines()[-lines:]))

def github_matrix(options):
    include = []
    for simulator in options.github_matrix:
        for vunit, cocotb in combinations(options):
            if unsupported(simulator, cocotb) is None:
                include.append({"vunit": vunit, "cocotb": cocotb, "simulator": simulator})
    return {"include": include}

def main():
    options = parse_args()
    if options.github_matrix:
        print(json.dumps(github_matrix(options)))
        return 0

    simulator = os.environ.get("VUNIT_SIMULATOR")
    if not simulator:
        sys.exit("Select the simulator with VUNIT_SIMULATOR, e.g. VUNIT_SIMULATOR=rivierapro")
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    pairs = combinations(options)
    runs = planned_runs(simulator, options.num_threads, options.suite)
    version, executable = simulator_version(simulator)
    summary = {
        "simulator": simulator,
        "simulator_version": version,
        "simulator_executable": executable,
        "os": platform.platform(),
        "python": platform.python_version(),
        "vcst": vcst_revision(),
        "threads": options.num_threads,
        "date": datetime.now().astimezone().isoformat(timespec="seconds"),
        "combinations": [],
    }
    print(f"VCST test matrix on {simulator} ({version}), Python {summary['python']}, {len(pairs)} combination{'s' if len(pairs) != 1 else ''}, "
          f"-p {options.num_threads}")
    print(f"Output: {output}")

    vcst_source = output / "vcst-src"
    copy_vcst(vcst_source)
    #The Python of each virtual environment is run without activating it, as by CI. VCST would pass the VIRTUAL_ENV
    #of an activated environment on to cocotb 1.x, which would then use that environment.
    env = {name: value for name, value in os.environ.items() if name != "VIRTUAL_ENV"}

    try:
        for index, (vunit, cocotb) in enumerate(pairs, 1):
            name = combination_name(vunit, cocotb)
            combination = {"vunit": vunit, "cocotb": cocotb, "status": "run", "runs": []}
            summary["combinations"].append(combination)
            print(f"\n[{index}/{len(pairs)}] VUnit {vunit}, cocotb {cocotb}")
            reason = unsupported(simulator, cocotb)
            if reason:
                combination.update(status="unsupported", reason=reason)
                print(f"  not run: {reason}")
                continue

            results_dir = output / name
            shutil.rmtree(results_dir, ignore_errors=True)
            results_dir.mkdir()
            install_log = results_dir / "install.log"
            start = time.monotonic()
            python = install(output / "venvs" / name, vunit, cocotb, vcst_source, install_log)
            if python is None:
                combination.update(status="install failed", install_log=str(install_log))
                print(f"  installation failed, see {install_log}")
                continue
            print(f"  installed in {duration(time.monotonic() - start)}")

            for run_name, suite, threads in runs:
                run_dir = results_dir / run_name
                run_dir.mkdir()
                log = run_dir / "console.log"
                missing = [tool for tool in suite.requires if shutil.which(tool, path=env.get("PATH")) is None]
                if missing:
                    reason = f"{', '.join(missing)} not found"
                    log.write_text(f"Skipped: {reason}\n")
                    combination["runs"].append({"name": run_name, "result": "skip", "seconds": 0, "log": str(log),
                                                "reason": reason})
                    print(f"  {run_name:<26} skip     {reason}")
                    continue
                command = [str(python), str(ROOT / "tests" / suite.script), *suite.args, "-p", str(threads),
                           "--output-path", str(run_dir)]
                start = time.monotonic()
                #Run from the output directory, as a checkout in the working directory could be imported instead of
                #the VCST installed
                result = run(command, log, run_dir, env, options.timeout)
                seconds = time.monotonic() - start
                combination["runs"].append({"name": run_name, "result": result, "seconds": round(seconds, 1),
                                            "log": str(log)})
                print(f"  {run_name:<26} {result:<8} {duration(seconds)}")
    except KeyboardInterrupt:
        print("\nInterrupted, reporting the runs so far")
        summary["interrupted"] = True

    write_report(output, summary, runs)
    print()
    print("Columns: VUnit/cocotb")
    print(table(results_grid(summary, runs)))
    issues = problems(summary)
    failed = [run for c in summary["combinations"] for run in c["runs"] if run["result"] not in ("pass", "skip")]
    failed_installs = [c for c in summary["combinations"] if c["status"] == "install failed"]
    if issues:
        print("\nNot run or failed:")
        for line in issues:
            print(f"  {line}")
    if options.show_logs:
        for combination in failed_installs:
            print_log_end(combination["install_log"])
        for run_result in failed:
            print_log_end(run_result["log"])
    total = sum(len(c["runs"]) for c in summary["combinations"])
    skipped = sum(run["result"] == "skip" for c in summary["combinations"] for run in c["runs"])
    skipped_text = f", {skipped} skipped" if skipped else ""
    print(f"\n{total - skipped - len(failed)} of {total - skipped} runs passed{skipped_text}. Report: {output / 'report.md'}")
    if summary.get("interrupted"):
        return 130
    return 1 if failed or failed_installs else 0

if __name__ == "__main__":
    sys.exit(main())

"""
Checks the GUI of ModelSim/Questa and Riviera-PRO (VUnit's --gui), end to end, with cocotb tests running in it:

- the test of a VHDL top level runs in the GUI, and its results are read back; also the test of a Verilog top level,
  with Riviera-PRO
- the test reads a signal inside the design, which drives no port, and with vsim_flags.gui set, as a user debugging
  does, the simulator shows it too: VUnit uses vsim_flags.gui instead of vsim_flags in the GUI, so VCST has to add the
  flags that load cocotb to vsim_flags.gui as well, without hiding the signals
- the simulation is restarted with vunit_restart, as a user does when debugging. VUnit runs the run script again to
  compile what changed, which goes through VCST and must finish, restarts the simulation and runs the test again. On
  ModelSim/Questa cocotb 2 doesn't run the test again (cocotb issue 284), and cocotb 1.x does the same or hangs the
  GUI, varying from run to run; on Riviera-PRO the test runs again and must pass. A restart that behaves differently
  from what is known fails the check, so that a fix, or a new problem, is noticed.

A GUI needs an X server. The first of these that works is used: Xvfb, if it is on the PATH; the DISPLAY of the user, if
an X client can open it; Xvfb in a podman container (tests/gui/Containerfile, built the first time, which needs network
access), sharing the socket directory /tmp/.X11-unix with the host, so that the simulator runs on the host with its
licence and installation. An Xvfb started here only accepts clients with a key it writes to the output directory, not
other users of the machine.

Usage: python check.py [-p N] [--output-path DIR]

Runs with the simulator selected by VUNIT_SIMULATOR, like the run scripts. A GUI that hasn't closed after
VCST_GUI_TIMEOUT seconds (default 90; a run takes about 5) is taken to hang, and is stopped with its simulator
processes. Exits with 0 if all checks passed, 1 if a check failed and 77 if the checks can't run, which run_matrix.py
reports as skipped: the simulator has no GUI to check, or there is no X server. The output of the runs is written to
DIR, by default a new temporary directory, which is kept if a check failed.
"""

import argparse
import contextlib
import hashlib
import os
import select
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from vunit.sim_if.factory import SIMULATOR_FACTORY

from vcst.utils.compat import COCOTB2

ROOT = Path(__file__).resolve().parent
SKIPPED = 77
X11_DIR = Path("/tmp/.X11-unix")
MARKER = "VCST_GUI_TEST_RAN"
GUI_TIMEOUT = int(os.environ.get("VCST_GUI_TIMEOUT", "90"))

# The simulators with a GUI to check, and flags for their vsim_flags.gui which the simulator accepts
FLAGS = {"modelsim": "-voptargs=+acc", "rivierapro": "+access +r"}
# The simulators whose GUI is also checked with a Verilog top level: VCST loads cocotb into ModelSim/Questa through FLI,
# which supports VHDL only
VERILOG = {"rivierapro"}

# What happens at a restart: the number of times the test ran and whether the GUI closed. The key is the simulator, and
# whether cocotb 2 is used, the value the outcomes seen. With cocotb 1.x on ModelSim/Questa the outcome varies from run
# to run, with the same versions.
RAN_ONCE = "ran once, the restart didn't run the test again"
RAN_TWICE = "ran twice, the restart ran the test again"
HUNG = "the GUI hung"
KNOWN_RESTARTS = {
    ("modelsim", True): (RAN_ONCE,),
    ("modelsim", False): (RAN_ONCE, HUNG),
    ("rivierapro", True): (RAN_TWICE,),
    ("rivierapro", False): (RAN_TWICE,),
}

failures = []


def check(name, condition, details=""):
    print(f"{'pass' if condition else 'FAIL'} {name}")
    if not condition:
        failures.append(name)
        print(details)


class NoXServer(Exception):
    """An X server that can't be used, with the reason"""


def skip(reason):
    print(f"Skipped: {reason}")
    sys.exit(SKIPPED)


# Opens a display with libX11, as the simulator will, with its authorization: exits with 0 if it can, 1 if it can't, 2
# without libX11
OPEN_DISPLAY = """
import ctypes, ctypes.util, sys
name = ctypes.util.find_library("X11")
if not name:
    sys.exit(2)
x11 = ctypes.CDLL(name)
x11.XOpenDisplay.restype = ctypes.c_void_p
x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
display = x11.XOpenDisplay(sys.argv[1].encode())
if not display:
    sys.exit(1)
x11.XCloseDisplay(display)
"""


def socket_answers(display):
    """Whether something accepts connections at the socket of display, e.g. ':0' or 'host:1'"""
    host, _, number = display.partition(":")
    number = number.split(".")[0]
    if not number.isdigit():
        return False
    try:
        if host in ("", "unix"):
            with socket.socket(socket.AF_UNIX) as sock:
                sock.settimeout(5)
                sock.connect(str(X11_DIR / f"X{number}"))
        else:
            with socket.create_connection((host, 6000 + int(number)), timeout=5):
                pass
    except OSError:
        return False
    return True


def display_opens(display, xauthority=None):
    """
    Whether an X client can open display, with the authorization in xauthority or the user's. Without libX11 to check
    with, whether something answers at its socket.
    """
    env = {**os.environ, "DISPLAY": display}
    if xauthority:
        env["XAUTHORITY"] = str(xauthority)
    try:
        opened = subprocess.run(
            [sys.executable, "-c", OPEN_DISPLAY, display],
            env=env,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False
    return socket_answers(display) if opened.returncode == 2 else opened.returncode == 0


def free_display():
    """A display number with neither the socket nor the lock file of an X server"""
    try:
        if not X11_DIR.exists():
            X11_DIR.mkdir()
            # As X servers expect it, which the umask would prevent with mkdir alone
            X11_DIR.chmod(0o1777)
    except OSError as error:
        raise NoXServer(f"{X11_DIR} is needed for the socket of the X server: {error}") from error
    return next(
        n
        for n in range(90, 400)
        if not (X11_DIR / f"X{n}").exists() and not Path(f"/tmp/.X{n}-lock").exists()
    )


def write_xauthority(path, numbers):
    """
    Writes an Xauthority file with a random MIT-MAGIC-COOKIE-1 for the display numbers, valid on any host, so that the X
    server accepts only clients given that file
    """

    def field(data):
        return struct.pack(">H", len(data)) + data

    family_wild = struct.pack(">H", 0xFFFF)
    cookie = os.urandom(16)
    path.write_bytes(
        b"".join(
            family_wild
            + field(b"")
            + field(str(number).encode())
            + field(b"MIT-MAGIC-COOKIE-1")
            + field(cookie)
            for number in numbers
        )
    )
    path.chmod(0o600)


def failed_to_start(output):
    """Raises NoXServer as Xvfb didn't start, after showing its output, which can end with harmless warnings"""
    print("Xvfb didn't start. Its output:")
    for line in output.splitlines()[-40:]:
        print(f"  {line}")
    raise NoXServer("Xvfb didn't start, see its output above")


def wait_for(display, xauthority, alive, output):
    """Waits until display opens, skipping the checks with output() if alive() turns false or it takes 30 seconds"""
    deadline = time.monotonic() + 30
    while not display_opens(display, xauthority):
        if not alive() or time.monotonic() > deadline:
            failed_to_start(output())
        time.sleep(0.5)


@contextlib.contextmanager
def xvfb():
    """
    Starts Xvfb on the PATH, yields its DISPLAY and XAUTHORITY. Xvfb chooses the display number (-displayfd), as it sees
    X servers that a look at /tmp doesn't, e.g. those of other jobs with a /tmp of their own.
    """
    xauthority = work / "xvfb.xauthority"
    write_xauthority(xauthority, range(1000))
    log = work / "xvfb.log"
    read_end, write_end = os.pipe()
    with open(log, "w") as log_file:
        proc = subprocess.Popen(
            ["Xvfb", "-displayfd", str(write_end), "-auth", str(xauthority)]
            + ["-screen", "0", "1280x1024x24", "-nolisten", "tcp"],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            pass_fds=[write_end],
        )
    os.close(write_end)
    try:
        # Xvfb writes the number of its display once it is ready, and the pipe closes if it exits
        number = ""
        deadline = time.monotonic() + 30
        while not number.endswith("\n") and time.monotonic() < deadline:
            if select.select([read_end], [], [], 1)[0]:
                chunk = os.read(read_end, 64).decode(errors="replace")
                if not chunk:
                    break
                number += chunk
        number = number.strip()
        if not number.isdigit():
            failed_to_start(log.read_text(errors="replace"))
        wait_for(
            f":{number}",
            xauthority,
            lambda: proc.poll() is None,
            lambda: log.read_text(errors="replace"),
        )
        yield f":{number}", xauthority
    finally:
        os.close(read_end)
        proc.terminate()
        proc.wait()


@contextlib.contextmanager
def xvfb_in_container():
    """Starts Xvfb in a podman container, yields its DISPLAY and XAUTHORITY"""
    containerfile = ROOT / "Containerfile"
    image = f"vcst-xvfb:{hashlib.sha256(containerfile.read_bytes()).hexdigest()[:12]}"
    if subprocess.run(["podman", "image", "exists", image], check=False).returncode:
        print(f"Building the image {image} with Xvfb")
        built = subprocess.run(
            ["podman", "build", "-q", "-t", image, "-f", str(containerfile), str(ROOT)],
            capture_output=True,
            text=True,
            check=False,
        )
        if built.returncode:
            raise NoXServer(f"the image with Xvfb can't be built: {built.stderr[-300:]}")
    number = free_display()
    auth_dir = work / "xvfb_auth"
    auth_dir.mkdir(exist_ok=True)
    xauthority = auth_dir / "xauthority"
    write_xauthority(xauthority, [number])
    name = f"vcst-xvfb-{os.getpid()}"
    # The X server needs no network, only the socket directory; SELinux labels would keep it from writing there
    started = subprocess.run(
        [
            *["podman", "run", "-d", "--userns=keep-id", "--network=none", "--name", name],
            *["--security-opt", "label=disable", "-v", f"{X11_DIR}:{X11_DIR}"],
            *["-v", f"{auth_dir}:{auth_dir}:ro", image],
            *["Xvfb", f":{number}", "-auth", str(xauthority), "-screen", "0", "1280x1024x24"],
            *["-nolisten", "tcp"],
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if started.returncode:
        raise NoXServer(f"Xvfb can't be started in a container: {started.stderr[-300:]}")
    try:

        def running():
            state = subprocess.run(
                ["podman", "inspect", "-f", "{{.State.Running}}", name],
                capture_output=True,
                text=True,
                check=False,
            )
            return state.stdout.strip() == "true"

        def logs():
            done = subprocess.run(
                ["podman", "logs", name], capture_output=True, text=True, check=False
            )
            return (done.stdout + done.stderr) or "(nothing)"

        wait_for(f":{number}", xauthority, running, logs)
        yield f":{number}", xauthority
    finally:
        subprocess.run(["podman", "rm", "-f", "-t", "2", name], capture_output=True, check=False)


def find_display(stack):
    """
    Returns (DISPLAY, XAUTHORITY or None for the user's) of an X server that a client can open, starting one if
    needed, trying the next way when one doesn't work. stack closes what is started.
    """
    reasons = []
    if shutil.which("Xvfb"):
        print(f"Using Xvfb ({shutil.which('Xvfb')})")
        try:
            return stack.enter_context(xvfb())
        except NoXServer as error:
            reasons.append(f"Xvfb on the PATH: {error}")
            print(f"{reasons[-1]}; trying the next way")
    user_display = os.environ.get("DISPLAY")
    if user_display and display_opens(user_display):
        print(f"Using the X server at DISPLAY={user_display}")
        return user_display, None
    if user_display:
        reasons.append(f"DISPLAY={user_display} can't be opened")
        print(reasons[-1])
    if shutil.which("podman"):
        print("Using Xvfb in a container")
        try:
            return stack.enter_context(xvfb_in_container())
        except NoXServer as error:
            reasons.append(f"Xvfb in a container: {error}")
    reasons = "; ".join(reasons) or "none of Xvfb, DISPLAY and podman is there"
    skip(
        f"no X server: {reasons}. Install Xvfb or podman, or set DISPLAY to an X server you can open"
    )


def descendants(pid):
    """The pids of the processes started by pid, directly or not, found in /proc (none where there is no /proc)"""
    parents = {}
    for stat in Path("/proc").glob("[0-9]*/stat"):
        try:
            # After the name of the process, which may contain spaces and parentheses: state and parent
            fields = stat.read_text().rpartition(")")[2].split()
            parents[int(stat.parent.name)] = int(fields[1])
        except (OSError, ValueError, IndexError):
            continue
    found = []
    pending = [pid]
    while pending:
        parent = pending.pop()
        children = [child for child, ppid in parents.items() if ppid == parent]
        found += children
        pending += children
    return found


def stop(proc):
    """
    Stops a run script and the simulators it started, which VUnit starts in process groups of their own, which a signal
    to the script doesn't reach: they are interrupted, as VUnit then stops its simulators, and killed if that doesn't
    end the script, and whatever is left of them is killed.
    """
    groups = {proc.pid}
    for pid in descendants(proc.pid):
        with contextlib.suppress(ProcessLookupError, PermissionError):
            groups.add(os.getpgid(pid))
    for sig in (signal.SIGINT, signal.SIGKILL):
        for group in groups:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(group, sig)
        try:
            proc.wait(30 if sig == signal.SIGINT else None)
            break
        except subprocess.TimeoutExpired:
            continue
    for group in groups:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(group, signal.SIGKILL)


def run_gui(name, display, xauthority, init_file, flags=None, top="vhdl"):
    """
    Runs the project in the GUI, with init_file sourced once the design is loaded. Returns (exit code or None if it
    hung, VUnit's output, the simulator's transcripts, the number of times the test ran, whether cocotb wrote results
    and all of them passed).
    """
    output_path = work / name
    env = {
        **os.environ,
        "DISPLAY": display,
        "VCST_GUI_INIT": str(ROOT / init_file),
        "VCST_GUI_FLAGS": flags or "",
        "VCST_GUI_TOP": top,
    }
    if xauthority:
        env["XAUTHORITY"] = str(xauthority)
    command = [
        sys.executable,
        str(ROOT / "project" / "run.py"),
        "--gui",
        "--output-path",
        str(output_path),
    ]
    # Its own session, so that the simulator can be stopped with the script if the GUI hangs
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
        env=env,
        start_new_session=True,
    )
    try:
        output, _ = proc.communicate(timeout=GUI_TIMEOUT)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        stop(proc)
        output, _ = proc.communicate()
        code = None
    except BaseException:
        # Interrupted: the GUI and its simulator, in a session of their own, would be left running
        stop(proc)
        raise
    # In the GUI the output of the simulator is in its transcript, one for each simulator process of the test
    transcripts = "".join(
        transcript.read_text(errors="replace")
        for transcript in sorted(output_path.rglob("transcript"))
    )
    results = []
    for results_file in output_path.rglob("cocotb_results.xml"):
        try:
            results += [
                case.find("failure") is None and case.find("error") is None
                for case in ET.parse(results_file).getroot().iter("testcase")
            ]
        except ET.ParseError:
            # Cut short by a hung GUI being stopped
            results.append(False)
    return code, output, transcripts, transcripts.count(MARKER), bool(results) and all(results)


def details(code, output, transcripts, ran, passed):
    """What a failed check prints: the outcome, and the end of VUnit's output and of the simulator's transcripts"""
    return (
        f"exit code {code}, the test ran {ran} times, passed: {passed}\n"
        f"--- VUnit's output, end:\n{output[-1500:]}\n--- the simulator's transcripts, end:\n{transcripts[-3000:]}"
    )


parser = argparse.ArgumentParser(description="Checks the GUI of the simulator with cocotb tests")
parser.add_argument(
    "-p", "--num-threads", default="1", help="accepted as the other suites, not used"
)
parser.add_argument("--output-path", help="where to write the output of the runs")
options = parser.parse_args()

simulator = SIMULATOR_FACTORY.select_simulator().name
if simulator not in FLAGS:
    skip(f"{simulator} has no GUI to check, only ModelSim/Questa and Riviera-PRO are")

if options.output_path:
    work = Path(options.output_path).resolve()
    work.mkdir(parents=True, exist_ok=True)
else:
    work = Path(tempfile.mkdtemp(prefix="vcst_gui_"))

# Stopped from outside, the X server and the GUI running are stopped too, as for an interrupt
signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(128 + signum))

with contextlib.ExitStack() as stack:
    display, xauthority = find_display(stack)

    tops = ["vhdl", "verilog"] if simulator in VERILOG else ["vhdl"]
    for top in tops:
        outcome = run_gui(f"run_once_{top}", display, xauthority, "run_once.do", top=top)
        code, _, _, ran, passed = outcome
        check(
            f"the test of a {top.upper()} top level runs in the GUI",
            code == 0 and ran == 1 and passed,
            details(*outcome),
        )

    outcome = run_gui("flags", display, xauthority, "run_once.do", FLAGS[simulator])
    code, _, transcripts, ran, passed = outcome
    check(
        "the test runs in the GUI with vsim_flags.gui set",
        code == 0 and ran == 1 and passed,
        details(*outcome),
    )
    # What run_once.do printed when it had the simulator examine a signal inside the design, leaving out the lines
    # echoing the script
    examined = [
        line.split("VCST_GUI_EXAMINE", 1)[1]
        for line in transcripts.splitlines()
        if "VCST_GUI_EXAMINE" in line and "puts" not in line
    ]
    check(
        "the simulator shows a signal inside the design, with the vsim_flags.gui a user debugging gives",
        len(examined) == 1
        and examined[0].startswith("D ")
        and examined[0][2:].strip(" '\"") == "0",
        f"run_once.do printed: {examined}\n" + details(*outcome),
    )

    outcome = run_gui("restart", display, xauthority, "restart.do")
    code, output, transcripts, ran, passed = outcome
    if code is None:
        observed = HUNG
    elif code != 0:
        observed = f"the GUI failed with exit code {code}"
    elif ran == 2:
        observed = RAN_TWICE if passed else "ran twice, and the test run again failed"
    elif ran == 1:
        observed = RAN_ONCE
    else:
        observed = f"ran {ran} times"
    # vunit_restart prints this once the run script, which goes through VCST, has compiled what changed
    recompiled = "Re-compile finished" in transcripts
    if observed != HUNG and not recompiled:
        observed += ", and the recompile before the restart didn't finish"
    print(f"vunit_restart: {observed}")
    known = KNOWN_RESTARTS[(simulator, COCOTB2)]
    check(
        "a restart ends as it is known to",
        observed in known,
        f"expected one of: {known}\nobserved: {observed}\n"
        "This is not what is known: update KNOWN_RESTARTS if it is fixed.\n" + details(*outcome),
    )

print("=" * 70)
if failures:
    print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
    if not options.output_path:
        print(f"The output of the runs is kept in {work}")
    sys.exit(1)
if not options.output_path:
    shutil.rmtree(work, ignore_errors=True)
print("All checks passed.")

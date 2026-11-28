"""
The workaround which lets coverage.py save its data with an SQLite older than 3.26, as Riviera-PRO loads into the
simulator (vcst/utils/old_sqlite.py says why it's needed and when it can be removed).

With a stand-in sqlite3 module: the constant is removed only for an SQLite older than 3.26.

With a real old SQLite, loaded with LD_PRELOAD into a Python started for it: the one VCST_OLD_SQLITE names (CI builds
SQLite 3.25.3, the version of Riviera-PRO 2026.04), or else Riviera-PRO's own (bin/Linux64/libsqlite3.so) when
VUNIT_SIMULATOR is rivierapro. These check that SQLite refuses the setting, that coverage.py fails to save its data
without the workaround, and that with it coverage.py, used in the order cocotb 2.1 uses it, saves data which a Python
with a current SQLite reads. They use the installed coverage.py, or else the newest, installed into a temporary
directory, which needs pip and the package index.

Skipped, saying why, when there is nothing to check: without such an SQLite, on Python before 3.12 (which hasn't the
setting), with a Python that has SQLite built in (as uv's have), which LD_PRELOAD can't replace, without coverage.py,
when Riviera-PRO's own SQLite is 3.26 or newer and doesn't need the workaround, and when coverage.py saves without the
workaround, having fixed the problem. With VCST_OLD_SQLITE set, as in CI, a Python or SQLite that can't be used fails
instead.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import types
import unittest
from pathlib import Path

from vcst.utils.old_sqlite import DEFENSIVE_SINCE, hide_defensive_config

REPO = Path(__file__).resolve().parents[2]


def fake_sqlite3(version, constant=True):
    module = types.SimpleNamespace(sqlite_version_info=version)
    if constant:
        module.SQLITE_DBCONFIG_DEFENSIVE = 1010
    return module


class StandIn(unittest.TestCase):
    def test_the_constant_is_removed_for_an_sqlite_older_than_3_26(self):
        module = fake_sqlite3((3, 25, 3))
        self.assertTrue(hide_defensive_config(module))
        self.assertFalse(hasattr(module, "SQLITE_DBCONFIG_DEFENSIVE"))

    def test_the_constant_is_kept_from_3_26(self):
        for version in (DEFENSIVE_SINCE, (3, 46, 1)):
            module = fake_sqlite3(version)
            self.assertFalse(hide_defensive_config(module))
            self.assertTrue(hasattr(module, "SQLITE_DBCONFIG_DEFENSIVE"))

    def test_a_python_without_the_constant_is_left_alone(self):
        self.assertFalse(hide_defensive_config(fake_sqlite3((3, 25, 3), constant=False)))


def old_sqlite():
    """The old SQLite to check with, and whether it was asked for with VCST_OLD_SQLITE, or (None, False)"""
    if os.environ.get("VCST_OLD_SQLITE"):
        return Path(os.environ["VCST_OLD_SQLITE"]), True
    if os.environ.get("VUNIT_SIMULATOR") != "rivierapro" or not sys.platform.startswith("linux"):
        return None, False
    try:
        from vunit.sim_if.rivierapro import RivieraProInterface

        prefix = RivieraProInterface.find_prefix()
    except Exception:  # any failure to find Riviera-PRO means there is nothing to check
        return None, False
    library = Path(prefix) / "Linux64" / "libsqlite3.so" if prefix else None
    return (library, False) if library and library.exists() else (None, False)


# Run in a Python with the old SQLite. Prints the SQLite version, then what was checked.
SCRIPT = textwrap.dedent(
    """
    import os, sqlite3, sys
    print(sqlite3.sqlite_version)
    if sys.argv[1] == "problem":
        try:
            sqlite3.connect(":memory:").setconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE, False)
            print("setconfig worked")
        except (SystemError, sqlite3.Error) as error:
            print(f"setconfig failed: {type(error).__name__}: {error}")
    else:
        # As cocotb 2.1 does in the simulator: load and start at its start, then the cocotb module imports vcst.utils
        sys.path.insert(0, os.environ["VCST_COVERAGE_PATH"])
        import coverage
        cov = coverage.Coverage(data_file=os.path.join(sys.argv[2], ".coverage"), data_suffix=True)
        cov.load()
        cov.start()
        if sys.argv[1] == "with":
            import vcst.utils
        sys.path.insert(0, sys.argv[2])
        import measured
        measured.f(3)
        cov.stop()
        try:
            cov.save()
            print(f"saved with coverage.py {coverage.__version__}")
        except Exception as error:
            print(f"save failed with coverage.py {coverage.__version__}: {type(error).__name__}: {error}")
    """
)

MEASURED = textwrap.dedent(
    """
    def f(n):
        total = 0
        for i in range(n):
            total += i
        return total
    """
)

# Run in this Python, with its SQLite: combines and reads what the other saved
READ = textwrap.dedent(
    """
    import os, sys
    sys.path.insert(0, os.environ["VCST_COVERAGE_PATH"])
    import coverage
    cov = coverage.Coverage(data_file=os.path.join(sys.argv[1], ".coverage"))
    cov.combine()
    cov.load()
    data = cov.get_data()
    print(sorted(line for name in data.measured_files() if name.endswith("measured.py") for line in data.lines(name)))
    """
)


@unittest.skipIf(
    sys.version_info < (3, 12), "Python before 3.12 hasn't the setting the workaround is about"
)
class RealOldSqlite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library, cls.required = old_sqlite()
        if cls.library is None:
            raise unittest.SkipTest(
                "no old SQLite: set VCST_OLD_SQLITE, or VUNIT_SIMULATOR=rivierapro with Riviera-PRO installed"
            )
        cls.work = Path(tempfile.mkdtemp(prefix="vcst_old_sqlite_"))
        cls.addClassCleanup(shutil.rmtree, cls.work, ignore_errors=True)
        cls.environ = {
            **os.environ,
            "PYTHONPATH": os.pathsep.join(filter(None, [str(REPO), os.environ.get("PYTHONPATH")])),
            "VCST_COVERAGE_PATH": str(cls.work / "coverage_package"),
        }

    def run_python(self, args, preload=True, script=SCRIPT):
        environ = {**self.environ, **({"LD_PRELOAD": str(self.library)} if preload else {})}
        done = subprocess.run(
            [sys.executable, "-c", script, *args],
            capture_output=True,
            text=True,
            env=environ,
            check=False,
        )
        lines = done.stdout.splitlines()
        return done, lines

    def old_version(self):
        """
        The output of the problem check with the old SQLite, failing or skipping the test if that SQLite isn't old or
        this Python doesn't use it
        """
        # The version of the library itself, asked from it
        asked = self.run_python(
            [str(self.library)],
            preload=False,
            script="import ctypes, sys\n"
            "library = ctypes.CDLL(sys.argv[1])\n"
            "library.sqlite3_libversion.restype = ctypes.c_char_p\n"
            "print(library.sqlite3_libversion().decode())",
        )[0]
        if asked.returncode != 0:
            self.fail(f"{self.library} isn't an SQLite library:\n{asked.stderr}")
        version = asked.stdout.strip()
        if tuple(int(part) for part in version.split(".")) >= DEFENSIVE_SINCE:
            message = (
                f"{self.library} is SQLite {version}, which has the setting, so the workaround in "
                "vcst/utils/old_sqlite.py isn't needed with it"
            )
            if self.required:
                self.fail(message)
            self.skipTest(f"{message}; it is still needed for older versions of Riviera-PRO")
        done, lines = self.run_python(["problem"])
        if done.returncode != 0 or not lines:
            self.fail(f"Python with {self.library} failed:\n{done.stdout}{done.stderr}")
        if lines[0] != version:
            message = (
                f"LD_PRELOAD of {self.library} doesn't replace the SQLite of this Python ({lines[0]}), which has it "
                "built in"
            )
            if self.required:
                self.fail(message)
            self.skipTest(message)
        return lines

    def coverage_py(self):
        """Makes coverage.py importable in the Python started for the old SQLite, skipping the test if it can't be"""
        coverage_path = Path(self.environ["VCST_COVERAGE_PATH"])
        has_coverage = subprocess.run(
            [sys.executable, "-c", "import coverage"], capture_output=True, check=False
        )
        if has_coverage.returncode == 0 or coverage_path.exists():
            return
        install = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--quiet",
                "--target",
                str(coverage_path),
                "coverage",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if install.returncode != 0:
            shutil.rmtree(coverage_path, ignore_errors=True)
            message = f"coverage.py isn't installed and can't be:\n{install.stderr[-500:]}"
            if self.required:
                self.fail(message)
            self.skipTest(message)

    def save(self, mode):
        """Saves coverage data in the Python with the old SQLite, without or with the workaround"""
        self.old_version()
        self.coverage_py()
        data = self.work / mode
        data.mkdir()
        (data / "measured.py").write_text(MEASURED)
        done, lines = self.run_python([mode, str(data)])
        self.assertEqual(done.returncode, 0, f"{done.stdout}{done.stderr}")
        return data, lines[-1]

    def test_the_old_sqlite_refuses_the_setting(self):
        lines = self.old_version()
        self.assertTrue(lines[1].startswith("setconfig failed"), lines)

    def test_without_the_workaround_coverage_fails_to_save(self):
        _, outcome = self.save("without")
        if outcome.startswith("saved"):
            self.skipTest(
                f"{outcome} without the workaround, so that coverage.py has fixed the problem: once VCST requires it, "
                "remove vcst/utils/old_sqlite.py and the limit for cocotb 2.1 in the README"
            )
        self.assertTrue(outcome.startswith("save failed"), outcome)

    def test_with_the_workaround_coverage_saves_its_data(self):
        data, outcome = self.save("with")
        self.assertTrue(outcome.startswith("saved"), outcome)
        read, read_lines = self.run_python([str(data)], preload=False, script=READ)
        self.assertEqual(read.returncode, 0, f"{read.stdout}{read.stderr}")
        self.assertEqual(read_lines[-1], "[2, 3, 4, 5, 6]", read_lines)


if __name__ == "__main__":
    unittest.main()

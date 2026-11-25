"""
Behaviour VCST should have and doesn't, found by reading and trying (see the notes of the latent bug investigation).
Each test is expected to fail. When a fix makes one pass, unittest reports an unexpected success and the run fails, so
that the decorator is removed together with the fix.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from vcst.test.suites import CocoTestRun
from vcst.utils.mod_utils import import_mod


class KnownBugs(unittest.TestCase):
    @unittest.expectedFailure
    def test_modules_with_the_same_file_name_in_different_directories_are_different_modules(self):
        # import_mod imports by file name only, so the second module is the first one
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for index in (1, 2):
                path = Path(directory) / f"dir{index}"
                path.mkdir()
                (path / "vcst_unit_same_name.py").write_text(f"VALUE = {index}\n")
                paths.append(str(path / "vcst_unit_same_name"))
            self.addCleanup(sys.modules.pop, "vcst_unit_same_name", None)
            self.assertEqual([import_mod(path).VALUE for path in paths], [1, 2])

    @unittest.expectedFailure
    def test_a_relative_cocotb_module_location_gives_an_absolute_python_path(self):
        # The simulator runs in another directory than the run script, where a relative path finds nothing
        run = CocoTestRun(vhdl=True, top_level="top", simulator_if=SimpleNamespace(name="ghdl"), config=None,
                          elaborate_only=False, cocotb_module=None, cocotb_module_location="relative/dir/module",
                          test_suite_name="lib.top", test_cases=["test"])
        with mock.patch.dict(os.environ, {"LIBPYTHON_LOC": "/x/libpython.so"}):
            os.environ.pop("PYTHONPATH", None)
            environ = run.create_environ("/some/output")
        self.assertTrue(os.path.isabs(environ["PYTHONPATH"]), environ["PYTHONPATH"])


if __name__ == "__main__":
    unittest.main()

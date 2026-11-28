"""
What VCST gives the simulator's cocotb to embed the Python running VCST, which differs between versions of cocotb,
while respecting what the user has set, and when cocotb opens the Python debugger, which VCST warns about.
"""

import sys
import unittest
from unittest import mock

import vcst.utils.compat as compat
from vcst.utils.compat import COCOTB2, gpi_environ, pdb_on_exception

HAS_ENTRY_POINT = hasattr(compat.cocotb_config, "pygpi_entry_point")
LIBPYTHON = "/user/libpython.so"


class GpiEnviron(unittest.TestCase):
    def test_the_python_running_vcst_is_given_to_the_gpi(self):
        self.assertEqual(
            gpi_environ({"LIBPYTHON_LOC": LIBPYTHON})["PYGPI_PYTHON_BIN"], sys.executable
        )

    def test_libpython_of_the_user_is_used(self):
        environ = gpi_environ({"LIBPYTHON_LOC": LIBPYTHON})
        if HAS_ENTRY_POINT:
            library, _, entry_point = environ["GPI_USERS"].partition(";")
            self.assertEqual(library, LIBPYTHON)
            self.assertTrue(entry_point)
            self.assertNotIn("LIBPYTHON_LOC", environ)
        else:
            self.assertEqual(environ["LIBPYTHON_LOC"], LIBPYTHON)
            self.assertNotIn("GPI_USERS", environ)

    @unittest.skipUnless(HAS_ENTRY_POINT, "GPI_USERS is used by cocotb 2.1 and later")
    def test_gpi_users_of_the_user_is_respected(self):
        environ = gpi_environ({"GPI_USERS": "mine", "LIBPYTHON_LOC": LIBPYTHON})
        self.assertNotIn("GPI_USERS", environ)
        self.assertNotIn("LIBPYTHON_LOC", environ)

    @unittest.skipIf(COCOTB2, "only cocotb 1.x finds a virtual environment through VIRTUAL_ENV")
    def test_a_virtual_environment_which_isnt_activated_is_given_to_cocotb_1(self):
        with (
            mock.patch.object(sys, "prefix", "/some/venv"),
            mock.patch.object(sys, "base_prefix", "/usr"),
        ):
            self.assertEqual(gpi_environ({"LIBPYTHON_LOC": LIBPYTHON})["VIRTUAL_ENV"], "/some/venv")
            self.assertNotIn(
                "VIRTUAL_ENV", gpi_environ({"LIBPYTHON_LOC": LIBPYTHON, "VIRTUAL_ENV": "/other"})
            )

    @unittest.skipIf(COCOTB2, "only cocotb 1.x finds a virtual environment through VIRTUAL_ENV")
    def test_no_virtual_environment_is_given_outside_one(self):
        with (
            mock.patch.object(sys, "prefix", "/usr"),
            mock.patch.object(sys, "base_prefix", "/usr"),
        ):
            self.assertNotIn("VIRTUAL_ENV", gpi_environ({"LIBPYTHON_LOC": LIBPYTHON}))

    @unittest.skipUnless(COCOTB2, "cocotb 2 doesn't need VIRTUAL_ENV")
    def test_cocotb_2_isnt_given_a_virtual_environment(self):
        with (
            mock.patch.object(sys, "prefix", "/some/venv"),
            mock.patch.object(sys, "base_prefix", "/usr"),
        ):
            self.assertNotIn("VIRTUAL_ENV", gpi_environ({"LIBPYTHON_LOC": LIBPYTHON}))


class PdbOnException(unittest.TestCase):
    """cocotb 2.1 reads COCOTB_PDB_ON_EXCEPTION as a boolean, earlier versions only check that it is set"""

    def opens(self, version, value):
        environ = {} if value is None else {"COCOTB_PDB_ON_EXCEPTION": value}
        with mock.patch.object(compat, "COCOTB_VERSION", version):
            return pdb_on_exception(environ)

    def test_unset_never_opens_the_debugger(self):
        for version in ((1, 8), (2, 0), (2, 1)):
            self.assertFalse(self.opens(version, None))

    def test_before_2_1_any_value_opens_it(self):
        for version in ((1, 8), (1, 9), (2, 0)):
            for value in ("1", "0", "false", ""):
                self.assertTrue(self.opens(version, value), (version, value))

    def test_from_2_1_only_a_true_value_opens_it(self):
        for value in ("1", "yes", "Y", "on", "TRUE", "enable"):
            self.assertTrue(self.opens((2, 1), value), value)
        for value in ("0", "no", "n", "OFF", "False", "disable", "", " "):
            self.assertFalse(self.opens((2, 1), value), value)


if __name__ == "__main__":
    unittest.main()

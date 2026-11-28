import inspect
import os
from typing import Optional

import cocotb
from vunit import VUnit
from vunit.test.list import TestList

# If a later VUnit renames or moves this, _suites_with_changed_python_files reports it
try:
    from vunit.test.list import TestSuiteWrapper
except ImportError:
    TestSuiteWrapper = None

from ..utils.compat import COCOTB_SUPPORTS_NVC, pdb_on_exception
from ..utils.mod_utils import import_mod, project_python_files
from .library import VCSTLibrary

# VUnit 4.x adds the VHDL builtins unless compile_builtins=False, VUnit 5 only when asked to
_VUNIT_HAS_COMPILE_BUILTINS = "compile_builtins" in inspect.signature(VUnit.__init__).parameters

# The method of VUnit 5 which selects the test suites for --changed, extended by VCST
_CHANGED_HOOK = "_get_test_list_depending_on_change"


class VCST(VUnit):
    # Set while VUnit.from_argv creates the object with from_args, see from_argv
    _builtins_added_by_from_argv = False

    @classmethod
    def from_argv(
        cls,
        argv=None,
        compile_builtins: Optional[bool] = True,
        vhdl_standard: Optional[str] = None,
    ):
        """
        Create VCST instance from command line arguments.

        :param argv: Use explicit argv instead of actual command line argument
        :param compile_builtins: Add VUnit's VHDL builtins, as done by add_vhdl_builtins
        :param vhdl_standard: The VHDL standard used to compile files,
                              if None the VUNIT_VHDL_STANDARD environment variable is used
        """
        # VUnit.from_argv creates the object with from_args, but VUnit 5 sets up what selecting the simulator,
        # and thereby adding the builtins, needs after that. Hence the builtins are added here instead.
        cls._builtins_added_by_from_argv = True
        try:
            if _VUNIT_HAS_COMPILE_BUILTINS:
                vcst_obj = super().from_argv(
                    argv=argv, compile_builtins=False, vhdl_standard=vhdl_standard
                )
            else:
                vcst_obj = super().from_argv(argv=argv, vhdl_standard=vhdl_standard)
        finally:
            cls._builtins_added_by_from_argv = False

        if compile_builtins:
            vcst_obj.add_vhdl_builtins()
        return vcst_obj

    @classmethod
    def from_args(
        cls,
        args,
        compile_builtins: Optional[bool] = True,
        vhdl_standard: Optional[str] = None,
    ):
        """
        Create VCST instance from args namespace.

        :param args: The parsed argument namespace object
        :param compile_builtins: Add VUnit's VHDL builtins, as done by add_vhdl_builtins
        :param vhdl_standard: The VHDL standard used to compile files,
                              if None the VUNIT_VHDL_STANDARD environment variable is used
        """
        vcst_obj = cls(args, vhdl_standard=vhdl_standard)
        if compile_builtins and not cls._builtins_added_by_from_argv:
            vcst_obj.add_vhdl_builtins()
        return vcst_obj

    def __init__(self, args, vhdl_standard: Optional[str] = None):
        # Builtins are added by from_argv/from_args, the same way for all VUnit versions
        if _VUNIT_HAS_COMPILE_BUILTINS:
            super().__init__(args, compile_builtins=False, vhdl_standard=vhdl_standard)
        else:
            super().__init__(args, vhdl_standard=vhdl_standard)
        # The real paths of the files of the cocotb modules added, see _get_test_list_depending_on_change
        self._cocotb_module_files = set()
        self._changed_requested = bool(getattr(args, "changed", False))

    def main(self, *args, **kwargs):
        """Runs VUnit, see :meth:`vunit.ui.VUnit.main`"""
        if self._changed_requested and not hasattr(VUnit, _CHANGED_HOOK):
            print(
                "WARNING: this version of VUnit doesn't have what VCST needs to also take Python files "
                "into account with --changed, so it only considers HDL files, which changes nothing "
                "for tests that only changed in Python. Run without --changed to run them all."
            )
        if pdb_on_exception(os.environ):
            # VUnit starts the simulator with a pipe as its input, which nothing writes to, so the debugger that cocotb
            # opens when a test raises an exception waits forever.
            print(
                f"WARNING: COCOTB_PDB_ON_EXCEPTION is set (to {os.environ['COCOTB_PDB_ON_EXCEPTION']!r}), which makes "
                f"cocotb {cocotb.__version__} open the Python debugger in the first test that raises an exception. "
                "Under VUnit the debugger waits forever for input, which hangs the run. Unset it, and debug the test "
                "outside VUnit."
            )
        return super().main(*args, **kwargs)

    def library(self, library_name: str):
        """
        Get a library

        :param library_name: The name of the library
        :returns: A :class:`.Library` object
        """
        if not self._project.has_library(library_name):
            raise KeyError(library_name)
        return VCSTLibrary(library_name, self, self._project, self._test_bench_list)

    def add_cocotb_testbench(self, cocotb_module_location, cocotb_module=None):
        """Adds a cocotb module to a library based on variables defined in the cocotb module."""
        # The simulator runs in another directory than this script, where a relative path finds nothing
        cocotb_module_location = os.path.abspath(cocotb_module_location)
        top_level = None
        top_level_type = None
        top_level_library = None

        if cocotb_module is None:
            cocotb_module = import_mod(cocotb_module_location)

        if hasattr(cocotb_module, "top_level"):
            top_level = cocotb_module.top_level
        else:
            raise RuntimeError(f"top_level not defined in cocotb module {cocotb_module}")

        if hasattr(cocotb_module, "top_level_type"):
            top_level_type = cocotb_module.top_level_type
        else:
            raise RuntimeError(f"top_level_type not defined in cocotb module {cocotb_module}")

        if hasattr(cocotb_module, "top_level_library"):
            top_level_library = cocotb_module.top_level_library
        else:
            raise RuntimeError(f"top_level_library not defined in cocotb module {cocotb_module}")

        if not isinstance(top_level, str):
            raise RuntimeError(
                f"top_level defined in cocotb module should be a string {cocotb_module}"
            )

        if not isinstance(top_level_type, str):
            raise RuntimeError(
                f"top_level_type defined in cocotb module should be a string {cocotb_module}"
            )

        if not isinstance(top_level_library, str):
            raise RuntimeError(
                f"top_level_library defined in cocotb module should be a string {cocotb_module}"
            )

        if top_level_type not in ("entity", "module"):
            raise RuntimeError(
                f"Invalid top level type {top_level_type} in cocotb module {cocotb_module} specified. Please specify either entity or module."
            )

        simulator_class = self._simulator_class
        if (
            simulator_class is not None
            and simulator_class.name == "nvc"
            and not COCOTB_SUPPORTS_NVC
        ):
            raise RuntimeError(
                f"NVC needs cocotb 1.9 or later, cocotb {cocotb.__version__} is installed"
            )

        module_file = getattr(cocotb_module, "__file__", None)
        if isinstance(module_file, str):
            self._cocotb_module_files.add(os.path.realpath(module_file))

        library = self.library(top_level_library)
        top_level_design_unit = None

        if top_level_type == "entity":
            top_level_design_unit = library.entity(top_level, test_bench=False)
        else:
            top_level_design_unit = library.module(top_level, test_bench=False)

        return library.add_cocotb_testbench(
            top_level_design_unit, cocotb_module, cocotb_module_location
        )

    def _get_test_list_depending_on_change(self, test_list):
        """
        Extracts the test suites of test_list that depend on changes, for --changed (VUnit 5).

        VUnit only knows the HDL files, so it takes the HDL file of the top level as the file of a cocotb test. A
        cocotb test also depends on Python code: its own module and the rest of the Python files of the project, those
        loaded by the run script, which are what the tests import. These are all the Python files not in the standard
        library or site-packages (editable installs are), except for the other cocotb modules. A file that is
        imported only while a test runs, or by a package which the run script doesn't load, isn't known.

        This relies on private parts of VUnit. If they are not as expected, all tests are selected, since
        selecting too few tests would hide failures.
        """
        depending_on_change = super()._get_test_list_depending_on_change(test_list)
        try:
            python_changed = self._suites_with_changed_python_files(test_list)
        except (AttributeError, KeyError, TypeError) as error:
            print(
                "WARNING: VCST can't tell which tests depend on changed Python files with this version of "
                f"VUnit ({error!r}), so --changed selects all tests."
            )
            return test_list

        selected = {suite.name for suite in depending_on_change} | python_changed
        new_test_list = TestList()
        for suite in test_list:
            if suite.name in selected:
                new_test_list.add_suite(suite)
        return new_test_list

    def _suites_with_changed_python_files(self, test_list):
        """
        Returns the names of the test suites of test_list with a Python file modified after their tests last ran.
        Suites without history are left out, as VUnit selects them.
        """
        shared_files = project_python_files() - self._cocotb_module_files
        history = self._test_history
        changed = set()
        if TestSuiteWrapper is None:
            raise AttributeError("vunit.test.list.TestSuiteWrapper")
        for suite in test_list:
            # VUnit wraps each test case in a test suite of its own, but not those of tests run in the same
            # simulation. Test cases of HDL test benches have no cocotb module.
            if not isinstance(suite, TestSuiteWrapper):
                continue
            module_file = getattr(suite._test_case, "cocotb_module_file", None)
            suite_history = history.get(suite.name)
            if module_file is None or not suite_history:
                continue
            start_times = [test["start_time"] for test in suite_history.values()]
            if None in start_times or _modified_after(
                min(start_times), {module_file} | shared_files
            ):
                changed.add(suite.name)
        return changed


def _modified_after(start_time, file_names):
    """Returns whether any of the files was modified after start_time"""
    for file_name in file_names:
        try:
            if os.stat(file_name).st_mtime > start_time:
                return True
        except OSError:  # Removed since it was imported
            continue
    return False

import inspect
import os
from typing import Optional

import cocotb
from vunit import VUnit
from vunit.test.list import TestList

from ..utils.compat import COCOTB_SUPPORTS_NVC
from ..utils.mod_utils import import_mod, project_python_files
from .library import VCSTLibrary

# VUnit 4.x adds the VHDL builtins unless compile_builtins=False, VUnit 5 only when asked to
_VUNIT_HAS_COMPILE_BUILTINS = "compile_builtins" in inspect.signature(VUnit.__init__).parameters


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
        """
        depending_on_change = super()._get_test_list_depending_on_change(test_list)
        selected = {suite.name for suite in depending_on_change}
        shared_files = project_python_files() - self._cocotb_module_files

        new_test_list = TestList()
        for suite in test_list:
            if suite.name in selected or self._python_changed(suite, shared_files):
                new_test_list.add_suite(suite)
        return new_test_list

    def _python_changed(self, suite, shared_files):
        """
        Returns whether a Python file of the test suite was modified after its tests last ran. A suite without
        history is not asked, as VUnit selects it.
        """
        # VUnit wraps each test case in a test suite of its own
        module_file = getattr(getattr(suite, "_test_case", suite), "cocotb_module_file", None)
        history = self._test_history.get(suite.name)
        if module_file is None or not history:
            return False
        start_times = [test["start_time"] for test in history.values()]
        if None in start_times:
            return True
        start_time = min(start_times)
        for file_name in {module_file} | shared_files:
            try:
                if os.stat(file_name).st_mtime > start_time:
                    return True
            except OSError:  # Removed since it was imported
                continue
        return False

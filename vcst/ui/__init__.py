import inspect
from typing import Optional

from vunit import VUnit

from .library import VCSTLibrary
from ..utils.mod_utils import import_mod

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
                vcst_obj = super().from_argv(argv=argv, compile_builtins=False, vhdl_standard=vhdl_standard)
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
        top_level = None
        top_level_type = None
        top_level_library = None

        if cocotb_module is None:
           cocotb_module = import_mod(cocotb_module_location)

        if hasattr(cocotb_module, "top_level"):
            top_level = getattr(cocotb_module, "top_level")
        else:
            raise RuntimeError(f"top_level not defined in cocotb module {cocotb_module}")

        if hasattr(cocotb_module, "top_level_type"):
            top_level_type = getattr(cocotb_module, "top_level_type")
        else:
            raise RuntimeError(f"top_level_type not defined in cocotb module {cocotb_module}")

        if hasattr(cocotb_module, "top_level_library"):
            top_level_library = getattr(cocotb_module, "top_level_library")
        else:
            raise RuntimeError(f"top_level_library not defined in cocotb module {cocotb_module}")

        if not isinstance(top_level, str):
            raise RuntimeError(f"top_level defined in cocotb module should be a string {cocotb_module}")

        if not isinstance(top_level_type, str):
            raise RuntimeError(f"top_level_type defined in cocotb module should be a string {cocotb_module}")

        if not isinstance(top_level_library, str):
            raise RuntimeError(f"top_level_library defined in cocotb module should be a string {cocotb_module}")

        if top_level_type not in ("entity", "module"):
            raise RuntimeError(f"Invalid top level type {top_level_type} in cocotb module {cocotb_module} specified. Please specify either entity or module.")

        library = self.library(top_level_library)
        top_level_design_unit = None

        if top_level_type == "entity":
            top_level_design_unit = library.entity(top_level, test_bench=False)
        else:
            top_level_design_unit = library.module(top_level, test_bench=False)

        return library.add_cocotb_testbench(top_level_design_unit, cocotb_module, cocotb_module_location)

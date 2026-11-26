import logging

from vunit.ui.library import Library

from ..test.bench import CocoTestBench

LOGGER = logging.getLogger(__name__)


class VCSTLibrary(Library):
    def add_cocotb_testbench(self, design_unit, cocotb_module, cocotb_module_location):
        """
        Adds a test bench running the tests of cocotb_module with design_unit as top level.
        """
        # VUnit adds a test bench of its own for each top level, which this one replaces. A test bench
        # of an earlier cocotb module would be replaced too, or fail to be set up.
        try:
            existing = self._test_bench_list.get_test_bench(self._library_name, design_unit.name)
        except KeyError:
            existing = None
        if isinstance(existing, CocoTestBench):
            if existing.cocotb_module_location == cocotb_module_location:
                # The same module again, which is harmless
                return self.test_bench(design_unit.name)
            raise RuntimeError(
                f"The top level {design_unit.name} of library {self._library_name} has the cocotb "
                f"module {existing.cocotb_module_location} already, so {cocotb_module_location} "
                "can't be added. VCST supports one cocotb module for each top level."
            )
        # The database holds the test history, from which --seed repeat takes the seeds of the previous run
        test_bench = CocoTestBench(
            design_unit,
            cocotb_module,
            cocotb_module_location,
            database=self._test_bench_list._database,
        )
        self._test_bench_list._add_test_bench(test_bench)
        return self.test_bench(design_unit.name)

    def entity(self, name, test_bench=True):
        """
        Get an entity of name within the library. Returns a TestBench object if test_bench is true
        otherwise returns a DesignUnit.
        """
        name = name.lower()
        library = self._project.get_library(self._library_name)
        if not library.has_entity(name):
            raise KeyError(name)

        if test_bench:
            return self.test_bench(name)

        return library._entities[name]

    def module(self, name, test_bench=True):
        """
        Get a module of name within the library. Returns a TestBench object if test_bench is true
        otherwise returns a DesignUnit.
        """
        library = self._project.get_library(self._library_name)
        if name not in library.modules:
            raise KeyError(name)

        if test_bench:
            return self.test_bench(name)

        return library.modules[name]

"""
What a user gets from VCSTLibrary.add_cocotb_testbench when the top level has a cocotb module already.
"""

import types
import unittest
from collections import OrderedDict

from vcst.ui.library import VCSTLibrary


class FakeDesignUnit:
    """A design unit as far as test benches use it, with VUnit's check that there is one architecture callback"""

    original_file_name = file_name = "dut.vhd"
    library_name = "lib"
    generic_names = ()

    def __init__(self, name, is_entity):
        self.name = name
        self.is_entity = is_entity
        self.architecture_names = {"rtl": "dut.vhd"} if is_entity else {}
        self._callback = None

    def set_add_architecture_callback(self, callback):
        assert self._callback is None
        self._callback = callback


class FakeTestBenchList:
    """The test benches of VUnit, which keeps one for each design unit name"""

    def __init__(self):
        self._database = None
        self.test_benches = OrderedDict()

    def _add_test_bench(self, test_bench):
        self.test_benches[test_bench.name] = test_bench

    def get_test_bench(self, library_name, name):
        return self.test_benches[name]


def cocotb_module():
    return types.SimpleNamespace(top_level="dut")


class OneCocotbModulePerTopLevel(unittest.TestCase):
    def library(self):
        test_benches = FakeTestBenchList()
        library = VCSTLibrary("lib", None, None, test_benches)
        # test_bench() of VUnit's Library looks the test bench up in its project
        library.test_bench = lambda name: test_benches.test_benches[name]
        return library

    def test_a_second_cocotb_module_for_the_top_level_is_refused_by_name(self):
        for is_entity in (True, False):
            with self.subTest(is_entity=is_entity):
                library = self.library()
                design_unit = FakeDesignUnit("dut", is_entity)
                library.add_cocotb_testbench(design_unit, cocotb_module(), "/first/test_dut")
                with self.assertRaises(RuntimeError) as context:
                    library.add_cocotb_testbench(design_unit, cocotb_module(), "/second/test_dut")
                message = str(context.exception)
                self.assertIn("dut", message)
                self.assertIn("/first/test_dut", message)
                self.assertIn("/second/test_dut", message)

    def test_the_first_cocotb_module_is_kept_when_a_second_is_refused(self):
        library = self.library()
        design_unit = FakeDesignUnit("dut", True)
        library.add_cocotb_testbench(design_unit, cocotb_module(), "/first/test_dut")
        with self.assertRaises(RuntimeError):
            library.add_cocotb_testbench(design_unit, cocotb_module(), "/second/test_dut")
        kept = library.test_bench("dut")
        self.assertEqual(kept.cocotb_module_location, "/first/test_dut")

    def test_the_test_bench_of_vunit_is_replaced_and_other_top_levels_are_independent(self):
        library = self.library()
        library._test_bench_list.test_benches["dut"] = object()  # VUnit's own test bench of dut
        library.add_cocotb_testbench(FakeDesignUnit("dut", True), cocotb_module(), "/a/test_dut")
        library.add_cocotb_testbench(
            FakeDesignUnit("other", True), cocotb_module(), "/b/test_other"
        )
        self.assertEqual(sorted(library._test_bench_list.test_benches), ["dut", "other"])


if __name__ == "__main__":
    unittest.main()

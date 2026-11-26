"""
What a user gets from add_cocotb_testbench when the cocotb module is set up wrongly: an error which names what is wrong.
"""

import types
import unittest
from unittest import mock

import vcst.ui
from vcst.ui import VCST


class FakeLibrary:
    def __init__(self):
        self.calls = []

    def entity(self, name, test_bench=True):
        self.calls.append(("entity", name, test_bench))
        return f"entity {name}"

    def module(self, name, test_bench=True):
        self.calls.append(("module", name, test_bench))
        return f"module {name}"

    def add_cocotb_testbench(self, design_unit, cocotb_module, location):
        self.calls.append(("add", design_unit, location))
        return "test bench"


class FakeUI:
    """What add_cocotb_testbench needs of a VCST object, which otherwise needs a simulator"""

    def __init__(self, simulator_name=None):
        self._simulator_class = (
            types.SimpleNamespace(name=simulator_name) if simulator_name else None
        )
        self.libraries = {}

    def library(self, name):
        return self.libraries.setdefault(name, FakeLibrary())


def cocotb_module(**attributes):
    values = {"top_level": "dut", "top_level_type": "entity", "top_level_library": "lib"}
    values.update(attributes)
    module = types.ModuleType("my_cocotb_module")
    for name, value in values.items():
        if value is not None:
            setattr(module, name, value)
    return module


def add(module, ui=None):
    ui = ui or FakeUI()
    return ui, VCST.add_cocotb_testbench(ui, "/path/to/my_cocotb_module", module)


class AddCocotbTestbench(unittest.TestCase):
    def test_a_missing_variable_is_named(self):
        for name in ("top_level", "top_level_type", "top_level_library"):
            with self.subTest(name=name):
                with self.assertRaises(RuntimeError) as context:
                    add(cocotb_module(**{name: None}))
                self.assertIn(f"{name} not defined", str(context.exception))
                self.assertIn("my_cocotb_module", str(context.exception))

    def test_a_variable_which_isnt_a_string_is_named(self):
        for name in ("top_level", "top_level_type", "top_level_library"):
            with self.subTest(name=name):
                with self.assertRaises(RuntimeError) as context:
                    add(cocotb_module(**{name: 5}))
                self.assertIn(
                    f"{name} defined in cocotb module should be a string", str(context.exception)
                )

    def test_a_top_level_type_other_than_entity_or_module_is_refused(self):
        with self.assertRaises(RuntimeError) as context:
            add(cocotb_module(top_level_type="architecture"))
        self.assertIn("architecture", str(context.exception))
        self.assertIn("entity", str(context.exception))
        self.assertIn("module", str(context.exception))

    def test_an_entity_is_added_as_a_design_unit_of_its_library(self):
        ui, result = add(
            cocotb_module(top_level="counter", top_level_type="entity", top_level_library="work")
        )
        self.assertEqual(result, "test bench")
        self.assertEqual(
            ui.libraries["work"].calls,
            [("entity", "counter", False), ("add", "entity counter", "/path/to/my_cocotb_module")],
        )

    def test_a_module_is_added_as_a_design_unit_of_its_library(self):
        ui, _ = add(
            cocotb_module(top_level="counter", top_level_type="module", top_level_library="work")
        )
        self.assertEqual(ui.libraries["work"].calls[0], ("module", "counter", False))

    def test_nvc_is_refused_with_a_cocotb_which_doesnt_support_it(self):
        with mock.patch.object(vcst.ui, "COCOTB_SUPPORTS_NVC", False):
            with self.assertRaises(RuntimeError) as context:
                add(cocotb_module(), FakeUI("nvc"))
        self.assertIn("NVC needs cocotb 1.9 or later", str(context.exception))
        with mock.patch.object(vcst.ui, "COCOTB_SUPPORTS_NVC", True):
            add(cocotb_module(), FakeUI("nvc"))
        with mock.patch.object(vcst.ui, "COCOTB_SUPPORTS_NVC", False):
            add(cocotb_module(), FakeUI("ghdl"))


if __name__ == "__main__":
    unittest.main()

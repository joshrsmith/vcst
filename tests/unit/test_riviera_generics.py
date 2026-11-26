"""
VCST gives the generics of a VHDL top level to Riviera-PRO as VUnit does, except that a list becomes an aggregate. A
Verilog top level also gets its strings quoted, which Riviera-PRO needs for string parameters.
"""
import importlib.util
import unittest

import vunit.sim_if.rivierapro

from vcst.monkey_patching import rivierapro


def vunit_format_generic():
    """Returns VUnit's own format_generic, from a fresh copy of its module, as VCST replaces it in the original"""
    path = vunit.sim_if.rivierapro.__file__
    spec = importlib.util.spec_from_file_location("vunit.sim_if.rivierapro_original", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.format_generic


class FormatGeneric(unittest.TestCase):
    def setUp(self):
        self.addCleanup(setattr, rivierapro._formatting, "quote_strings", False)
        rivierapro._formatting.quote_strings = False

    def test_values_of_a_vhdl_top_level_are_formatted_as_vunit_does(self):
        reference = vunit_format_generic()
        values = [0, 16, -3, 3.5, True, False, "FAST", "x\"00FF\"", "'1'", "(FOO,BAR)", "data/file.txt", "hello world",
                  "a  b", " ", "", 1e-9]
        for value in values:
            with self.subTest(value=value):
                self.assertEqual(rivierapro.format_generic(value), reference(value))

    def test_lists_and_tuples_become_aggregates(self):
        self.assertEqual(rivierapro.format_generic(["FOO", "BAR"]), "(FOO,BAR)")
        self.assertEqual(rivierapro.format_generic(("SLOW", "FAST")), "(SLOW,FAST)")
        self.assertEqual(rivierapro.format_generic([1, 2, 3]), "(1,2,3)")

    def test_items_of_an_aggregate_are_formatted_as_values(self):
        self.assertEqual(rivierapro.format_generic(["a b", "c"]), '("a b",c)')
        self.assertEqual(rivierapro.format_generic([["a", "b"], ["c", "d"]]), "((a,b),(c,d))")

    def test_strings_of_a_verilog_top_level_are_quoted(self):
        rivierapro._formatting.quote_strings = True
        self.assertEqual(rivierapro.format_generic("hello"), '"hello"')
        self.assertEqual(rivierapro.format_generic("hello world"), '"hello world"')

    def test_numbers_of_a_verilog_top_level_are_not_quoted(self):
        rivierapro._formatting.quote_strings = True
        self.assertEqual(rivierapro.format_generic(3), "3")


if __name__ == "__main__":
    unittest.main()

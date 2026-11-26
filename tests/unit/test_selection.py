"""
VCST selects the tests of a cocotb run by name, and must select exactly the tests it was asked to, however they are named:
a name which is the end of another name, or contains characters special to regular expressions, must not select other
tests. The tests are real cocotb tests, found as VCST finds them.
"""

import importlib
import os
import re
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from vcst.utils.compat import COCOTB2, find_cocotb_tests, test_selection_environ

MAIN_MODULE = """
import cocotb
from vcst_unit_other import imported

@cocotb.test()
async def plain(dut):
    pass

@cocotb.test()
async def fail(dut):
    pass

@cocotb.test()
async def expect_fail(dut):
    pass

@cocotb.test()
async def tail_plain(dut):
    pass
"""

OTHER_MODULE = """
import cocotb

@cocotb.test()
async def imported(dut):
    pass
"""

# Names cocotb 2 allows, to be selected one at a time
NAMED_MODULE = """
import cocotb

def make(name):
    @cocotb.test(name=name)
    async def test(dut):
        pass
    return test

for index, name in enumerate(["a.b", "aXb", "a+b", "aab", "(x)", "a|b", "ab", "x*", "[y]", "plain", "plain2", "end$",
                              "^start"]):
    globals()[f"test_{index}"] = make(name)
"""


class Modules:
    """Writes modules to a directory, imports them and removes them from sys.modules when done"""

    def __init__(self, test_case, **sources):
        directory = Path(tempfile.mkdtemp(prefix="vcst_unit_"))
        test_case.addCleanup(shutil.rmtree, directory, True)
        for name, source in sources.items():
            (directory / f"{name}.py").write_text(textwrap.dedent(source))
        sys.path.insert(0, str(directory))
        test_case.addCleanup(sys.path.remove, str(directory))
        importlib.invalidate_caches()
        self.modules = {}
        for name in sources:
            test_case.addCleanup(sys.modules.pop, name, None)
        for name in sources:
            self.modules[name] = importlib.import_module(name)


@unittest.skipUnless(COCOTB2, "cocotb 2 selects tests with a regular expression")
class Cocotb2Filter(unittest.TestCase):
    def select(self, module, names, test_modules=None):
        """Returns the names of the tests the filter VCST gives cocotb selects, among all tests of the module"""
        environ = test_selection_environ(module.__name__, names, "top", None, test_modules)
        test_filter = re.compile(environ["COCOTB_TEST_FILTER"])
        tests = [
            test
            for obj, test_names in find_cocotb_tests(module)
            for test in self.expand_generators(obj, test_names)
        ]
        return sorted(test.name for test in tests if test_filter.search(test.fullname))

    @staticmethod
    def expand_generators(obj, test_names):
        import cocotb.regression

        generate = getattr(obj, "generate_tests", None)
        return (
            list(generate()) if generate and not isinstance(obj, cocotb.regression.Test) else [obj]
        )

    def test_only_the_tests_asked_for_are_selected(self):
        modules = Modules(self, vcst_unit_main=MAIN_MODULE, vcst_unit_other=OTHER_MODULE).modules
        main = modules["vcst_unit_main"]
        names = {
            name.name: name for _, test_names in find_cocotb_tests(main) for name in test_names
        }
        test_modules = {name: test.module for name, test in names.items()}
        for wanted in (
            ["plain"],
            ["fail"],
            ["expect_fail"],
            ["fail", "tail_plain"],
            ["imported"],
            ["plain", "imported"],
        ):
            with self.subTest(wanted=wanted):
                self.assertEqual(self.select(main, wanted, test_modules), sorted(wanted))

    def test_names_with_characters_special_to_regular_expressions(self):
        module = Modules(self, vcst_unit_named=NAMED_MODULE).modules["vcst_unit_named"]
        all_names = sorted(
            name.name for _, test_names in find_cocotb_tests(module) for name in test_names
        )
        self.assertGreater(len(all_names), 10)
        for wanted in all_names:
            with self.subTest(wanted=wanted):
                self.assertEqual(self.select(module, [wanted]), [wanted])
        self.assertEqual(self.select(module, all_names), all_names)

    def test_an_environment_variable_of_cocotb_1_isnt_set(self):
        environ = test_selection_environ("module", ["test"], "top", None)
        # COCOTB_TESTCASE is removed, as cocotb refuses to run when it is set as well as COCOTB_TEST_FILTER
        self.assertIn("COCOTB_TESTCASE", environ)
        self.assertIsNone(environ["COCOTB_TESTCASE"])
        self.assertNotIn("TESTCASE", environ)

    def test_no_seed_is_left_to_cocotb(self):
        self.assertNotIn(
            "COCOTB_RANDOM_SEED", test_selection_environ("module", ["test"], "top", None)
        )
        self.assertEqual(
            test_selection_environ("module", ["test"], "top", 42)["COCOTB_RANDOM_SEED"], "42"
        )


@unittest.skipIf(COCOTB2, "cocotb 1.x selects tests by their names in the module")
class Cocotb1Selection(unittest.TestCase):
    def test_the_tests_and_module_are_given_to_cocotb(self):
        environ = test_selection_environ("my_module", ["one", "two"], "top", 7)
        self.assertEqual(environ["MODULE"], "my_module")
        self.assertEqual(environ["TESTCASE"].split(","), ["one", "two"])
        self.assertEqual(environ["TOPLEVEL"], "top")
        self.assertEqual(environ["RANDOM_SEED"], "7")

    def test_no_seed_is_left_to_cocotb(self):
        self.assertNotIn("RANDOM_SEED", test_selection_environ("my_module", ["one"], "top", None))

    def test_x_and_z_resolve_to_zero_unless_the_user_chose(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("COCOTB_RESOLVE_X", None)
            self.assertEqual(
                test_selection_environ("m", ["t"], "top", None)["COCOTB_RESOLVE_X"], "ZEROS"
            )
            os.environ["COCOTB_RESOLVE_X"] = "ERROR"
            self.assertNotIn("COCOTB_RESOLVE_X", test_selection_environ("m", ["t"], "top", None))


if __name__ == "__main__":
    unittest.main()

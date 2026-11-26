"""
Which tests --changed selects: those VUnit selects because of their HDL files, and those whose Python files changed. If
what VCST relies on of VUnit is not as expected, all tests are selected, or a warning says that Python files are ignored.
"""

import contextlib
import io
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from vunit import VUnit
from vunit.test.list import TestList, TestSuiteWrapper

import vcst.ui
from vcst.ui import VCST

HOOK = "_get_test_list_depending_on_change"
# When the tests last ran. Files modified later changed since.
START = 1000.0


def suite(name, module_file):
    """A test suite of a cocotb test"""
    return TestSuiteWrapper(types.SimpleNamespace(name=name, cocotb_module_file=module_file))


def history(*names):
    return {name: {"test": {"start_time": START}} for name in names}


class SelectionTestCase(unittest.TestCase):
    """Files of a project with two cocotb modules and a file they share, and a VCST object to select tests with"""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.module_a = self.file("test_a.py")
        self.module_b = self.file("test_b.py")
        self.shared = self.file("shared.py")
        self.project_files = {self.module_a, self.module_b, self.shared}
        patcher = mock.patch.object(
            vcst.ui, "project_python_files", lambda: set(self.project_files)
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def file(self, name, modified=START - 500):
        path = self.directory / name
        path.write_text("")
        os.utime(path, (modified, modified))
        return str(path)

    def modify(self, path):
        os.utime(path, (START + 500, START + 500))

    def ui(self, test_history, selected_by_vunit=()):
        ui = object.__new__(VCST)
        ui._cocotb_module_files = {self.module_a, self.module_b}
        ui._test_history = test_history
        self.selected_by_vunit = TestList()
        for test_suite in selected_by_vunit:
            self.selected_by_vunit.add_suite(test_suite)
        return ui

    def select(self, ui, *suites):
        test_list = TestList()
        for test_suite in suites:
            test_list.add_suite(test_suite)
        output = io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                mock.patch.object(VUnit, HOOK, create=True, return_value=self.selected_by_vunit)
            )
            stack.enter_context(contextlib.redirect_stdout(output))
            selected = ui._get_test_list_depending_on_change(test_list)
        return [s.name for s in selected], output.getvalue()


class ChangedSelection(SelectionTestCase):
    def test_a_cocotb_module_modified_since_its_tests_ran_selects_only_its_tests(self):
        a, b = suite("a", self.module_a), suite("b", self.module_b)
        self.modify(self.module_a)
        selected, output = self.select(self.ui(history("a", "b")), a, b)
        self.assertEqual((selected, output), (["a"], ""))

    def test_a_python_file_shared_by_the_modules_selects_the_tests_of_all(self):
        a, b = suite("a", self.module_a), suite("b", self.module_b)
        self.modify(self.shared)
        selected, _ = self.select(self.ui(history("a", "b")), a, b)
        self.assertEqual(selected, ["a", "b"])

    def test_nothing_modified_selects_nothing(self):
        a, b = suite("a", self.module_a), suite("b", self.module_b)
        selected, output = self.select(self.ui(history("a", "b")), a, b)
        self.assertEqual((selected, output), ([], ""))

    def test_tests_selected_by_vunit_stay_selected(self):
        a, b = suite("a", self.module_a), suite("b", self.module_b)
        selected, _ = self.select(self.ui(history("a", "b"), selected_by_vunit=[b]), a, b)
        self.assertEqual(selected, ["b"])

    def test_a_removed_file_is_ignored(self):
        a = suite("a", self.module_a)
        os.remove(self.shared)
        selected, output = self.select(self.ui(history("a")), a)
        self.assertEqual((selected, output), ([], ""))

    def test_a_suite_that_isnt_a_wrapped_test_case_is_not_looked_into(self):
        # As the suite of HDL tests run in the same simulation, which VUnit selects by itself
        a = suite("a", self.module_a)
        same_sim = types.SimpleNamespace(name="same_sim")
        self.modify(self.module_a)
        selected, output = self.select(self.ui(history("a", "same_sim")), a, same_sim)
        self.assertEqual((selected, output), (["a"], ""))

    def test_a_test_case_without_cocotb_module_is_not_selected_for_its_python_files(self):
        hdl = TestSuiteWrapper(types.SimpleNamespace(name="hdl"))
        self.modify(self.shared)
        selected, output = self.select(self.ui(history("hdl")), hdl)
        self.assertEqual((selected, output), ([], ""))


class UnexpectedVUnit(SelectionTestCase):
    """What happens if VUnit is not as VCST relies on"""

    def assert_everything_selected(self, ui):
        a, b = suite("a", self.module_a), suite("b", self.module_b)
        selected, output = self.select(ui, a, b)
        self.assertEqual(selected, ["a", "b"])
        self.assertIn("WARNING", output)
        self.assertIn("selects all tests", output)

    def test_without_test_history_all_tests_are_selected(self):
        ui = self.ui(history("a", "b"))
        del ui._test_history
        self.assert_everything_selected(ui)

    def test_a_test_history_of_another_type_selects_all_tests(self):
        self.assert_everything_selected(self.ui(["not", "a", "dict"]))

    def test_a_test_history_without_start_times_selects_all_tests(self):
        self.assert_everything_selected(self.ui({"a": {"test": {}}, "b": {"test": {}}}))

    def test_a_wrapper_without_its_test_case_selects_all_tests(self):
        class Renamed(TestSuiteWrapper):
            """A wrapper that keeps its test case under another name"""

            def __init__(self, name):
                self.suite_name = name

            @property
            def name(self):
                return self.suite_name

        selected, output = self.select(self.ui(history("a")), Renamed("a"))
        self.assertEqual(selected, ["a"])
        self.assertIn("selects all tests", output)

    def test_without_the_wrapper_class_all_tests_are_selected(self):
        with mock.patch.object(vcst.ui, "TestSuiteWrapper", None):
            self.assert_everything_selected(self.ui(history("a", "b")))


class WarningWithoutVUnitHook(unittest.TestCase):
    def run_main(self, changed, with_hook):
        ui = object.__new__(VCST)
        ui._changed_requested = changed
        output = io.StringIO()
        with contextlib.ExitStack() as stack:
            if with_hook:
                stack.enter_context(mock.patch.object(VUnit, HOOK, create=True))
            elif hasattr(VUnit, HOOK):
                hook = VUnit.__dict__[HOOK]
                delattr(VUnit, HOOK)
                stack.callback(setattr, VUnit, HOOK, hook)
            main = stack.enter_context(mock.patch.object(VUnit, "main", return_value="ran"))
            stack.enter_context(contextlib.redirect_stdout(output))
            result = ui.main(post_run="post_run")
        return result, main, output.getvalue()

    def test_changed_without_the_hook_warns_and_still_runs(self):
        result, main, output = self.run_main(changed=True, with_hook=False)
        self.assertEqual(result, "ran")
        main.assert_called_once_with(post_run="post_run")
        self.assertIn("WARNING", output)
        self.assertIn("only considers HDL files", output)

    def test_no_warning_with_the_hook(self):
        _, _, output = self.run_main(changed=True, with_hook=True)
        self.assertEqual(output, "")

    def test_no_warning_without_changed(self):
        _, _, output = self.run_main(changed=False, with_hook=False)
        self.assertEqual(output, "")


if __name__ == "__main__":
    unittest.main()

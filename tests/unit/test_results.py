"""
How VCST turns the results file cocotb writes into the outcomes of the VUnit tests. VUnit counts a test it ran as failed
unless it passed, so a test which ended without a failure passes, also if it skipped itself.
"""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from vunit.test.report import FAILED, PASSED, SKIPPED

from vcst.test.suites import CocoTestRun

RESULTS = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites name="results">
  <testsuite name="all" package="all">
    {testcases}
  </testsuite>
</testsuites>
"""


def test_run(test_cases, result_names=None):
    return CocoTestRun(
        vhdl=True,
        top_level="top",
        simulator_if=SimpleNamespace(name="ghdl"),
        config=None,
        elaborate_only=False,
        cocotb_module=None,
        cocotb_module_location="/some/module",
        test_suite_name="lib.top",
        test_cases=test_cases,
        result_names=result_names,
    )


class ReadTestResults(unittest.TestCase):
    def read(self, run, testcases):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.xml"
            path.write_text(RESULTS.format(testcases=testcases))
            return run._read_test_results(str(path))

    def test_a_test_without_failure_passes_and_one_with_failure_or_error_fails(self):
        run = test_run(["passes", "fails", "errors"])
        results = self.read(
            run,
            """
            <testcase name="passes" classname="module" time="0.1" sim_time_ns="1" ratio_time="1"/>
            <testcase name="fails" classname="module" time="0.1" sim_time_ns="1" ratio_time="1">
              <failure message="assert 1 == 2"/>
            </testcase>
            <testcase name="errors" classname="module" time="0.1" sim_time_ns="1" ratio_time="1">
              <error message="exception"/>
            </testcase>""",
        )
        self.assertEqual(results, {"passes": PASSED, "fails": FAILED, "errors": FAILED})

    def test_a_test_which_skipped_itself_passes(self):
        run = test_run(["skipped"])
        results = self.read(
            run,
            """
            <testcase name="skipped" classname="module" time="0.1" sim_time_ns="1" ratio_time="1">
              <skipped message="not today"/>
            </testcase>""",
        )
        self.assertEqual(results, {"skipped": PASSED})

    def test_tests_are_found_by_the_name_cocotb_reports_them_with(self):
        # cocotb 1.x reports a test by its __qualname__, which can differ from the name VCST selects it by
        run = test_run(["selected_name"], result_names={"reported_name": "selected_name"})
        results = self.read(run, '<testcase name="reported_name" classname="module"/>')
        self.assertEqual(results, {"selected_name": PASSED})

    def test_results_of_other_tests_are_ignored(self):
        run = test_run(["mine"])
        results = self.read(
            run,
            """
            <testcase name="mine" classname="module"/>
            <testcase name="not_mine" classname="module"><failure message="x"/></testcase>""",
        )
        self.assertEqual(results, {"mine": PASSED})

    def test_without_a_results_file_the_tests_fail(self):
        # The simulation ended without cocotb reporting, e.g. because the simulator crashed or cocotb didn't load
        run = test_run(["one", "two"])
        self.assertEqual(
            run._read_test_results("/no/such/file.xml"), {"one": FAILED, "two": FAILED}
        )


class CheckResults(unittest.TestCase):
    """cocotb's results stand whatever the exit status of the simulator is"""

    def check(self, results, sim_ok):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            done, checked = test_run(list(results))._check_results(dict(results), sim_ok)
        return done, checked, output.getvalue()

    def test_a_passed_test_stays_passed_if_the_simulator_exits_with_a_non_zero_status(self):
        # As a test that expects the HDL to end the simulation does, or a simulator that fails when shutting down
        done, results, output = self.check({"test": PASSED}, sim_ok=False)
        self.assertEqual(results, {"test": PASSED})
        self.assertFalse(done)  # post_check still runs
        self.assertIn("non-zero status", output)

    def test_a_clean_exit_gives_no_warning(self):
        done, results, output = self.check({"test": PASSED}, sim_ok=True)
        self.assertEqual((done, results, output), (False, {"test": PASSED}, ""))

    def test_a_failed_test_is_final_whatever_the_exit_status(self):
        for sim_ok in (True, False):
            done, results, _ = self.check({"failed": FAILED, "passed": PASSED}, sim_ok)
            self.assertEqual((done, results), (True, {"failed": FAILED, "passed": PASSED}))

    def test_a_skipped_test_stays_skipped(self):
        done, results, output = self.check({"test": SKIPPED}, sim_ok=False)
        self.assertEqual((done, results, output), (False, {"test": SKIPPED}, ""))


if __name__ == "__main__":
    unittest.main()

"""
How VCST turns the results file cocotb writes into the outcomes of the VUnit tests. VUnit counts a test it ran as failed
unless it passed, so a test which ended without a failure passes, also if it skipped itself.
"""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from vunit.test.report import FAILED, PASSED

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


if __name__ == "__main__":
    unittest.main()

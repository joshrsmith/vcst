"""
Runs a VCST test suite whose tests are expected to have specific outcomes, some of them failures, and makes the run
script pass only when every test has its expected outcome.
"""

import sys


def main_checking_outcomes(ui, expected):
    """
    Runs ui.main() and exits with 0 only if every test has the outcome in expected, which maps full test names
    (library.test_bench.test, with the configuration if any) to "passed", "failed" or "skipped". When tests are
    selected on the command line, only the tests run are checked.
    """
    mismatches = []
    checked = []

    def post_run(results):
        report = results.get_report()
        tests = report.tests
        full_run = (
            ui._args.test_patterns == ["*"]
            and not ui._args.with_attributes
            and not ui._args.without_attributes
        )

        for name, test in tests.items():
            if name not in expected:
                mismatches.append(f"{name}: not in the expected outcomes")
            elif test.status != expected[name]:
                mismatches.append(f"{name}: expected {expected[name]}, got {test.status}")

        if full_run:
            for name in expected:
                if name not in tests:
                    mismatches.append(f"{name}: expected {expected[name]}, but the test didn't run")

        checked.append(True)

    try:
        ui.main(post_run=post_run)
    except SystemExit:
        if not checked:
            # Not a test run, e.g. --list or a failed compilation, so VUnit's exit code stands
            raise

    print("=" * 70)
    if mismatches:
        print("Unexpected test outcomes:")
        for mismatch in mismatches:
            print(f"  {mismatch}")
        sys.exit(1)
    print("All tests had their expected outcomes.")
    sys.exit(0)

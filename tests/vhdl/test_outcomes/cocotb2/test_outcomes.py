# Tests with known outcomes, checked by run.py, showing that VCST selects each test exactly and reports what cocotb
# reports for it.
import atexit
import os

import cocotb
from cocotb.regression import SimFailure
from cocotb.triggers import Timer

from vcst.utils import set_top_level

# The names of the tests run in this simulation. VCST runs each test in a simulation of its own, which run_alone
# checks, so that selecting a test by name also selecting other tests is noticed.
_tests_run = []


async def run_alone(name):
    _tests_run.append(name)
    assert _tests_run == [name], f"{name} ran in the same simulation as {_tests_run[:-1]}"
    await Timer(1, unit="ns")


# Test name -> outcome expected by run.py
EXPECTED_OUTCOMES = {}


def expect(outcome, *names):
    for name in names:
        EXPECTED_OUTCOMES[name] = outcome


@cocotb.test()
async def passing(dut):
    await run_alone("passing")


@cocotb.test()
async def failing_assert(dut):
    await run_alone("failing_assert")
    assert False, "expected failure"


@cocotb.test()
async def erroring(dut):
    await run_alone("erroring")
    raise ValueError("expected error")


# Fails when cocotb starts it, as nothing gives the argument. cocotb 2.1 reports this as an error rather than a
# failure.
@cocotb.test()
async def fails_to_start(dut, missing_argument):
    await run_alone("fails_to_start")


# A suffix of other test names, e.g. erroring, which must not be selected with it
@cocotb.test()
async def ing(dut):
    await run_alone("ing")


@cocotb.test(expect_fail=True)
async def expect_fail_failing(dut):
    await run_alone("expect_fail_failing")
    assert False


@cocotb.test(expect_fail=True)
async def expect_fail_passing(dut):
    await run_alone("expect_fail_passing")


@cocotb.test(expect_error=ValueError)
async def expect_error_raised(dut):
    await run_alone("expect_error_raised")
    raise ValueError("expected error")


@cocotb.test(expect_error=ValueError)
async def expect_error_not_raised(dut):
    await run_alone("expect_error_not_raised")


# The HDL ends the simulation with an assertion failure, so the simulator exits with a non-zero status. cocotb reports
# the test as passed if it expected that, and as failed if it didn't.
@cocotb.test(expect_error=SimFailure)
async def expect_sim_failure_ended(dut):
    await run_alone("expect_sim_failure_ended")
    dut.trigger_failure.value = 1
    await Timer(10, unit="ns")


@cocotb.test()
async def sim_failure_not_expected(dut):
    await run_alone("sim_failure_not_expected")
    dut.trigger_failure.value = 1
    await Timer(10, unit="ns")


# Fails, as the simulation doesn't end
@cocotb.test(expect_error=SimFailure)
async def expect_sim_failure_not_ended(dut):
    await run_alone("expect_sim_failure_not_ended")


# The simulator exits with a non-zero status when it shuts down, after cocotb wrote its results. The test passed.
@cocotb.test()
async def simulator_fails_after_test(dut):
    await run_alone("simulator_fails_after_test")
    atexit.register(lambda: os._exit(3))


@cocotb.test(timeout_time=10, timeout_unit="ns")
async def timing_out(dut):
    await run_alone("timing_out")
    await Timer(100, unit="ns")


# cocotb runs a test selected by name even if it is marked skip, as VCST selects every test by name
@cocotb.test(skip=True)
async def skipped(dut):
    await run_alone("skipped")


# The names of parametrized tests contain "/", "=" and "."
@cocotb.test()
@cocotb.parametrize(value=[1, 2.5])
async def parametrized(dut, value):
    await run_alone(f"parametrized/value={value}")
    assert value == 1


expect(
    "passed",
    "passing",
    "ing",
    "expect_fail_failing",
    "expect_error_raised",
    "expect_sim_failure_ended",
    "simulator_fails_after_test",
    "skipped",
    "parametrized/value=1",
)
expect(
    "failed",
    "failing_assert",
    "erroring",
    "fails_to_start",
    "expect_fail_passing",
    "expect_error_not_raised",
    "sim_failure_not_expected",
    "expect_sim_failure_not_ended",
    "timing_out",
    "parametrized/value=2.5",
)

if hasattr(cocotb, "xfail"):
    # cocotb 2.1 and later
    @cocotb.test()
    @cocotb.xfail(raises=ValueError)
    async def xfail_raised(dut):
        await run_alone("xfail_raised")
        raise ValueError("expected error")

    @cocotb.test()
    @cocotb.xfail(raises=ValueError)
    async def xfail_not_raised(dut):
        await run_alone("xfail_not_raised")

    # Passes, as a VUnit test that runs either passes or fails, and failing would fail the run
    @cocotb.test()
    async def skipped_at_runtime(dut):
        import pytest  # A dependency of cocotb 2.1

        await run_alone("skipped_at_runtime")
        pytest.skip("expected skip")

    expect("passed", "xfail_raised", "skipped_at_runtime")
    expect("failed", "xfail_not_raised")

# Tests defined in another module, which cocotb names after that module
from outcomes_imported import imported_failing, imported_passing  # noqa: E402, F401

expect("passed", "imported_passing")
expect("failed", "imported_failing")

set_top_level("outcomes_dut", "entity", "lib")

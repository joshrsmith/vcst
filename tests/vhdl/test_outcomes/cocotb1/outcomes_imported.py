# Tests imported by test_outcomes, which VCST runs as tests of the module importing them
import cocotb


@cocotb.test()
async def imported_passing(dut):
    from test_outcomes import run_alone  # Not at the top, as test_outcomes imports this module

    await run_alone("imported_passing")


@cocotb.test()
async def imported_failing(dut):
    from test_outcomes import run_alone

    await run_alone("imported_failing")
    assert False, "expected failure"

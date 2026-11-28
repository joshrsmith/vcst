import cocotb
import driver
from cocotb.triggers import Timer

from vcst.utils import set_top_level


@cocotb.test()
async def b_test(dut):
    # Waits, as the test is about --changed, not about tests that finish in no time (see zero_time in test_outcomes)
    await Timer(1, "ns")
    assert driver.regs.REGISTER_COUNT == 4


set_top_level("changed_b", "entity", "lib")

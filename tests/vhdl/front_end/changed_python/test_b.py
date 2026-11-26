import cocotb
import driver

from vcst.utils import set_top_level


@cocotb.test()
async def b_test(dut):
    assert driver.regs.REGISTER_COUNT == 4


set_top_level("changed_b", "entity", "lib")

# Another module named test_same, with the top level dut_b
import cocotb
from cocotb.triggers import Timer

from vcst.utils import set_top_level


@cocotb.test()
async def test_two(dut):
    await Timer(1, "ns")


set_top_level("dut_b", "entity", "lib")

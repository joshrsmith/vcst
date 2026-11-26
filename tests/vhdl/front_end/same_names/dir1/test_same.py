# A module named test_same, with the top level dut_a
import cocotb
from cocotb.triggers import Timer

from vcst.utils import set_top_level


@cocotb.test()
async def test_one(dut):
    await Timer(1, "ns")


set_top_level("dut_a", "entity", "lib")

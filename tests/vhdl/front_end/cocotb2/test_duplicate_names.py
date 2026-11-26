# Two tests with the same name, which VUnit can't tell apart, so VCST refuses them
import cocotb
from cocotb.triggers import Timer

from vcst.utils import set_top_level


@cocotb.test(name="duplicate")
async def first(dut):
    await Timer(1, unit="ns")


@cocotb.test(name="duplicate")
async def second(dut):
    await Timer(1, unit="ns")


set_top_level("front_end_dut", "entity", "lib")

# Tests of the iso_b top level, run at the same time as those of the other top level and configurations
import cocotb
from cocotb.triggers import Timer
from isolation_checks import check_environment

from vcst.utils import set_top_level


@cocotb.test()
async def first(dut):
    await Timer(1, "ns")
    check_environment(dut, __name__, "iso_b")


@cocotb.test()
async def second(dut):
    await Timer(1, "ns")
    check_environment(dut, __name__, "iso_b")


@cocotb.test()
async def third(dut):
    await Timer(1, "ns")
    check_environment(dut, __name__, "iso_b")


set_top_level("iso_b", "entity", "lib")

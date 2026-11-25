#Tests of the iso_a top level, run at the same time as those of the other top level and configurations
import cocotb
from cocotb.triggers import Timer
from vcst.utils import set_top_level
from isolation_checks import check_environment

@cocotb.test()
async def first(dut):
    await Timer(1, "ns")
    check_environment(dut, __name__, "iso_a")

@cocotb.test()
async def second(dut):
    await Timer(1, "ns")
    check_environment(dut, __name__, "iso_a")

@cocotb.test()
async def third(dut):
    await Timer(1, "ns")
    check_environment(dut, __name__, "iso_a")

set_top_level("iso_a", "entity", "lib")

#Tests of the iso_b top level, run at the same time as those of the other top level and configurations
import cocotb
from cocotb.triggers import Timer
from vcst.utils import set_top_level
from isolation_checks import check_environment

@cocotb.test()
async def first(dut):
    await Timer(1, units="ns")
    check_environment(dut, __name__, "iso_b", cocotb2=False)

@cocotb.test()
async def second(dut):
    await Timer(1, units="ns")
    check_environment(dut, __name__, "iso_b", cocotb2=False)

@cocotb.test()
async def third(dut):
    await Timer(1, units="ns")
    check_environment(dut, __name__, "iso_b", cocotb2=False)

set_top_level("iso_b", "entity", "lib")

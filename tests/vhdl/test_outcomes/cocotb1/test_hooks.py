#A test run with the pre_config and post_check hooks of the configurations in run.py
import cocotb
from cocotb.triggers import Timer
from vcst.utils import set_top_level

@cocotb.test()
async def hooked(dut):
    await Timer(1)

set_top_level("hooks_dut", "entity", "lib")

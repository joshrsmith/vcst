# Tests run by check.py with different command lines
import random

import cocotb
from cocotb.triggers import Timer

import vcst
from vcst.utils import set_top_level


@vcst.test(attributes=[".tagged"])
async def tagged(dut):
    await Timer(1, "ns")


@cocotb.test()
async def untagged(dut):
    await Timer(1, "ns")


# Logs the random seed and the first random value, which check.py compares between runs
@cocotb.test()
async def random_values(dut):
    await Timer(1, "ns")
    dut._log.info("VCST_RANDOM_SEED=%s VCST_RANDOM_VALUE=%s", cocotb.RANDOM_SEED, random.random())


set_top_level("front_end_dut", "entity", "lib")

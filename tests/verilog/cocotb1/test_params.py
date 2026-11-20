#Tests of a Verilog top level, checking that the parameters of its configurations reach the simulation
import random
import cocotb
from cocotb.triggers import Timer

from vcst.utils import set_top_level

#The NAME parameter of each configuration in run.py, identified by its WIDTH, as the name_id the DUT outputs for it
NAME_IDS = {8: 1, 16: 2, 4: 3}

@cocotb.test()
async def parameters(dut):
    width = len(dut.a)
    assert width in NAME_IDS, f"WIDTH {width} isn't one of the configurations"
    await Timer(1, units="ns")
    assert int(dut.name_id.value) == NAME_IDS[width], f"NAME doesn't match WIDTH {width}: name_id {int(dut.name_id.value)}"

@cocotb.test()
async def adding(dut):
    width = len(dut.a)
    for _ in range(10):
        a = random.randint(0, 2**width - 1)
        b = random.randint(0, 2**width - 1)
        dut.a.value = a
        dut.b.value = b
        await Timer(1, units="ns")
        assert int(dut.sum.value) == a + b, f"{a} + {b} gave {int(dut.sum.value)}"

set_top_level("params_dut", "module", "lib")

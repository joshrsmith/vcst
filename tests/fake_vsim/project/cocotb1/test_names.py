#Tests selected by name in the module with cocotb 1.x, including generated tests and a test with a second name
import cocotb
from cocotb.regression import TestFactory
from vcst.utils import set_top_level

@cocotb.test()
async def plain(dut):
    pass

second_name = plain

async def generated(dut, value):
    pass

factory = TestFactory(generated)
factory.add_option("value", [1, 2])
factory.generate_tests()

set_top_level("names_dut", "entity", "lib")

#A test of a Verilog top level, which is loaded with VPI rather than VHPI on Riviera-PRO
import cocotb
from vcst.utils import set_top_level

@cocotb.test()
async def verilog_test(dut):
    pass

set_top_level("verilog_dut", "module", "lib")

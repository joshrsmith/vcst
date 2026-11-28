# The test that check.py runs in the GUI of a simulator. It logs a line each time it runs, which check.py counts, and
# reads a signal inside the design.
import cocotb
from cocotb.triggers import Timer

from vcst.utils import set_top_level


@cocotb.test()
async def gui_test(dut):
    dut._log.info("VCST_GUI_TEST_RAN")
    dut.d.value = 1
    await Timer(1, "ns")
    # A signal inside the design, which drives no port
    assert int(dut.not_d.value) == 0, f"not_d is {dut.not_d.value} with d at 1"


set_top_level("gui_dut", "entity", "lib")

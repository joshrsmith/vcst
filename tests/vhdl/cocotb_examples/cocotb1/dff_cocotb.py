# ==============================================================================
# Authors:		Martin Zabel
#
# Cocotb Testbench:	For D flip-flop
#
# Description:
# ------------------------------------
# Automated testbench for simple D flip-flop.
#
# License:
# ==============================================================================
# Copyright 2016 Technische Universitaet Dresden - Germany
# Chair for VLSI-Design, Diagnostics and Architecture
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
import random

import cocotb
from cocotb.clock import Clock
from cocotb.regression import TestFactory
from cocotb.triggers import RisingEdge

from vcst.utils import set_top_level

#      dut
#    ________
#    |      |
#  --| d  q |--
#    |      |
#  --|>c    |
#    |______|


class BitMonitor:
    """Observe a single-bit input or output of the DUT at each rising clock edge."""

    def __init__(self, signal, clk, callback):
        self.signal = signal
        self.clk = clk
        self.callback = callback
        self._task = cocotb.start_soon(self._monitor())

    async def _monitor(self):
        clkedge = RisingEdge(self.clk)

        while True:
            # Capture signal at rising edge of clock
            await clkedge
            self.callback(int(self.signal.value))

    def stop(self):
        self._task.kill()


async def drive_bits(signal, clk):
    """Drive random data, holding each value for a random number of cycles."""
    clkedge = RisingEdge(clk)
    while True:
        signal.value = random.randint(0, 1)
        for _ in range(random.randint(1, 5)):
            await clkedge


class DFF_TB:
    def __init__(self, dut, init_val):
        """
        Setup the testbench.

        *init_val* signifies the value which must be captured by the
        output monitor with the first rising clock edge.
        This must match the initial state of the D flip-flop in RTL.
        """
        self.dut = dut
        self.stopped = False

        # What goes in at d comes out on q one clock cycle later, starting with init_val
        self.expected_output = [init_val]
        self.received_output = []

        self.input_mon = BitMonitor(signal=dut.d, clk=dut.c, callback=self.model)
        self.output_mon = BitMonitor(signal=dut.q, clk=dut.c, callback=self.received_output.append)
        self.input_drv = None

    def model(self, transaction):
        """Model the DUT based on the input *transaction*, except for the last clock cycle."""
        if not self.stopped:
            self.expected_output.append(transaction)

    def start(self):
        """Start generating input data."""
        self.input_drv = cocotb.start_soon(drive_bits(self.dut.d, self.dut.c))

    def stop(self):
        """Stop generating input data, and expected output, after the current clock cycle."""
        self.input_drv.kill()
        self.stopped = True

    def check(self):
        self.input_mon.stop()
        self.output_mon.stop()
        assert self.received_output == self.expected_output[: len(self.received_output)]
        assert len(self.received_output) == len(self.expected_output)


async def run_test(dut, cycles):
    """Setup testbench and run a test."""

    cocotb.start_soon(Clock(dut.c, 10, units="us").start(start_high=False))

    tb = DFF_TB(dut, init_val=0)

    clkedge = RisingEdge(dut.c)

    # Apply random input data for the given number of clock cycles.
    tb.start()
    for _ in range(cycles):
        await clkedge

    # Stop generation of input data. One more clock cycle is needed to capture
    # the resulting output of the DUT.
    tb.stop()
    await clkedge

    tb.check()


# Register the tests: run_test_001 and run_test_002
factory = TestFactory(run_test)
factory.add_option("cycles", [10, 100])
factory.generate_tests()

set_top_level("dff", "entity", "lib")

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

import vcst
from vcst.utils import set_top_level


@vcst.test(attributes=[".reset"])
async def reset_test(dut):
    Clock(dut.clock, 4, unit="ns").start()

    await RisingEdge(dut.clock)
    dut.reset.value = 1
    dut.enable.value = 0
    await RisingEdge(dut.clock)
    dut.reset.value = 0
    await RisingEdge(dut.clock)

    assert dut.counter_value.value == 0, "Counter value did not reset to 0."


@cocotb.test()
async def count_test(dut):
    Clock(dut.clock, 4, unit="ns").start()

    await RisingEdge(dut.clock)
    dut.reset.value = 1
    dut.enable.value = 0
    await RisingEdge(dut.clock)
    dut.reset.value = 0
    dut.enable.value = 1
    await RisingEdge(dut.clock)

    counter_wrap = int(dut.COUNTER_WRAP.value)
    for i in range(counter_wrap):
        assert dut.counter_value.value == i, (
            f"Counter value was incorrect. Expected: {i}. Actual: {dut.counter_value.value}"
        )
        await RisingEdge(dut.clock)


@cocotb.test()
async def wrap_test(dut):
    Clock(dut.clock, 4, unit="ns").start()

    await RisingEdge(dut.clock)
    dut.reset.value = 1
    dut.enable.value = 0
    await RisingEdge(dut.clock)
    dut.reset.value = 0
    dut.enable.value = 1
    await RisingEdge(dut.clock)

    counter_wrap = int(dut.COUNTER_WRAP.value)
    for _ in range(counter_wrap):
        await RisingEdge(dut.clock)

    assert dut.counter_value.value == counter_wrap, (
        f"Counter value did not reach wrapping point. Expected: {counter_wrap}. Actual: {dut.counter_value.value}"
    )

    await RisingEdge(dut.clock)
    assert dut.counter_value.value == 0, "Counter value did not wrap to 0."


@cocotb.test()
async def internal_signal_test(dut):
    """Reads a signal inside the counter, which drives no port"""
    Clock(dut.clock, 4, unit="ns").start()

    await RisingEdge(dut.clock)
    dut.reset.value = 1
    dut.enable.value = 0
    await RisingEdge(dut.clock)
    dut.reset.value = 0
    dut.enable.value = 1

    counter_wrap = int(dut.COUNTER_WRAP.value)
    for _ in range(counter_wrap + 3):
        await RisingEdge(dut.clock)

    assert dut.wraps.value == 1, f"The counter wrapped {int(dut.wraps.value)} times, not once"


########################
set_top_level("counter", "entity", "lib")

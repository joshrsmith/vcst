import cocotb
from vcst.utils import parameterize_test, set_top_level
from cocotb.triggers import RisingEdge
from cocotb.clock import Clock

async def sum_values(dut, values):
    Clock(dut.clock, 4, unit="ns").start()

    await RisingEdge(dut.clock)
    for a,b in values:
        dut.input_a.value = a
        dut.input_b.value = b
        await RisingEdge(dut.clock)
        await RisingEdge(dut.clock)
        expected_result = a+b
        assert dut.sum.value.to_signed() == expected_result, f"Incorrect sum. Expected {expected_result}. Actual: {dut.sum.value.to_signed()}"


#Show the alternate to test factory.
parameterize_test(sum_values, "positive_values", [(0, 1), (12, 13), (100, 200)])
parameterize_test(sum_values, "negative_values", [(-1, 10), (-111, -222), (-1111, -2222)])
parameterize_test(sum_values, "positive_and_negative_value", [(123, -456), (789, -12), (345, -678)])

########################
set_top_level("ADDER", "entity", "lib")

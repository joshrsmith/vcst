# Tests whose names contain characters with a special meaning in regular expressions and tcl, which VCST passes to
# cocotb 2.x in a regular expression, through tcl when the simulator process is reused. VUnit itself doesn't support
# "$", "[" and "]" in test names with these simulators, as it names the output directory of a test after it and doesn't
# quote that path for tcl.
import cocotb

from vcst.utils import set_top_level

NAMES = [
    "plain",
    "parens(1)",
    "plus+star*",
    "question?",
    "braces{1}",
    "caret^pipe|",
    "space name",
    "back\\slash",
    "dot.dot",
]


def make_test(name):
    async def test(dut):
        pass

    test.__qualname__ = test.__name__ = "test_" + str(NAMES.index(name))
    return cocotb.test(name=name)(test)


for _name in NAMES:
    globals()[f"test_{NAMES.index(_name)}"] = make_test(_name)

set_top_level("names_dut", "entity", "lib")

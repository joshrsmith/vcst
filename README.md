# vcst
VUnit and Cocotb Smashed Together

VUnit provides a testing framework for designing and running testbenches in VHDL or System Verilog. It is robust, supports many simulators and has many features. It emphasizes continuous integration and thus has an interface that allows for ease in discovering and running tests. It abstracts many of the details of interfacing to simulators including source compilation. It is extremely popular in the hardware FOSS community and for good reason. Cocotb on the other hand provides a mechanism for writing testbenches where the actual testbench is written in python. Python is increasingly becoming a popular language for verification compared to alternatives such as SystemVerilog. Unfortunately, the primary interface to cocotb is hand crafted makefiles. This includes manually specifying source files in compile order. There is no built in support for various generic permutations. Users must script this themselves. My perception is that the front end interface to cocotb is it's biggest weakness. Others have done work to improve the situation. See [cocotb-test](https://github.com/themperek/cocotb-test) for such work. 

For many users (such as myself), VUnit provides an ideal front end interface while cocotb provides an ideal framework for creating testbenches. In some ideal sense, VUnit and Cocotb are complementary. However VUnit and Cocotb have some overlap. For example both have test discovery, test execution and reporting mechanisms. However the core functionality of each is fairly distinct and *could* complement one another. Unfortunately they each are designed with somewhat contradictory philosophies. For example VUnit and Cocotb both prefer to be in charge of test execution and reporting. VUnit requires a HDL testbench that makes specific function calls. Many Cocotb users enjoy not writing any HDL at all for their testbenches.

VCST seeks to combine the best of both worlds. This includes inheriting VUnit's command line interface, automatic compilation order, incremental compilation and robust test execution. VCST seeks to inherit cocotb's python interface to simulators. In addition, testbenches already designed for VUnit should also continue to work in VCST. This supports many different verification strategies all of which have a place. In large teams and large projects, it is generally not a unwise to say a specific approach is optimal. Note that Cocotb testbenches may need a small amount of extra boiler plate to be used in VCST. 

## Goals
The goal of VCST is to provide a proof of example concept of VUnit and Cocotb working together without a single source change to other project. This will provide a couple of benefits. First, it is an interim solutions for VUnit and Cocotb users. Second, it will shed some light on what works could be done to make cooctb and vunit even more modular. Third, it has given me an opportunity to dig more into how these tools work so I can contribute more to these amazing tools.

## Simulator Support
At the moment, the supported simulators are GHDL, Riviera-Pro and ModelSim/Questa. The tests in this repository are run with GHDL; Riviera-Pro and ModelSim/Questa have not been tested with the current versions of VUnit and cocotb. GHDL has very limited support for VPI and therefore Cocotb can't fully utilize it. I invite anyone who wants to help me broaden simulator support to contribute. I also intend to add support for Icarus as well. This is bigger effort as VUnit does not support Icarus (as it does not support enough of System Verilog). VUnit's SystemVerilog testbenches would not work, but cocotb testbenches could work. 

## Supported Versions
VCST works with cocotb 1.8 and 1.9 as well as cocotb 2.0 and later, and with VUnit 4.7.1 or later, including the upcoming VUnit 5. Any of these cocotb versions can be combined with any of these VUnit versions. The run script and the VCST interface are the same for all of them, so a project can move to cocotb 2 without changing how its tests are added and run. The cocotb test modules themselves need to be written for the cocotb version installed. With VUnit 5, which needs Python 3.11 or later, cocotb 1.8 can be used with Python 3.11 and 3.12. Use VCST 0.0.11 or earlier with cocotb before 1.8 or VUnit before 4.7.

The tests in this repository have a cocotb 1.x version (the `cocotb1` directories) and a cocotb 2.x version (the `cocotb2` directories) of each cocotb test module. The run scripts pick the one matching the installed cocotb, see `vcst.utils.compat.COCOTB2`.

## Disadvantages
There are a few disadvantages compared to use either VUnit or Cocotb by themselves. These include:
1. Simulator Support - VUnit supports fewer simulators than cocotb. In addition I do not have access to most simulators and thus cannot ensure that other simulators work.
2. VUnit and Cocotb are moving targets. Future versions will likely break VCST. I do intend to support VCST for some time.
3. There isn't an official flow for the Driver Co-simulation. However I suspect the VUnit pre-simulation hooks could be used to build the necessary software prior to test execution.

## Installation Instructions
0. Be sure that Python-devel support is installed in your linux package manager eg: dnf install python3.11-devel on RHEL
1. Create a virtual environment
    ```bash
    python3 -m venv path_to_virtual_environment
    ```    
2. Activate virtual environment 
    ```bash
    source path_to_virtual_environment/bin/activate
    ```
3. ```bash
    pip install wheel
    ```
4. Clone repository
5. Change working directory to root of repository 
6. ```bash
    pip install .
    ```

## Creating Testbenches
When creating HDL testbenches, the normal flow is the same. However instead of import a VUnit object from vunit to create a user interface, import a VCST object to create a user interface. Then proceed as normal to add source files, configurations to testbenches etc. 
```python
from vcst import VCST
ui = VCST.from_argv()
```

Like VUnit before version 5, VCST adds VUnit's VHDL builtins by default. Pass `compile_builtins=False` to `from_argv` or `from_args` to leave them out, for example in order to call `ui.add_vhdl_builtins()` with arguments of your own.

Now to import a cocotb test module there are two steps. The cocotb module itself must call the set_top_level function defined in VCST. The set_top_level function takes in three arguments:
1. top_level_name - Top level entity or module that this cocotb tests.
2. top_level_type - "entity" if VHDL, "module" if verilog.
3. top_level_library - Name of the library the top level was compiled into.

```python
import cocotb
from vcst.utils import set_top_level
from cocotb.triggers import RisingEdge
from cocotb.clock import Clock

@cocotb.test()
async def reset_test(dut):
    Clock(dut.clock, 4, unit="ns").start()

    await RisingEdge(dut.clock)
    dut.reset.value = 1
    dut.enable.value = 0
    await RisingEdge(dut.clock)
    dut.reset.value = 0
    await RisingEdge(dut.clock)

    assert dut.counter_value.value == 0, "Counter value did not reset to 0."

set_top_level("counter", "entity", "lib") #This is different than a normal cocotb testbench

```

Every test cocotb would run from the module becomes a VUnit test, including those generated by `@cocotb.parametrize`. Tests decorated with `@vcst.test(attributes=[".my_attribute"])` instead of `@cocotb.test()` get VUnit attributes, which can be used to select tests with the `--with-attributes` and `--without-attributes` options. With VUnit 5, the seed VUnit gives a test (see `--seed`) is also used as the cocotb random seed.

Once that is defined, the cocotb module can be added via the ui object.
```python
adder_tb = ui.add_cocotb_testbench(root / "hdl/test_adder")
adder_tb.add_config(name="data_width_8", generics={"DATA_WIDTH": 8})
adder_tb.add_config(name="data_width_16", generics={"DATA_WIDTH": 16})
```
Notice how the adder_tb can have configurations with different generics added to it, much like a normal testbench.

Now you're all set. Run your run.py script like you would any vuint run script.


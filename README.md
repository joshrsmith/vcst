# vcst
VUnit and Cocotb Smashed Together

VUnit provides a testing framework for designing and running testbenches in VHDL or System Verilog. It is robust, supports many simulators and has many features. It emphasizes continuous integration and thus has an interface that allows for ease in discovering and running tests. It abstracts many of the details of interfacing to simulators including source compilation. It is extremely popular in the hardware FOSS community and for good reason. Cocotb on the other hand provides a mechanism for writing testbenches where the actual testbench is written in python. Python is increasingly becoming a popular language for verification compared to alternatives such as SystemVerilog. Unfortunately, the primary interface to cocotb is hand crafted makefiles. This includes manually specifying source files in compile order. There is no built in support for various generic permutations. Users must script this themselves. My perception is that the front end interface to cocotb is it's biggest weakness. Others have done work to improve the situation. See [cocotb-test](https://github.com/themperek/cocotb-test) for such work. 

For many users (such as myself), VUnit provides an ideal front end interface while cocotb provides an ideal framework for creating testbenches. In some ideal sense, VUnit and Cocotb are complementary. However VUnit and Cocotb have some overlap. For example both have test discovery, test execution and reporting mechanisms. However the core functionality of each is fairly distinct and *could* complement one another. Unfortunately they each are designed with somewhat contradictory philosophies. For example VUnit and Cocotb both prefer to be in charge of test execution and reporting. VUnit requires a HDL testbench that makes specific function calls. Many Cocotb users enjoy not writing any HDL at all for their testbenches.

VCST seeks to combine the best of both worlds. This includes inheriting VUnit's command line interface, automatic compilation order, incremental compilation and robust test execution. VCST seeks to inherit cocotb's python interface to simulators. In addition, testbenches already designed for VUnit should also continue to work in VCST. This supports many different verification strategies all of which have a place. In large teams and large projects, it is generally not a unwise to say a specific approach is optimal. Note that Cocotb testbenches may need a small amount of extra boiler plate to be used in VCST. 

## Goals
The goal of VCST is to provide a proof of example concept of VUnit and Cocotb working together without a single source change to other project. This will provide a couple of benefits. First, it is an interim solutions for VUnit and Cocotb users. Second, it will shed some light on what works could be done to make cooctb and vunit even more modular. Third, it has given me an opportunity to dig more into how these tools work so I can contribute more to these amazing tools.

## Compatibility
VCST supports VUnit 4.7.1 and VUnit 5 (pre-release), and cocotb 1.8, 1.9, 2.0 and 2.1. Any of these VUnit versions can be combined with any of these cocotb versions. The run script and the VCST interface are the same for all of them, but the cocotb test modules must be written for the installed cocotb version.

| Simulator       | Status                | Notes                                                                  |
|-----------------|-----------------------|------------------------------------------------------------------------|
| GHDL            | Tested in CI          | GHDL's VPI support is limited, so cocotb can't use everything with it  |
| NVC             | Tested in CI          | Needs cocotb 1.9 or later                                              |
| Riviera-PRO     | Tested by hand        | Full `tests/run_matrix.py` run with Riviera-PRO 2026.04, all passed    |
| ModelSim/Questa | Tested by hand        | Full `tests/run_matrix.py` run with Questa Altera Starter FPGA Edition 2025.2 on Linux, all passed |

**ModelSim/Questa** was tested with that edition and version on Linux only; reports about others, and about Windows, are welcome. Known issues:
* With cocotb 2, Questa crashes if it quits before a test ran ([cocotb#5777](https://github.com/cocotb/cocotb/issues/5777)), so VCST doesn't load cocotb for `--elaborate`, with any version of cocotb: `--elaborate` doesn't check that cocotb loads.
* If the simulation kernel of a simulator that VUnit reuses for several tests (its default) dies, for example because of a crash in a library loaded into it, Questa doesn't answer VUnit any more and the run hangs instead of reporting a failure. If a run stops making progress, run it with `--unique-sim`, which starts a simulator for every test, and look at the output of the test that was running.

The GUI (`--gui`) of ModelSim/Questa and Riviera-PRO is tested by hand too. After `vunit_restart` in the GUI, Riviera-PRO runs the cocotb test again; ModelSim/Questa doesn't with cocotb 2, and with cocotb 1.x it doesn't either or the GUI hangs ([cocotb#284](https://github.com/cocotb/cocotb/issues/284)), so close the GUI and run the test again instead.

I invite anyone who wants to help me broaden simulator support to contribute. I also intend to add support for Icarus as well. This is bigger effort as VUnit does not support Icarus (as it does not support enough of System Verilog). VUnit's SystemVerilog testbenches would not work, but cocotb testbenches could work.

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
3. Clone repository
4. Change working directory to root of repository 
5. ```bash
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

For example:

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


set_top_level("counter", "entity", "lib")  # This is different than a normal cocotb testbench
```

Once that is defined, the cocotb module can be added via the ui object.
```python
adder_tb = ui.add_cocotb_testbench(root / "hdl/test_adder")
adder_tb.add_config(name="data_width_8", generics={"DATA_WIDTH": 8})
adder_tb.add_config(name="data_width_16", generics={"DATA_WIDTH": 16})
```
Notice how the adder_tb can have configurations with different generics added to it, much like a normal testbench.

Now you're all set. Run your run.py script like you would any vuint run script.

### Running only the tests that changed
With VUnit 5, `--changed` runs only the tests that depend on changes since they last ran. VUnit only sees HDL files, so VCST adds the Python files of a cocotb test to what it depends on: the file of its cocotb module, and the Python files of your project that your run script has loaded, which are the files your cocotb modules import. That includes packages installed in editable mode (`pip install -e`), as their files are in your source tree. A modified file reruns the tests of all cocotb modules, except that a cocotb module only reruns its own tests. Files in the standard library and in site-packages don't count, so after updating an installed package, run the tests without `--changed`.

VCST can't see a Python file that is only imported while a test runs, or by a package that isn't loaded when the run script runs. To have it considered, import it in the run script. Data files that tests read aren't known either. As in VUnit, a test that failed isn't run again by `--changed` unless something it depends on changed.

This relies on private parts of VUnit 5, which is still changing. If they aren't as VCST expects, it prints a warning and `--changed` selects all tests. If VUnit no longer has the method VCST extends, the warning says that `--changed` only considers HDL files, as VUnit does by itself.

### Coverage of the Python tests
`COCOTB_USER_COVERAGE=1` (`COVERAGE=1` with cocotb 1.x) makes cocotb measure the Python code of the tests with coverage.py. By default every simulator writes its data to `.coverage` in its working directory, which is the same for all of them, so simulators running at once (`-p`) overwrite each other's data and the report misses lines. Have each simulator write a file of its own and combine them afterwards. Give the paths as absolute ones, as ModelSim/Questa and Riviera-PRO run in VUnit's output directory, and erase the data of the previous run first, which cocotb 2.1 would otherwise add to:

```
# coverage.rc
[run]
parallel = True
data_file = /path/to/results/.coverage
```
```
export COVERAGE_RCFILE="$PWD/coverage.rc"
coverage erase
COCOTB_USER_COVERAGE=1 python run.py -p 4
coverage combine
coverage report
```

### The Python debugger
`COCOTB_PDB_ON_EXCEPTION` can't be used under VUnit: VUnit gives the simulator no input, so the debugger waits forever in the first test that raises an exception and the run hangs. VCST prints a warning when it is set to a value with which cocotb opens the debugger (with cocotb 2.0 and earlier, any value, even `0`). To debug a test with it, run the test with cocotb's own Makefiles or runner instead of VUnit.

## Under the Hood

Every test cocotb would run from the module becomes a VUnit test, including those generated by `@cocotb.parametrize` and those imported from other modules. VUnit needs every test of a module to have a name of its own, so VCST refuses tests with the same name (which cocotb 2.x allows). A top level can have one cocotb module, and VCST refuses a second, different one.

Other behaviors:

* `run_all_in_same_sim`, as an attribute of a cocotb test bench or of one of its configurations, is ignored with a warning: VCST runs each cocotb test in a simulator of its own, to select it by name.
* A test skipped while it runs (e.g. `pytest.skip()` with cocotb 2.1) passes, as a VUnit test that runs either passes or fails.
* Tests decorated with `@vcst.test(attributes=[".my_attribute"])` instead of `@cocotb.test()` get VUnit attributes, which can be used to select tests with the `--with-attributes` and `--without-attributes` options.
* With VUnit 5, the seed VUnit gives a test is also the cocotb random seed, so `--seed` and `--seed repeat` work for cocotb tests as for VUnit tests. A seed set with `COCOTB_RANDOM_SEED` (`RANDOM_SEED` with cocotb 1.x) takes precedence.
* With Riviera-PRO, a generic with a value of a list or tuple becomes an aggregate, e.g. `["FOO", "BAR"]` in python becomes `(FOO,BAR)` when passed to the simulator. Generics of a VHDL top level are otherwise passed to the simulator as written, as done with VUnit, so they are written as VHDL: `"FOO"` for an enumeration literal, `'x"00FF"'`, `"(FOO,BAR)"`, and quotes are only added to values containing spaces.
* The design is loaded with access to the signals inside it, so that cocotb can read them, and they can be seen in the GUI: with read and write access to all of it on ModelSim/Questa (`-voptargs=-access=rw+/.`), as cocotb's runner does, and with `+access +w -O2` on Riviera-PRO. This limits how much the simulator optimizes the design, which can make large designs simulate slower.
* With Riviera-PRO, strings given to a Verilog top level are quoted, as it needs for string parameters.
* With cocotb 2, a test that ends before any simulation time passed makes cocotb quit ModelSim/Questa. VCST reports the outcome cocotb gives, and VUnit starts a new simulator for the next test.

## Testing

Where a cocotb test module needs different code for cocotb 1.x and 2.x, the tests in this repository have a cocotb 1.x version (in a `cocotb1` directory) and a cocotb 2.x version (in a `cocotb2` directory) of it, and the run scripts pick the one matching the installed cocotb, see `vcst.utils.compat.COCOTB2`. What each suite covers, and how to run them all with every supported combination of VUnit and cocotb, is described in [tests/README.md](tests/README.md).

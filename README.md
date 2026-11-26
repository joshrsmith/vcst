# vcst
VUnit and Cocotb Smashed Together

VUnit provides a testing framework for designing and running testbenches in VHDL or System Verilog. It is robust, supports many simulators and has many features. It emphasizes continuous integration and thus has an interface that allows for ease in discovering and running tests. It abstracts many of the details of interfacing to simulators including source compilation. It is extremely popular in the hardware FOSS community and for good reason. Cocotb on the other hand provides a mechanism for writing testbenches where the actual testbench is written in python. Python is increasingly becoming a popular language for verification compared to alternatives such as SystemVerilog. Unfortunately, the primary interface to cocotb is hand crafted makefiles. This includes manually specifying source files in compile order. There is no built in support for various generic permutations. Users must script this themselves. My perception is that the front end interface to cocotb is it's biggest weakness. Others have done work to improve the situation. See [cocotb-test](https://github.com/themperek/cocotb-test) for such work. 

For many users (such as myself), VUnit provides an ideal front end interface while cocotb provides an ideal framework for creating testbenches. In some ideal sense, VUnit and Cocotb are complementary. However VUnit and Cocotb have some overlap. For example both have test discovery, test execution and reporting mechanisms. However the core functionality of each is fairly distinct and *could* complement one another. Unfortunately they each are designed with somewhat contradictory philosophies. For example VUnit and Cocotb both prefer to be in charge of test execution and reporting. VUnit requires a HDL testbench that makes specific function calls. Many Cocotb users enjoy not writing any HDL at all for their testbenches.

VCST seeks to combine the best of both worlds. This includes inheriting VUnit's command line interface, automatic compilation order, incremental compilation and robust test execution. VCST seeks to inherit cocotb's python interface to simulators. In addition, testbenches already designed for VUnit should also continue to work in VCST. This supports many different verification strategies all of which have a place. In large teams and large projects, it is generally not a unwise to say a specific approach is optimal. Note that Cocotb testbenches may need a small amount of extra boiler plate to be used in VCST. 

## Goals
The goal of VCST is to provide a proof of example concept of VUnit and Cocotb working together without a single source change to other project. This will provide a couple of benefits. First, it is an interim solutions for VUnit and Cocotb users. Second, it will shed some light on what works could be done to make cooctb and vunit even more modular. Third, it has given me an opportunity to dig more into how these tools work so I can contribute more to these amazing tools.

## Compatibility
VCST supports VUnit 4.7.1 and VUnit 5 (pre-release, tested with 5.0.0.dev16), and cocotb 1.8, 1.9, 2.0 and 2.1. Any of these VUnit versions can be combined with any of these cocotb versions, and CI tests every combination. The run script and the VCST interface are the same for all of them, but the cocotb test modules must be written for the installed cocotb version. For cocotb before 1.8 or VUnit before 4.7, use VCST 0.0.11 or earlier.

| Simulator       | Status                | Notes                                                                  |
|-----------------|-----------------------|------------------------------------------------------------------------|
| GHDL            | Tested in CI          | GHDL's VPI support is limited, so cocotb can't use everything with it  |
| NVC             | Tested in CI          | Needs cocotb 1.9 or later                                              |
| Riviera-PRO     | Tested by hand        | Full `tests/run_matrix.py` run with Riviera-PRO 2026.04, all passed    |
| ModelSim/Questa | Supported, not tested | Not run with the current versions of VUnit and cocotb; reports welcome |

I invite anyone who wants to help me broaden simulator support to contribute. I also intend to add support for Icarus as well. This is bigger effort as VUnit does not support Icarus (as it does not support enough of System Verilog). VUnit's SystemVerilog testbenches would not work, but cocotb testbenches could work.

## Tests
Where a cocotb test module needs different code for cocotb 1.x and 2.x, the tests in this repository have a cocotb 1.x version (in a `cocotb1` directory) and a cocotb 2.x version (in a `cocotb2` directory) of it, and the run scripts pick the one matching the installed cocotb, see `vcst.utils.compat.COCOTB2`. A module which is the same for both is one file. Each script passes only if all of its tests have their expected outcomes:

- `tests/vhdl/cocotb_examples`, `vunit_and_cocotb` and `parameterize_test`: example test benches, including VUnit and cocotb tests of the same design.
- `tests/vhdl/test_outcomes`: tests with known outcomes, many of them failures, such as failing assertions, exceptions, tests failing to start, timeouts, `expect_fail` and `expect_error`, and tests that have names that are suffixes of other test names, are parametrized, are generated, are imported from another module or skip themselves while they run. The run script passes only if every test is reported with its expected outcome. Also covers `pre_config` and `post_check`.
- `tests/vhdl/isolation`: tests of two top levels in several configurations run in parallel, each checking that its simulation has the environment of its own test, and the one set by the user.
- `tests/unit`: unit tests of the logic of VCST, which need no simulator: what is sent to a persistent vsim (checked with tclsh, which the tests need), the environment of the simulation of each test in parallel runs, the selection of tests by name, the seeds, the formatting of generics for Riviera-PRO, what is given to cocotb to embed Python, the results of cocotb, importing cocotb modules by their paths, the errors of `add_cocotb_testbench` and its absolute path of a relative module location, and the refusal of a second cocotb module for a top level.
- `tests/fake_vsim/check.py` (needs tclsh): runs tests with Riviera-PRO and ModelSim/Questa replaced by fake simulators, which run the tcl VUnit sends to the simulator with tclsh and check what the cocotb simulation gets: the cocotb library and its loading, the Python environment, the top level, the selected test and the generics, and that VUnit's run script finds the test suite done. Both when VUnit reuses the simulator process for several tests and when it doesn't, and in GUI mode with `vsim_flags.gui` set. This doesn't show that the real simulators work with cocotb, but needs neither of them.
- `tests/vhdl/front_end/check.py`: runs run scripts with different command lines, checking `from_argv` and `from_args` with and without `compile_builtins`, rejection of unknown options, attribute selection, `--list`, `--export-json`, `--elaborate`, random seeds (`--seed`, `--seed repeat` and the `seed` simulation option), a `COCOTB_TESTCASE` set by the user, tests with the same name, cocotb modules with the same file name in different directories and a second cocotb module for a top level.

`tests/verilog` has cocotb tests of a Verilog top level with an integer and a string parameter, checking that the parameters of each configuration reach the simulation. It needs Riviera-PRO, so CI doesn't run it.

### Running all tests
`tests/run_matrix.py` runs every suite with every supported combination of VUnit and cocotb, on the simulator selected by `VUNIT_SIMULATOR`, and reports which runs passed. It installs each combination in a virtual environment of its own, together with the VCST of the checkout, so all it needs is Python 3.9 or later and access to PyPI, or the package index pip is configured with. Nothing is installed in the environment it is run with. For example, with Riviera-PRO:

```bash
export VUNIT_SIMULATOR=rivierapro
export VUNIT_RIVIERAPRO_PATH=/path/to/riviera-pro/bin
python3 tests/run_matrix.py --quick --output /path/to/results -p 4   # 4 combinations covering each version
python3 tests/run_matrix.py --output /path/to/results -p 4           # all combinations
```

Everything it creates is in the output directory (`matrix_out` by default) including virtual environments created during the run, console outputs and logs, and a report, `report.md`, which summarizes the results. At the end it prints one line saying whether all runs passed, and a combination which needs a newer Python than the one running the script (VUnit 5 needs Python 3.11 or later) is reported as not run. See `--help` for all options. The `unit` and `fake_vsim` suites don't use the simulator selected, but are run with every simulator. Without tclsh, `fake_vsim` is reported as skipped, which isn't a failure, and the tests of `unit` which need it are skipped. CI runs the same script, one combination per job, with GHDL and NVC.

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

Every test cocotb would run from the module becomes a VUnit test, including those generated by `@cocotb.parametrize` and those imported from other modules. VUnit needs every test of a module to have a name of its own, so VCST refuses tests with the same name, which cocotb 2.x allows. A top level can have one cocotb module, and VCST refuses a second. Modules with the same file name in different directories are different modules, for different top levels. A test skipped while it runs (`pytest.skip()` with cocotb 2.1) passes, as a VUnit test that runs either passes or fails. Tests decorated with `@vcst.test(attributes=[".my_attribute"])` instead of `@cocotb.test()` get VUnit attributes, which can be used to select tests with the `--with-attributes` and `--without-attributes` options.

With VUnit 5, the seed VUnit gives a test is also used as the cocotb random seed, so `--seed` and `--seed repeat` work for cocotb tests as for VUnit tests. The `seed` simulation option can be any string: a decimal number, such as a seed reported by cocotb, becomes the cocotb seed as it is. A seed set with `COCOTB_RANDOM_SEED` (`RANDOM_SEED` with cocotb 1.x) takes precedence.

Once that is defined, the cocotb module can be added via the ui object.
```python
adder_tb = ui.add_cocotb_testbench(root / "hdl/test_adder")
adder_tb.add_config(name="data_width_8", generics={"DATA_WIDTH": 8})
adder_tb.add_config(name="data_width_16", generics={"DATA_WIDTH": 16})
```
Notice how the adder_tb can have configurations with different generics added to it, much like a normal testbench.

With Riviera-PRO, a list or tuple given as the value of a generic becomes an aggregate, e.g. `["FOO", "BAR"]` becomes `(FOO,BAR)`. Generics of a VHDL top level are otherwise passed to the simulator as written, as with VUnit, so they are written as VHDL: `"FOO"` for an enumeration literal, `'x"00FF"'`, `"(FOO,BAR)"`, and quotes are only added to values containing spaces. Strings given to a Verilog top level are quoted, as Riviera-PRO needs for string parameters.

Now you're all set. Run your run.py script like you would any vuint run script.


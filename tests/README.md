# Tests of VCST

Every suite is a run script or a check script that exits with 1 unless all its tests have their expected outcomes. The
suites that run a simulator use the one selected by `VUNIT_SIMULATOR`, like VUnit. Where a cocotb test module needs
different code for cocotb 1.x and 2.x, the suite has a `cocotb1` and a `cocotb2` directory, and its run script picks the
one matching the installed cocotb, see the top-level [README](../README.md#testing).

Where to find what each suite covers:

| Suite | What it tests | Described in |
|---|---|---|
| `vhdl/cocotb_examples`, `vhdl/vunit_and_cocotb`, `vhdl/parameterize_test` | Example test benches, including VUnit and cocotb tests of the same design | the header of each `run.py` |
| `vhdl/test_outcomes` | That each test is reported with the outcome cocotb gives it, many of them failures, and that each is selected exactly | [its README](vhdl/test_outcomes/README.md) |
| `vhdl/isolation` | Tests of two top levels run in parallel, each with the environment of its own test | the header of its `run.py` |
| `vhdl/front_end/check.py` | The command line and run script interface, which differs between VUnit 4.7 and 5, and settings VCST ignores or warns about | its docstring |
| `unit` | The logic of VCST, without a simulator | the docstring of each test module, and of `run.py` |
| `fake_vsim/check.py` | The Riviera-PRO and ModelSim/Questa support, with fake simulators run by `tclsh` | its docstring |
| `verilog` | A Verilog top level; needs Riviera-PRO or ModelSim/Questa, so CI doesn't run it | the header of its `run.py` |

## Running all tests

`tests/run_matrix.py` runs every suite with every supported combination of VUnit and cocotb, on the simulator selected
by `VUNIT_SIMULATOR`, and reports which runs passed. It installs each combination in a virtual environment of its own,
together with the VCST of the checkout, so all it needs is Python 3.9 or later and access to PyPI, or the package index
pip is configured with. Nothing is installed in the environment it is run with. For example, with Riviera-PRO:

```bash
export VUNIT_SIMULATOR=rivierapro
export VUNIT_RIVIERAPRO_PATH=/path/to/riviera-pro/bin
python3 tests/run_matrix.py --quick --output /path/to/results -p 4   # 4 combinations covering each version
python3 tests/run_matrix.py --output /path/to/results -p 4           # all combinations
```

Everything it creates is in the output directory (`matrix_out` by default), including a report, `report.md`, which
summarizes the results; the header of `run_matrix.py` describes the rest. At the end it prints one line saying whether
all runs passed. A combination which needs a newer Python than the one running the script (VUnit 5 needs Python 3.11 or
later) is reported as not run. See `--help` for all options.

The `unit` and `fake_vsim` suites don't use the simulator selected, but are run with every simulator. Without `tclsh`,
`fake_vsim` is reported as skipped, which isn't a failure, and the tests of `unit` which need it are skipped. CI runs
the same script, one combination per job, with GHDL and NVC.

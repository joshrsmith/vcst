# test_outcomes

Tests with known outcomes, many of them failures. `run.py` passes only if every test is reported with the outcome it is
expected to have, so it checks that VCST reports what cocotb reports and that each test is selected exactly. The
expected outcomes are declared next to the tests (`EXPECTED_OUTCOMES`, filled by `expect`), as they depend on the
version of cocotb, and `../common/expected_outcomes.py` compares them with the report. Each test also checks that it
runs in a simulation of its own, so that selecting a test never runs another.

The tests are in `cocotb1/test_outcomes.py` or `cocotb2/test_outcomes.py`, whichever matches the installed cocotb. They
cover:

- failing assertions, exceptions, tests failing to start and timeouts
- `expect_fail` and `expect_error`, and with cocotb 2.1 `xfail` and a test that skips itself while it runs, which passes
  as VUnit counts a test it runs as failed unless it passed
- tests that end the simulation with an HDL assertion failure, with and without expecting it (`expect_error=SimFailure`),
  and a simulator that exits with a non-zero status after a test passed, which VCST reports as passed
- tests with names that are suffixes of other test names, which must not be selected with them
- parametrized tests (`cocotb.parametrize` with cocotb 2.x), whose names contain `/`, `=` and `.`, and tests generated
  with `TestFactory` (cocotb 1.x)
- tests imported from another module (`outcomes_imported.py`), which cocotb names after that module
- a test that finishes without simulation time passing (`zero_time`), after which cocotb 2 quits ModelSim/Questa: in a
  simulator reused by several tests (VUnit's default), VUnit then fails to read the outcome, and VCST reports the
  outcome cocotb gives, while VUnit starts a new simulator for the next test
- a test marked `skip=True`, which runs, as VCST selects every test by name

`test_hooks.py` runs a test in configurations that give `pre_config` and `post_check` hooks: one where both pass, and
two where one fails.

`simulator_fails_after_test` can't run in a simulator that VUnit reuses on ModelSim/Questa: its simulation kernel dies
when VUnit unloads the design (`quit -sim`) after the test, while the simulator stays and never answers, so the run
hangs. `tests/run_matrix.py` therefore runs the suite on ModelSim/Questa twice: in reused simulators without that test
(`--without-attributes .ends_simulator`), and with every test in a simulator of its own (`--unique-sim`). Riviera-PRO,
GHDL and NVC run the whole suite in reused simulators.

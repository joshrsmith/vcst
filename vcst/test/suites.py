import hashlib
import os
import re
from pathlib import Path
import xml.etree.ElementTree as ET

from vunit.test.report import PASSED, SKIPPED, FAILED
from vunit.test.suites import IndependentSimTestCase, TestRun

from ..monkey_patching.environment import extra_env
from ..utils.compat import gpi_environ, gpi_lib, seed_variable, test_selection_environ

class IndependentCocoSimTestCase(IndependentSimTestCase):
    def __init__(self, test, config, simulator_if, elaborate_only=False, seed=None):
        self._name = self.get_name(test, config)
        self._configuration = config
        self._test = test

        self._run = CocoTestRun(
            vhdl=test._vhdl,
            top_level=test._top_level,
            simulator_if=simulator_if,
            config=config,
            elaborate_only=elaborate_only,
            cocotb_module = test._cocotb_module,
            cocotb_module_location=test._cocotb_module_location,
            test_suite_name=self._name,
            test_cases=[test.name],
            result_names={test.result_name: test.name},
            test_modules={test.name: test.defining_module},
            seed=seed,
        )

    @staticmethod
    def get_name(test, config):
        """Returns the full name of the test run with the configuration"""
        name = "%s.%s" % (config.library_name, config.design_unit_name)

        if not config.is_default:
            name += "." + config.name

        if test.is_explicit:
            name += "." + test.name
        elif config.is_default:
            # JUnit XML test reports wants three dotted name hierarchies
            name += ".all"

        return name

class CocoTestRun(TestRun):
    def __init__(self, vhdl, top_level, simulator_if, config, elaborate_only, cocotb_module, cocotb_module_location, test_suite_name, test_cases, result_names=None, test_modules=None, seed=None):
        # TestRun.__init__ differs between VUnit versions, so set its attributes directly
        self._simulator_if = simulator_if
        self._config = config
        self._elaborate_only = elaborate_only
        self._test_suite_name = test_suite_name
        self._test_cases = test_cases
        self._seed = seed
        # Maps the names of the tests in the cocotb results file to their names in test_cases
        self._result_names = result_names if result_names is not None else {}
        # Maps the names of tests defined in other modules than the cocotb module to the names of these modules
        self._test_modules = test_modules if test_modules is not None else {}
        self._cocotb_module_location = cocotb_module_location
        self._top_level = top_level
        self._vhdl = vhdl

    def create_environ(self, output_path, seed=None):
        """
        Creates the environment variables cocotb needs, in addition to those of the VCST process, None for those to
        remove from it.
        """
        environ = gpi_environ(os.environ)
        mod_dir, mod_name = os.path.split(self._cocotb_module_location)

        if "PYTHONPATH" not in os.environ:
            environ["PYTHONPATH"] = mod_dir
        else:
            environ["PYTHONPATH"] = os.environ["PYTHONPATH"] + f"{os.pathsep}{mod_dir}"

        environ["COCOTB_RESULTS_FILE"] = get_result_file_name(output_path)
        environ["TOPLEVEL_LANG"] = "vhdl" if self._vhdl else "verilog"

        if self._simulator_if.name in ("ghdl", "nvc"):
            top_level = self._top_level.lower()
            # As done by cocotb's runners for these simulators. Ignored by cocotb 1.x.
            if "COCOTB_TRUST_INERTIAL_WRITES" not in os.environ:
                environ["COCOTB_TRUST_INERTIAL_WRITES"] = "1"
        else:
            top_level = self._top_level

        cocotb_seed = None if seed_variable() in os.environ else _get_cocotb_seed(seed)
        environ.update(test_selection_environ(mod_name, self._test_cases, top_level, cocotb_seed,
                                              self._test_modules))

        return environ

    def configure_simulator(self, config, environ):
        """
            Sets simulator flags to load the VPI/VHPI/FLI interfaces as appropriate. Also sets environment
            variables related to those interfaces.
            TODO: Support more simulators.
        """
        if self._simulator_if.name == "ghdl":
            append_sim_options(config, "ghdl.sim_flags", [f"--vpi={gpi_lib('vpi', 'ghdl')}"])

        if self._simulator_if.name == "nvc":
            append_sim_options(config, "nvc.sim_flags", [f"--load={gpi_lib('vhpi', 'nvc')}"])

        if self._simulator_if.name == "modelsim":
            append_sim_options(config, "modelsim.vsim_flags", [f"-foreign \"cocotb_init {gpi_lib('fli', 'questa')}\""])

        if self._simulator_if.name == "rivierapro":
            append_sim_options(config, "rivierapro.vsim_flags", ["+access", "+w", "-interceptcoutput", "-O2"])

            if self._vhdl:
                append_sim_options(config, "rivierapro.vsim_flags", [f"-loadvhpi {gpi_lib('vhpi', 'riviera')}"])
            else:
                append_sim_options(config, "rivierapro.vsim_flags", [f"-pli {gpi_lib('vpi', 'riviera')}"])

    def run(self, output_path, read_output, *args, **kwargs):
        """
        Run selected test cases within the test suite

        Returns a dictionary of test results
        """
        results = {}
        for name in self._test_cases:
            results[name] = FAILED

        # VUnit 5 gives each test a seed, passed to the pre_config hook and on to cocotb
        seed = self.get_seed() if hasattr(TestRun, "get_seed") else None
        pre_config_args = (output_path, self._simulator_if.output_path) + (() if seed is None else (seed,))
        if not self._config.call_pre_config(*pre_config_args):
            return results

        # Results from a previous run must not be mistaken for the results of this one
        result_file_name = get_result_file_name(output_path)
        if os.path.exists(result_file_name):
            os.remove(result_file_name)

        sim_ok = self._simulate(output_path, seed)

        if self._elaborate_only:
            status = PASSED if sim_ok else FAILED
            return dict((name, status) for name in self._test_cases)

        results = self._read_test_results(file_name=result_file_name)

        done, results = self._check_results(results, sim_ok)
        if done:
            return results

        if not self._config.call_post_check(output_path, read_output):
            for name in self._test_cases:
                results[name] = FAILED

        return results

    def _simulate(self, output_path, seed=None):
        """Runs the simulation with the environment variables and simulator flags cocotb needs."""
        if seed is not None:
            # As VUnit 5 does for its own tests
            print(f"Seed for {self._test_suite_name}: {seed}")
        config = self._config.copy()
        env = self.create_environ(output_path, seed)
        self.configure_simulator(config, env)
        with extra_env(env):
            return self._simulator_if.simulate(
                output_path=output_path,
                test_suite_name=self._test_suite_name,
                config=config,
                elaborate_only=self._elaborate_only,
            )

    def _read_test_results(self, file_name):
        results = {}
        for name in self._test_cases:
            results[name] = FAILED

        if not os.path.exists(file_name):
            return results

        tree = ET.parse(file_name)
        root = tree.getroot()

        results_tests = []
        for result in root.iter("testcase"):
            test_name = self._result_names.get(result.attrib["name"], result.attrib["name"])
            if test_name not in results:
                continue
            results_tests.append(test_name)
            # A test skipped while it runs (pytest.skip with cocotb 2.1) passes, as VUnit counts a test it runs
            # as failed unless it passed
            results[test_name] = PASSED
            for thing in result:
                if thing.tag in ("failure", "error"):
                    results[test_name] = FAILED

        for test_name in self._test_cases:
            if test_name not in results_tests:
                results[test_name] = SKIPPED

        return results

def append_sim_options(config, name, value):
    sim_flags  = config.sim_options.get(name, [])
    sim_flags  = sim_flags + value
    config.set_sim_option(name, sim_flags)

def get_result_file_name(output_path):
    return str(Path(output_path) / "cocotb_results.xml")

def _get_cocotb_seed(seed):
    """
    Returns the VUnit seed as a cocotb seed (integer), or None if there is no seed. VUnit generates seeds of 16
    hexadecimal digits, which become 32 bit integers, but the seed simulation option can be any string: a decimal
    number, such as a seed reported by cocotb, is used as it is, and any other string is hashed.
    """
    if seed is None:
        return None
    seed = str(seed)
    if re.fullmatch("[0-9a-fA-F]{16}", seed):
        return int(seed, 16) % 2**32
    if re.fullmatch("[0-9]+", seed):
        return int(seed)
    return int.from_bytes(hashlib.blake2b(seed.encode(), digest_size=4).digest(), "big")

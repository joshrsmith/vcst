import inspect
from collections import OrderedDict
from dataclasses import dataclass

from vunit.test.bench import TestBench, TestConfigurationVisitor, FileLocation
from vunit.test.list import TestList
from vunit.configuration import Configuration, DEFAULT_NAME

from .suites import IndependentCocoSimTestCase
from ..utils.compat import find_cocotb_tests

# VUnit 5 gives each test a seed and passes it to create_tests before elaborate_only
_VUNIT_HAS_SEEDS = "seed" in inspect.signature(TestBench.create_tests).parameters

def _split_create_tests_args(args):
    """Returns (seed, elaborate_only, test_list) from the arguments VUnit gives create_tests after simulator_if."""
    if _VUNIT_HAS_SEEDS:
        seed, elaborate_only, test_list = (list(args) + [None] * 3)[:3]
        if seed == "repeat":
            # VCST keeps no test history to repeat seeds from, so a new seed is generated
            seed = None
    else:
        seed = None
        elaborate_only, test_list = (list(args) + [None] * 2)[:2]
    return seed, elaborate_only, test_list

class CocoTestBench(TestBench):
    def __init__(self, design_unit, cocotb_module, cocotb_module_location, database=None):
        # ConfigurationVisitor.__init__ differs between VUnit versions, so set its attribute directly
        self.design_unit = design_unit
        self._database = database

        self._individual_tests = True
        self._configs = {}
        self._test_cases = []
        self._implicit_test = None
        self._cocotb_module = None

        if design_unit.is_entity:
            design_unit.set_add_architecture_callback(self._add_architecture_callback)
            if design_unit.architecture_names:
                self._add_architecture_callback()

        self.discover_cocotb_tests(cocotb_module, cocotb_module_location)
        self.set_attribute(".cocotb", None)

    def _add_architecture_callback(self):
        """
        Called when architectures have been added
        """
        self._check_architectures(self.design_unit)

    def discover_cocotb_tests(self, cocotb_module, cocotb_module_location):
        """
        Discover tests defined in a cocotb module and
        """
        self._cocotb_module = cocotb_module
        tests = []
        #Iterate every value in the module looking for cocotb tests
        for obj, test_names in find_cocotb_tests(cocotb_module):
            for test_name in test_names:
                coco_test = CocoTest(test_name.name, self.design_unit, cocotb_module, cocotb_module_location,
                                     result_name=test_name.result_name, defining_module=test_name.module)
                for attr in getattr(obj, "vcst_attributes", []):
                    coco_test.add_attribute(CocoTestAttribute(attr, None))
                tests.append(coco_test)

        default_config = Configuration(DEFAULT_NAME, self.design_unit)
        self._test_cases = [
            CocoTestConfigurationVisitor(test, self.design_unit, True, default_config.copy())
            for test in tests
        ]

        self._configs = OrderedDict({default_config.name: default_config})

    def create_tests(self, simulator_if, *args, **kwargs):
        """
        Create all test cases from this test bench
        """

        self._check_architectures(self.design_unit)

        seed, elaborate_only, test_list = _split_create_tests_args(args)
        if test_list is None:
            test_list = TestList()

        for test_case in self._test_cases:
            test_case.create_coco_tests(simulator_if, seed, elaborate_only, test_list)

        return test_list


class CocoTest(object):
    """
    TODO: Describe
    """

    def __init__(self, name, design_unit, cocotb_module, cocotb_module_location, result_name=None,
                 defining_module=None):
        self._name = name
        self._result_name = name if result_name is None else result_name
        self._defining_module = defining_module
        self._top_level = cocotb_module.top_level
        self._vhdl = design_unit.is_entity
        self._location = FileLocation(design_unit.file_name, None, None, None) #offset, length, lineno set to None
        self._cocotb_module = cocotb_module
        self._cocotb_module_location = cocotb_module_location
        self._attributes = []

    @property
    def name(self):
        return self._name

    @property
    def result_name(self):
        """The name of the test in the cocotb results file"""
        return self._result_name

    @property
    def defining_module(self):
        """The name of the module defining the test if it was imported from another module, else None"""
        return self._defining_module

    @property
    def location(self):
        return self._location

    @property
    def is_explicit(self):
        return True

    def add_attribute(self, attr):
        self._attributes.append(attr)

    @property
    def attributes(self):
        return list(self._attributes)

    @property
    def attribute_names(self):
        return set((attr.name for attr in self._attributes))

    def _to_tuple(self):
        return (self._name, self._location, tuple(self._attributes))

    def __repr__(self):
        return "Test" + repr(self._to_tuple())

    def __eq__(self, other):
        return self._to_tuple() == other._to_tuple()  # pylint: disable=protected-access

    def __hash__(self):
        return hash(self._to_tuple())


class CocoTestConfigurationVisitor(TestConfigurationVisitor):
    """
    Override VUnit's TestConfigurationVisitor to create CocoIndependentSimTestCase objects
    """
    def create_tests(self, simulator_if, *args, **kwargs):
        seed, elaborate_only, test_list = _split_create_tests_args(args)
        self.create_coco_tests(simulator_if, seed, elaborate_only, test_list)

    def create_coco_tests(self, simulator_if, seed, elaborate_only, test_list):
        for config in self._get_configurations_to_run():
            test_list.add_test(
                IndependentCocoSimTestCase(
                    test=self._test,
                    config=config,
                    simulator_if=simulator_if,
                    elaborate_only=elaborate_only,
                    seed=seed,
                )
            )


@dataclass(frozen=True)
class CocoTestAttribute:
    name: str
    value: str

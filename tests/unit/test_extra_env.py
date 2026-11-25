"""
VUnit runs the tests in several threads, so the environment of a cocotb test can't be put in os.environ. Every process a
thread starts while it simulates a test must have the environment of that test, and no other.
"""
import os
import sys
import threading
import unittest
from unittest import mock

from vunit.ostools import Process

from vcst.monkey_patching.environment import extra_env, get_extra_env

PRINT_VARIABLE = "import os; print(os.environ.get('VCST_UNIT_X', 'unset'))"


def output_of_process(env=None):
    lines = []
    process = Process([sys.executable, "-c", PRINT_VARIABLE], env=env)
    process.consume_output(lines.append)
    process.wait()
    return "".join(lines).strip()


class ExtraEnv(unittest.TestCase):
    def test_processes_have_the_environment_of_their_thread(self):
        threads = 8
        barrier = threading.Barrier(threads)
        results = {}

        def simulate(index):
            with extra_env({"VCST_UNIT_X": f"value{index}"}):
                # All threads are inside their context while any of them starts a process
                barrier.wait(timeout=30)
                results[index] = output_of_process()

        workers = [threading.Thread(target=simulate, args=(index,)) for index in range(threads)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(60)
        self.assertEqual(results, {index: f"value{index}" for index in range(threads)})

    def test_the_environment_ends_with_the_context(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("VCST_UNIT_X", None)
            with extra_env({"VCST_UNIT_X": "inside"}):
                self.assertEqual(get_extra_env(), {"VCST_UNIT_X": "inside"})
                self.assertEqual(output_of_process(), "inside")
            self.assertIsNone(get_extra_env())
            self.assertEqual(output_of_process(), "unset")

    def test_the_environment_ends_when_the_test_raises(self):
        with self.assertRaises(ValueError):
            with extra_env({"VCST_UNIT_X": "inside"}):
                raise ValueError
        self.assertIsNone(get_extra_env())

    def test_none_removes_a_variable_of_the_process(self):
        with mock.patch.dict(os.environ, {"VCST_UNIT_X": "from the environment"}):
            self.assertEqual(output_of_process(), "from the environment")
            with extra_env({"VCST_UNIT_X": None}):
                self.assertEqual(output_of_process(), "unset")

    def test_variables_of_the_environment_given_to_the_process_are_kept(self):
        env = {**os.environ, "VCST_UNIT_X": "given", "VCST_UNIT_Y": "kept"}
        code = "import os; print(os.environ.get('VCST_UNIT_X'), os.environ.get('VCST_UNIT_Y'))"
        lines = []
        with extra_env({"VCST_UNIT_X": "extra"}):
            process = Process([sys.executable, "-c", code], env=env)
            process.consume_output(lines.append)
            process.wait()
        self.assertEqual("".join(lines).strip(), "extra kept")


if __name__ == "__main__":
    unittest.main()

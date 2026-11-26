"""
The seed VUnit gives a test becomes the seed of cocotb, so that a run can be repeated with --seed, the seed simulation
option or a seed reported by cocotb.
"""

import os
import subprocess
import sys
import unittest

from vcst.test.suites import _get_cocotb_seed


class CocotbSeed(unittest.TestCase):
    def test_no_seed_lets_cocotb_choose(self):
        self.assertIsNone(_get_cocotb_seed(None))

    def test_seeds_of_vunit_are_the_same_32_bit_numbers_as_before(self):
        # VUnit's seeds have 16 hexadecimal digits. These values were given to cocotb by VCST before the seed
        # simulation option could be any string, and a repeated run depends on them.
        self.assertEqual(_get_cocotb_seed("0123456789abcdef"), 0x89ABCDEF)
        self.assertEqual(_get_cocotb_seed("FEDCBA9876543210"), 0x76543210)
        self.assertEqual(_get_cocotb_seed("0000000000000000"), 0)

    def test_decimal_numbers_are_used_as_they_are(self):
        # As of a seed reported by cocotb, to run with it again
        self.assertEqual(_get_cocotb_seed("12345"), 12345)
        self.assertEqual(_get_cocotb_seed(12345), 12345)
        self.assertEqual(_get_cocotb_seed("4294967295"), 4294967295)

    def test_any_other_string_gives_a_number_cocotb_accepts(self):
        seeds = {
            text: _get_cocotb_seed(text)
            for text in ("any seed", "other", "", "0x1F", "-1", "1.5", "g" * 16)
        }
        for value in seeds.values():
            self.assertIsInstance(value, int)
            self.assertTrue(0 <= value < 2**32)
        self.assertEqual(
            len(set(seeds.values())), len(seeds), "different strings should give different seeds"
        )

    def test_the_same_string_gives_the_same_seed_in_every_process(self):
        # Python's own hash of a string changes from process to process, which would make the run unrepeatable
        code = "from vcst.test.suites import _get_cocotb_seed as seed; print(seed('any seed'))"
        values = set()
        for hash_seed in ("1", "2", "random"):
            env = {**os.environ, "PYTHONHASHSEED": hash_seed}
            proc = subprocess.run(
                [sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=120
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            values.add(int(proc.stdout))
        values.add(_get_cocotb_seed("any seed"))
        self.assertEqual(len(values), 1)


if __name__ == "__main__":
    unittest.main()

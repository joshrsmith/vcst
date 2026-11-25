"""
Runs the unit tests of VCST, which test its logic without a simulator.

Usage: python run.py [-p N] [--output-path DIR]

-p and --output-path are accepted as by the other run scripts and aren't used. Exits with 1 if a test fails.
"""
import argparse
import sys
import unittest
from pathlib import Path

parser = argparse.ArgumentParser(description="Runs the unit tests of VCST")
parser.add_argument("-p", "--num-threads", type=int, default=1, help="not used")
parser.add_argument("--output-path", type=Path, help="not used")
parser.add_argument("-v", "--verbose", action="store_true", help="print every test")
options = parser.parse_args()

here = Path(__file__).resolve().parent
suite = unittest.defaultTestLoader.discover(str(here), pattern="test_*.py", top_level_dir=str(here))
result = unittest.TextTestRunner(verbosity=2 if options.verbose else 1).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)

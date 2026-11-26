"""
import_mod, which imports the cocotb module a user gives by its path.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

from vcst.utils.mod_utils import import_mod


class ImportMod(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name).resolve()
        for name in ("vcst_unit_mod", "vcst_unit_pkg"):
            self.addCleanup(self.forget, name)

    @staticmethod
    def forget(name):
        for loaded in list(sys.modules):
            if loaded == name or loaded.startswith(f"{name}."):
                del sys.modules[loaded]

    def write(self, directory, file_name, text):
        path = self.directory / directory / file_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_a_module_is_imported_by_its_path_without_its_extension(self):
        self.write("dir", "vcst_unit_mod.py", "VALUE = 1\n")
        self.assertEqual(import_mod(str(self.directory / "dir" / "vcst_unit_mod")).VALUE, 1)

    def test_modules_with_the_same_file_name_in_different_directories_are_different_modules(self):
        paths = []
        for index in (1, 2):
            self.write(f"dir{index}", "vcst_unit_mod.py", f"VALUE = {index}\n")
            paths.append(str(self.directory / f"dir{index}" / "vcst_unit_mod"))
        self.assertEqual([import_mod(path).VALUE for path in paths], [1, 2])
        # and back, as a module added later may be in either directory
        self.assertEqual(import_mod(paths[0]).VALUE, 1)

    def test_a_module_imported_twice_from_the_same_directory_is_imported_once(self):
        self.write("dir", "vcst_unit_mod.py", "import itertools\nCOUNT = itertools.count()\n")
        path = str(self.directory / "dir" / "vcst_unit_mod")
        self.assertIs(import_mod(path), import_mod(path))

    def test_a_module_in_a_package_is_imported_by_its_dotted_name(self):
        for index in (1, 2):
            self.write(f"dir{index}/vcst_unit_pkg", "__init__.py", "")
            self.write(f"dir{index}/vcst_unit_pkg", "inner.py", f"VALUE = {index}\n")
        values = [
            import_mod(str(self.directory / f"dir{index}" / "vcst_unit_pkg.inner")).VALUE
            for index in (1, 2)
        ]
        self.assertEqual(values, [1, 2])

    def test_the_working_directory_and_the_module_search_path_are_kept(self):
        self.write("dir", "vcst_unit_mod.py", "VALUE = 1\n")
        directory, search_path = os.getcwd(), list(sys.path)
        import_mod(str(self.directory / "dir" / "vcst_unit_mod"))
        self.assertEqual((os.getcwd(), sys.path), (directory, search_path))


if __name__ == "__main__":
    unittest.main()

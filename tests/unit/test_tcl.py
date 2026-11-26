"""
What VCST sends to a persistent vsim must be read by tcl as the value it was given, whatever the value contains. A value
which tcl reads differently, e.g. by removing backslashes, changes what cocotb finds in its environment.
"""

import random
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from vcst.monkey_patching.vsim import set_env_var, tcl_quote

TCLSH = shutil.which("tclsh")

# Characters special to tcl, in the context of a double quoted word and otherwise. Characters outside the Basic
# Multilingual Plane aren't used: tcl 8.6.8 reads them from a script as several characters, whatever the script is.
SPECIAL = [
    "",
    " ",
    "a b",
    '"',
    "\\",
    "\\\\",
    "\\n",
    "$HOME",
    "${a}",
    "$(x)",
    "[exit 1]",
    "[puts hi]",
    "{",
    "}",
    "{a b}",
    ";",
    "a;b",
    "\n",
    "\r\n",
    "line1\nline2",
    "tab\there",
    "unicode: é€",
    "#",
    "\\$",
    '"\\"',
    "\\x41",
    "\\u0041",
    "100%",
    "a\\",
    "\\\\\\",
    "^test\\.name$",
    "(a|b)\\1",
]


def run_tcl(script):
    """Runs a tcl script with tclsh, returns its output lines. The script is read as UTF-8."""
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "script.tcl"
        path.write_text(script, encoding="utf-8")
        proc = subprocess.run(
            [TCLSH],
            input=f"source -encoding utf-8 {path}\n",
            capture_output=True,
            text=True,
            timeout=60,
        )
    if proc.returncode != 0:
        raise AssertionError(f"tclsh failed: {proc.stderr}\n{script[:2000]}")
    return proc.stdout.splitlines()


def hex_of(variable):
    """Tcl printing the value of a variable as hexadecimal UTF-8, independent of the encoding of stdout"""
    return f"puts [binary encode hex [encoding convertto utf-8 {variable}]]"


class FakeProcess:
    def __init__(self):
        self.lines = []

    def writeline(self, line):
        self.lines.append(line)


class FakeShell:
    def __init__(self):
        self.process = FakeProcess()

    def _process(self):
        return self.process


@unittest.skipUnless(TCLSH, "tclsh is needed")
class TclQuote(unittest.TestCase):
    def test_tcl_reads_the_value_back(self):
        rng = random.Random(20261125)
        alphabet = list('\\"$[]{};# \n\r\tabAB09é')
        values = SPECIAL + [
            "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 40))) for _ in range(300)
        ]
        script = "".join(f"set x {tcl_quote(value)}\n{hex_of('$x')}\n" for value in values)
        read = [bytes.fromhex(line).decode("utf-8") for line in run_tcl(script)]
        self.assertEqual(len(read), len(values))
        for value, got in zip(values, read):
            self.assertEqual(got, value)


@unittest.skipUnless(TCLSH, "tclsh is needed")
class SetEnvVar(unittest.TestCase):
    def values_after(self, env, preset=()):
        shell = FakeShell()
        set_env_var(shell, env)
        script = "".join(f"set ::env({name}) preset\n" for name in preset)
        script += "".join(line + "\n" for line in shell.process.lines)
        for name in env:
            script += f"if {{[info exists ::env({name})]}} {{ {hex_of(f'$::env({name})')} }} else {{ puts UNSET }}\n"
        output = run_tcl(script)
        return {
            name: (None if line == "UNSET" else bytes.fromhex(line).decode("utf-8"))
            for name, line in zip(env, output)
        }

    def test_values_reach_tcl_unchanged_also_when_longer_than_a_write(self):
        # Values are written in pieces, which must not split what tcl reads as one character
        env = {
            "VCST_SHORT": 'a "quoted" \\ value with $dollar and [brackets]',
            "VCST_LONG": "".join(f"{chr(65 + i % 26)}\\{i}$" for i in range(2000)),
            "VCST_BACKSLASH_AT_BOUNDARY": "x" * 1023 + "\\" + "y" * 10,
            "VCST_ALL_BACKSLASHES": "\\" * 2049,
            "VCST_NEWLINE_AT_BOUNDARY": "x" * 1023 + "\n" + "y" * 10,
            "VCST_EMPTY": "",
        }
        self.assertEqual(self.values_after(env), env)

    def test_none_removes_the_variable(self):
        self.assertEqual(
            self.values_after({"VCST_REMOVED": None, "VCST_SET": "1"}, preset=["VCST_REMOVED"]),
            {"VCST_REMOVED": None, "VCST_SET": "1"},
        )

    def test_removing_a_variable_which_is_not_set_is_not_an_error(self):
        self.assertEqual(self.values_after({"VCST_NEVER_SET": None}), {"VCST_NEVER_SET": None})


if __name__ == "__main__":
    unittest.main()

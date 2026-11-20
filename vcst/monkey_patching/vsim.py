#Extends VUnit's vsim based simulators (Riviera-PRO, ModelSim/Questa) to pass environment variables to the persistent
#vsim process, which is started once and then reused by the tests of a thread.
import vunit
from vunit.sim_if.vsim_simulator_mixin import VsimSimulatorMixin
from vunit.persistent_tcl_shell import PersistentTclShell

from .environment import get_extra_env

#Characters which have a special meaning in a double quoted tcl word, and how to write them literally
_TCL_ESCAPES = {char: "\\" + char for char in '\\"$[]{}'}
_TCL_ESCAPES.update({"\n": "\\n", "\r": "\\r"})

def tcl_quote(value):
    """Returns value as a double quoted tcl word, which tcl reads back as value."""
    return '"' + "".join(_TCL_ESCAPES.get(char, char) for char in value) + '"'

def set_env_var(self, env):
    """Sets environment variables by setting them in tcl. This is accomplished by interacting with
       the simulator via stdin.
    """
    #For some reason, there are times were writes to stdin are truncated if they are to long. Back to back writes seem to work,
    #so chunk up those writes. The value is split before quoting so that no escape sequence is split.

    C_MAX_CHARS = 1024
    process = self._process()
    for var, var_value in env.items():
        #Initialize a temp variable to hold the intermediate value
        process.writeline('set vcst_env_var ""')

        #Append each chunk of the desired environment variable to the temp variable
        for i in range(0, len(var_value), C_MAX_CHARS):
            process.writeline(f"append vcst_env_var {tcl_quote(var_value[i:i + C_MAX_CHARS])}")

        #Then set the environment variable to the temp value
        process.writeline(f"set ::env({var}) $vcst_env_var")

class ReadVarOutputConsumer(object):
    """
    Consume output from modelsim and print with indentation
    """

    def __init__(self):
        self.var = None

    def __call__(self, line):
        if "#VUNIT_READVAR=" in line:
            self.var = line.split("#VUNIT_READVAR=")[-1].strip()
            return True

_run_persistent = VsimSimulatorMixin._run_persistent

def run_persistent(self, *args, **kwargs):
    """
    Run a test bench using the persistent vsim process, after setting the environment variables of the test
    """
    env = get_extra_env()
    if env:
        self._persistent_shell.set_env_var(env)
    return _run_persistent(self, *args, **kwargs)

###############################################################
PersistentTclShell.set_env_var = set_env_var
vunit.persistent_tcl_shell.ReadVarOutputConsumer = ReadVarOutputConsumer
VsimSimulatorMixin._run_persistent = run_persistent

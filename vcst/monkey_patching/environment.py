"""
Gives the simulator processes of a cocotb test the environment variables cocotb needs.

VUnit runs tests in several threads at once, so the variables can't be put in os.environ. Instead they are
kept per thread while a cocotb test simulates, and added to the environment of every process VUnit starts from
that thread. This works the same for all simulators and doesn't depend on how a simulator interface starts its
processes.
"""
import os
import threading
from contextlib import contextmanager

from vunit.ostools import Process

_extra_env = threading.local()

def get_extra_env():
    """Returns the environment variables added for the test simulating in this thread, None if there are none."""
    return getattr(_extra_env, "env", None)

@contextmanager
def extra_env(env):
    """
    Adds env to the environment of the processes started by this thread within the context. Variables whose value
    is None are removed.
    """
    _extra_env.env = env
    try:
        yield
    finally:
        _extra_env.env = None

_process_init = Process.__init__

def _init_with_extra_env(self, args, cwd=None, env=None):
    extra = get_extra_env()
    if extra:
        env = dict(os.environ if env is None else env)
        env.update(extra)
        env = {name: value for name, value in env.items() if value is not None}
    _process_init(self, args, cwd=cwd, env=env)

Process.__init__ = _init_with_extra_env

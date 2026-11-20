from cocotb.decorators import test as cocotb_test

class test(cocotb_test):
    """
    Subclass of cocotb.decorators.test (https://docs.cocotb.org/en/v1.9.2/_modules/cocotb/decorators.html) which
    adds support for an "attributes" keyword argument.

    Used as ``@vcst.test(..., attributes=['.long_running'])`` in lieu of ``@cocotb.test(...)``.
    """
    def __init__(self, *args, **kwargs):
        self.vcst_attributes = list(kwargs.pop("attributes", None) or [])  # cocotb's constructor would error on it
        super().__init__(*args, **kwargs)

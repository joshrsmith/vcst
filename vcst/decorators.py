import cocotb

from .utils.compat import COCOTB2

if COCOTB2:

    def test(obj=None, *, attributes=None, **kwargs):
        """
        Wrapper around cocotb.test() (https://docs.cocotb.org/en/stable/library_reference.html#cocotb.test) which
        adds support for an "attributes" keyword argument.

        Used as ``@vcst.test(..., attributes=['.long_running'])`` in lieu of ``@cocotb.test(...)``. The attributes
        apply to every test the decorated function produces, e.g. when combined with ``@cocotb.parametrize``.
        """

        def add_attributes(cocotb_test):
            cocotb_test.vcst_attributes = list(attributes) if attributes is not None else []
            return cocotb_test

        if obj is not None:
            # Used without arguments, i.e. @vcst.test
            return add_attributes(cocotb.test(obj))

        cocotb_decorator = cocotb.test(**kwargs)
        return lambda func: add_attributes(cocotb_decorator(func))

else:
    from cocotb.decorators import test as cocotb_test

    class test(cocotb_test):
        """
        Subclass of cocotb.decorators.test (https://docs.cocotb.org/en/v1.9.2/_modules/cocotb/decorators.html) which
        adds support for an "attributes" keyword argument.

        Used as ``@vcst.test(..., attributes=['.long_running'])`` in lieu of ``@cocotb.test(...)``.
        """

        def __init__(self, *args, **kwargs):
            self.vcst_attributes = list(
                kwargs.pop("attributes", None) or []
            )  # cocotb's constructor would error on it
            super().__init__(*args, **kwargs)

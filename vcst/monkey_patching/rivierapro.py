#Replaces some of VUnit's simulator logic for Riviera in order to deal with generic strings.
import threading
import vunit.sim_if.rivierapro
from vunit.sim_if.rivierapro import RivieraProInterface

#Whether string values are quoted, for the test whose vsim command is created by this thread
_formatting = threading.local()

def is_iterable(obj):
   try:
      iterator = iter(obj)
      return True
   except TypeError:
      return False

def format_generic(*args):
   """
   Formats the value of a generic (the last argument) for vsim. Iterables become aggregates. Values with spaces are
   quoted, and with a Verilog top level all strings, as Riviera-PRO needs quotes for Verilog string parameters. Generics
   of VHDL top levels are otherwise passed on as written, as VUnit does, e.g. enumeration literals, x"00FF" or
   "(FOO,BAR)".
   """
   value = args[-1]
   if not isinstance(value, str) and is_iterable(value):
      value_str = "("
      for item in value:
         value_str = value_str + format_generic(item) + ","
      #Remove the comma at the end
      value_str = value_str[0:len(value_str)-1] + ")"
      return value_str
   else:
       value_str = str(value)
       if " " in value_str or (isinstance(value, str) and getattr(_formatting, "quote_strings", False)):
           return f'"{value_str}"'
       return value_str

_create_load_function = RivieraProInterface._create_load_function

def create_load_function(self, test_suite_name, config, *args, **kwargs):
   """
   Creates the vsim command of a test, quoting string generics if the top level is a Verilog module, which has no
   architecture
   """
   _formatting.quote_strings = config.architecture_name is None
   try:
      return _create_load_function(self, test_suite_name, config, *args, **kwargs)
   finally:
      _formatting.quote_strings = False

###############################################################
vunit.sim_if.rivierapro.format_generic = format_generic
RivieraProInterface._create_load_function = create_load_function

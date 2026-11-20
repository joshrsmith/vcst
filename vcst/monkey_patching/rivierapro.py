#Replaces some of VUnit's simulator logic for Riviera in order to deal with generic strings.
import vunit.sim_if.rivierapro

def is_iterable(obj):
   try:
      iterator = iter(obj)
      return True
   except TypeError:
      return False

def format_generic(value):
   if not isinstance(value, str) and is_iterable(value):
      value_str = "("
      for item in value:
         value_str = value_str + format_generic(item) + ","
      #Remove the comma at the end
      value_str = value_str[0:len(value_str)-1] + ")"
      return value_str
   else:
       value_str = str(value)
       if " " in value_str or type(value) is str:
           return f'"{value_str}"'
       return value_str

###############################################################
vunit.sim_if.rivierapro.format_generic = format_generic

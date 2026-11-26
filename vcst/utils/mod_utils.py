import inspect
import os
import site
import sys
import sysconfig


def get_module(stack_level):
    """
    Get a reference to the module at some level of the stack.
    """
    stack = inspect.stack()
    if stack_level >= len(stack):
        raise Exception("Stack level was to large.")

    # +1 because this function is on the stack!
    frame = inspect.stack()[stack_level + 1]

    # Get the module from the right frame.

    mod = inspect.getmodule(frame[0])
    return mod


def get_calling_module():
    # This function is on the stack already, so we want to get the one who called this.
    mod = get_module(2)
    return mod


# The directory each top-level module imported by import_mod was imported from
_IMPORTED_FROM = {}


def import_mod(module_path):
    """Imports a module given a path to the module. Handles splitting the path off and changing
    directories, then changing back. Modules with the same name in different directories are
    different modules.
    """
    old_dir = os.getcwd()
    old_path = list(sys.path)
    mod_dir, mod_name = os.path.split(module_path)

    if mod_dir != "":
        os.chdir(mod_dir)
        sys.path.append(os.getcwd())

    # Python caches modules by name, so a module with the name of one imported from another
    # directory would be that module. Forget it, and the modules of its package, to import this one.
    top_name = mod_name.split(".")[0]
    this_dir = os.getcwd()
    if _IMPORTED_FROM.get(top_name, this_dir) != this_dir:
        for name in list(sys.modules):
            if name == top_name or name.startswith(f"{top_name}."):
                del sys.modules[name]
    _IMPORTED_FROM[top_name] = this_dir

    try:
        mod = __import__(mod_name)
        components = mod_name.split(".")
        for comp in components[1:]:
            mod = getattr(mod, comp)
    finally:
        os.chdir(old_dir)
        sys.path = old_path
    return mod


def _library_directories():
    """The directories of the standard library and of installed packages"""
    directories = {
        sysconfig.get_paths().get(key) for key in ("stdlib", "platstdlib", "purelib", "platlib")
    }
    try:
        directories.update(site.getsitepackages())
        directories.add(site.getusersitepackages())
    except AttributeError:  # site is limited in some virtual environments
        pass
    return [os.path.realpath(d) for d in directories if d]


def project_python_files():
    """
    Returns the real paths of the files of all modules imported so far which aren't part of the standard library or
    installed in site-packages, and aren't the main script. These are the Python files of the user's project,
    including packages installed in editable mode, whose files are those of their source directory.
    """
    library_directories = _library_directories()
    files = set()
    for name, module in list(sys.modules.items()):
        file_name = getattr(module, "__file__", None)
        # multiprocessing imports the main script as __mp_main__
        if name in ("__main__", "__mp_main__") or not isinstance(file_name, str):
            continue
        path = os.path.realpath(file_name)
        if any(os.path.commonpath([path, d]) == d for d in library_directories):
            continue
        files.add(path)
    return files

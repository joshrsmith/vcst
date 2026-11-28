"""
Lets coverage.py save its data in a Python that uses an SQLite older than 3.26, such as the one Riviera-PRO loads into
the simulator.

Why: Riviera-PRO 2026.04 ships its own libsqlite3 (bin/Linux64/libsqlite3.so, SQLite 3.25.3 of 2018), which its
simulator loads before the system's, so the sqlite3 module of the Python embedded by cocotb uses it if that Python links
SQLite dynamically, as most do. coverage.py 7.3.2 and later, on Python 3.12 and later, turns SQLite's defensive mode off
whenever it opens a data file, with Connection.setconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE, False), if sqlite3 has that
constant. SQLite only knows that setting from 3.26, so 3.25.3 refuses it without an error message, Python raises
"SystemError: <method 'setconfig' of 'sqlite3.Connection' objects> returned NULL without setting an exception", and
cocotb can't save or read coverage data (COCOTB_USER_COVERAGE, COVERAGE with cocotb 1.x). This happens with and without
VCST.

What: with an SQLite older than 3.26, the constant is removed from the sqlite3 module, so that coverage.py does what it
does on Python 3.11 and keeps defensive mode, which such an SQLite doesn't have anyway. Nothing could use the constant
with such an SQLite, so nothing that worked stops working; with a current SQLite nothing is done. vcst.utils does this
when it's imported, so in every Python that imports VCST: the one running the run script, where it normally does
nothing, and the simulator's, as every cocotb module run by VCST imports vcst.utils for set_top_level.

Limit: that import comes after cocotb started, so it helps whatever coverage.py does later: saving the data at the end,
which is all cocotb 1.x and 2.0 do. cocotb 2.1 also reads an existing data file when it starts, before the cocotb module
is imported, which still fails. The README says to avoid it: a data file of its own for each simulator, with the files
of the previous run erased.

When to remove: once no supported simulator loads an SQLite older than 3.26, or once coverage.py no longer fails with
such an SQLite. tests/unit/test_old_sqlite.py checks this with an old SQLite (Riviera-PRO's own when VUNIT_SIMULATOR is
rivierapro, or the one VCST_OLD_SQLITE names, as CI does with SQLite 3.25.3 built from source): that coverage.py still
fails without the workaround, which tells when coverage.py has fixed it, and that it saves its data with the
workaround, which tells when a newer coverage.py or Python no longer works with it. It says when Riviera-PRO's own
SQLite is new enough not to need it.
"""

# The first SQLite with the setting SQLITE_DBCONFIG_DEFENSIVE
DEFENSIVE_SINCE = (3, 26, 0)


def hide_defensive_config(sqlite3=None):
    """
    Removes sqlite3.SQLITE_DBCONFIG_DEFENSIVE if the SQLite in use is older than 3.26. Returns whether it was removed.
    sqlite3 is the module, imported if not given; nothing is done without one.
    """
    if sqlite3 is None:
        try:
            import sqlite3
        except ImportError:
            return False
    if sqlite3.sqlite_version_info >= DEFENSIVE_SINCE or not hasattr(
        sqlite3, "SQLITE_DBCONFIG_DEFENSIVE"
    ):
        return False
    del sqlite3.SQLITE_DBCONFIG_DEFENSIVE
    return True

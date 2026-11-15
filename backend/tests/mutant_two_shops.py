"""Mutation check of test_two_shops.py (D-MULTI-SHOP-004): with the shop filter removed from store._owned, the test
must fail. The filter is removed in this process only, by replacing the function; no file is changed.

Run from backend/:  uv run python tests/mutant_two_shops.py
Exit 0 with "MUTANT KILLED" when test_two_shops fails, as it must; exit 1 with "MUTANT SURVIVED" when it passes."""
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

from affiche.posters import jobs, reads, store


def unfiltered(conn, table, shop, id):
    """store._owned without its shop: any shop's row, by its id alone."""
    row = conn.execute(text(f"SELECT * FROM {table} WHERE id=:id"), {"id": id}).mappings().first()
    if row is None:
        raise store.Refused("not_found", 404)
    return row


# jobs and reads import the function by name; every other module calls store._owned when it runs.
store._owned = jobs._owned = reads._owned = unfiltered
code = pytest.main([str(Path(__file__).with_name("test_two_shops.py")), "-q", "-x", "-p", "no:cacheprovider"])
killed = code == pytest.ExitCode.TESTS_FAILED
print("MUTANT KILLED: test_two_shops fails without the shop filter in store._owned" if killed
      else f"MUTANT SURVIVED: pytest exited {code!r} with the shop filter removed")
sys.exit(0 if killed else 1)

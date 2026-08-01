"""
Standalone migration for schema future-proofing (per Decision: design for
growth without building it now). Adds:
  - CreatedOn / ModifiedOn to tblFloor and tblRoom (Client and Project already
    have these -- this just brings Floor/Space in line with the same pattern)
  - Archived flag to tblClient, tblProject, tblFloor, tblRoom (all default 0,
    unused by any current app logic or UI -- purely schema readiness so a
    future Archive workflow doesn't require a redesign; CreatedBy/roles stay
    deferred entirely since they need real user accounts that don't exist yet)

Safe to run against a database with real data -- only adds new nullable/
defaulted columns, never touches existing values.

Usage: python migrate_v280_future_proofing.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

changes = []


def add_column_if_missing(table, column, definition):
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    if column not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        changes.append(f"{table}.{column}")


# Timestamps on Floor and Space, matching the pattern Client/Project already use
add_column_if_missing("tblFloor", "CreatedOn", "TEXT")
add_column_if_missing("tblFloor", "ModifiedOn", "TEXT")
add_column_if_missing("tblRoom", "CreatedOn", "TEXT")
add_column_if_missing("tblRoom", "ModifiedOn", "TEXT")

# Archived flag everywhere -- unused for now, just schema readiness
add_column_if_missing("tblClient", "Archived", "INTEGER NOT NULL DEFAULT 0")
add_column_if_missing("tblProject", "Archived", "INTEGER NOT NULL DEFAULT 0")
add_column_if_missing("tblFloor", "Archived", "INTEGER NOT NULL DEFAULT 0")
add_column_if_missing("tblRoom", "Archived", "INTEGER NOT NULL DEFAULT 0")

conn.commit()

# Backfill CreatedOn/ModifiedOn for any existing real floors/spaces with
# today's date, since their actual creation time was never tracked before
# this column existed -- better than leaving it NULL.
cur.execute("UPDATE tblFloor SET CreatedOn=datetime('now') WHERE CreatedOn IS NULL")
cur.execute("UPDATE tblFloor SET ModifiedOn=datetime('now') WHERE ModifiedOn IS NULL")
cur.execute("UPDATE tblRoom SET CreatedOn=datetime('now') WHERE CreatedOn IS NULL")
cur.execute("UPDATE tblRoom SET ModifiedOn=datetime('now') WHERE ModifiedOn IS NULL")
conn.commit()

conn.close()

if changes:
    print("Added columns:")
    for c in changes:
        print(" -", c)
else:
    print("All columns already present -- nothing to add.")
print("\nMigration complete. No existing client/project/floor/space data was modified beyond adding these columns.")

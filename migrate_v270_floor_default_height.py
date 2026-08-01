"""
Standalone migration for v2.7.0's Floor Default Ceiling Height feature.
Safe to run against a database with real clients/projects -- only adds new
columns and backfills them sensibly; never touches existing client/project
rows beyond adding these two new fields with safe defaults.

Usage: python migrate_v270_floor_default_height.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("PRAGMA table_info(tblFloor)")
cols = [r[1] for r in cur.fetchall()]
if "DefaultCeilingHeight" not in cols:
    cur.execute("ALTER TABLE tblFloor ADD COLUMN DefaultCeilingHeight REAL DEFAULT 10")
    print("Added tblFloor.DefaultCeilingHeight (default 10 ft)")
else:
    print("tblFloor.DefaultCeilingHeight already exists")

cur.execute("PRAGMA table_info(tblRoom)")
cols = [r[1] for r in cur.fetchall()]
if "UsesFloorDefaultHeight" not in cols:
    cur.execute("ALTER TABLE tblRoom ADD COLUMN UsesFloorDefaultHeight INTEGER NOT NULL DEFAULT 1")
    print("Added tblRoom.UsesFloorDefaultHeight (default: True)")
else:
    print("tblRoom.UsesFloorDefaultHeight already exists")

conn.commit()

# Backfill: any existing real floors get a default of 10 ft (matches the
# app's own new-floor default); any existing real spaces are marked as
# "not using the floor default" since their current height was explicitly
# set before this feature existed -- safer than silently reassigning them.
cur.execute("UPDATE tblFloor SET DefaultCeilingHeight=10 WHERE DefaultCeilingHeight IS NULL")
floors_backfilled = cur.rowcount
cur.execute("UPDATE tblRoom SET UsesFloorDefaultHeight=0 WHERE CeilingHeight IS NOT NULL AND UsesFloorDefaultHeight=1")
rooms_marked_custom = cur.rowcount
conn.commit()

print(f"\nBackfilled DefaultCeilingHeight on {floors_backfilled} floor(s) with no value set.")
print(f"Marked {rooms_marked_custom} existing space(s) with an existing height as 'custom' (not floor-default) "
      f"-- their heights are preserved exactly as they were; nothing was changed.")

conn.close()
print("\nMigration complete. Existing clients, projects, floors, and spaces are untouched beyond the new columns.")

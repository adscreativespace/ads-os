"""
Standalone migration for v1.2.0's Floor Usage feature.
Safe to run against a database with real clients/projects/floors -- only adds
the new column and backfills it from each floor's project type; never deletes
or overwrites anything else.

Usage: python migrate_v120_floor_usage.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("PRAGMA table_info(tblFloor)")
cols = [r[1] for r in cur.fetchall()]
if "FloorUsage" not in cols:
    cur.execute("ALTER TABLE tblFloor ADD COLUMN FloorUsage TEXT")
    print("Added tblFloor.FloorUsage")
else:
    print("FloorUsage column already exists")

conn.commit()

# Backfill: any existing real floors default to their project's own type,
# preserving current behavior exactly (nothing changes for them until you
# explicitly override a floor's usage for a mixed-use case)
cur.execute("""
    SELECT f.FloorID, pt.ProjectType FROM tblFloor f
    JOIN tblProject p ON f.ProjectID = p.ProjectID
    JOIN mstProjectType pt ON p.ProjectTypeID = pt.ProjectTypeID
    WHERE f.FloorUsage IS NULL
""")
existing_floors = cur.fetchall()
for floor_id, project_type in existing_floors:
    cur.execute("UPDATE tblFloor SET FloorUsage=? WHERE FloorID=?", (project_type, floor_id))
conn.commit()
print(f"Backfilled FloorUsage for {len(existing_floors)} existing floor(s) -- no data lost, "
      f"each defaults to its project's own type.")

conn.close()
print("\nMigration complete. Existing clients, projects, floors, and spaces are untouched.")

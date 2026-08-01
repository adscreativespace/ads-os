"""
Standalone migration for v0.6.1's Floor Level / Display Name / Floor Code redesign.
Safe to run against a database that already has real clients/projects --
only adds new columns and backfills them; never deletes or overwrites existing rows.

Usage: python migrate_v061_floor_fields.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("PRAGMA table_info(mstFloorLibrary)")
cols = [r[1] for r in cur.fetchall()]
if "DefaultCode" not in cols:
    cur.execute("ALTER TABLE mstFloorLibrary ADD COLUMN DefaultCode TEXT")
    print("Added mstFloorLibrary.DefaultCode")

cur.execute("PRAGMA table_info(tblFloor)")
cols = [r[1] for r in cur.fetchall()]
if "FloorCode" not in cols:
    cur.execute("ALTER TABLE tblFloor ADD COLUMN FloorCode TEXT")
    print("Added tblFloor.FloorCode")
if "DisplayName" not in cols:
    cur.execute("ALTER TABLE tblFloor ADD COLUMN DisplayName TEXT")
    print("Added tblFloor.DisplayName")

conn.commit()

codes = {
    "Basement": "B1", "Mezzanine": "MZ", "Ground Floor": "GF", "First Floor": "FF",
    "Second Floor": "SF", "Third Floor": "TF", "Fourth Floor": "4F", "Fifth Floor": "5F",
    "Sixth Floor": "6F", "Seventh Floor": "7F", "Eighth Floor": "8F", "Ninth Floor": "9F",
    "Tenth Floor": "10F", "Terrace": "TR", "Custom": ""
}
for name, code in codes.items():
    cur.execute("UPDATE mstFloorLibrary SET DefaultCode=? WHERE FloorName=?", (code, name))
conn.commit()
print("Seeded default floor codes")

# Backfill any existing real floors: DisplayName = their current FloorName (no data changed in meaning)
cur.execute("SELECT FloorID, FloorName FROM tblFloor WHERE DisplayName IS NULL")
existing_floors = cur.fetchall()
for fid, fname in existing_floors:
    cur.execute("UPDATE tblFloor SET DisplayName=? WHERE FloorID=?", (fname, fid))
conn.commit()
print(f"Backfilled DisplayName for {len(existing_floors)} existing floor(s) -- no data lost")

conn.close()
print("\nMigration complete. Existing clients, projects, floors, and rooms are untouched.")

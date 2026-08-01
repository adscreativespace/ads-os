"""
Standalone migration: links trxBOQItem to mstMaterial. Real user feedback
identified that BOQ and Materials were being treated as fully separate,
requiring the same item (code, description, vendor, rate) to be typed twice
-- once in Materials, once in BOQ. This adds a nullable MaterialID so a BOQ
item can optionally reference a real Material record; selecting one in the
UI auto-fills Description/Unit/Rate/Vendor instead of retyping them.

Fully additive and backward-compatible -- BOQ items not tied to a specific
material (e.g. labour line items) continue to work exactly as before with
MaterialID simply NULL.

Safe to run against a database with real data.

Usage: python migrate_v360_boq_material_link.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("PRAGMA table_info(trxBOQItem)")
existing_cols = [r[1] for r in cur.fetchall()]
if "MaterialID" not in existing_cols:
    cur.execute("ALTER TABLE trxBOQItem ADD COLUMN MaterialID INTEGER REFERENCES mstMaterial(MaterialID)")
    print("Added trxBOQItem.MaterialID")
else:
    print("trxBOQItem.MaterialID already exists")
conn.commit()

# Self-register in the migration registry.
cur.execute("""CREATE TABLE IF NOT EXISTS sysMigrationHistory (
    MigrationID INTEGER PRIMARY KEY AUTOINCREMENT,
    MigrationName TEXT UNIQUE NOT NULL,
    AppliedOn TEXT NOT NULL DEFAULT (datetime('now')),
    AppVersion TEXT
)""")
cur.execute("INSERT OR IGNORE INTO sysMigrationHistory (MigrationName) VALUES (?)", ("migrate_v360_boq_material_link",))
conn.commit()

conn.close()
print("No existing BOQ items or materials were touched.")

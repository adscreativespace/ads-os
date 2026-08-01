"""
Standalone migration for Vendors, fourth of six Commercial modules.
Extends the minimal mstVendor table (VendorID, VendorName, Active) created
during BOQ/Materials with the full vendor profile fields -- additive only.
Every existing VendorID referenced from trxBOQItem or mstMaterial keeps
working unchanged; new columns are nullable/defaulted so existing rows don't
need any data filled in.

Safe to run against a database with real data.

Usage: python migrate_v330_vendors.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

new_columns = [
    ("VendorCode", "TEXT"),
    ("Category", "TEXT"),
    ("ContactPerson", "TEXT"),
    ("Phone", "TEXT"),
    ("Email", "TEXT"),
    ("GSTNo", "TEXT"),
    ("Address", "TEXT"),
    ("Status", "TEXT NOT NULL DEFAULT 'Active'"),
    ("Rating", "REAL"),
    ("CreatedOn", "TEXT"),
    ("ModifiedOn", "TEXT"),
]

cur.execute("PRAGMA table_info(mstVendor)")
existing_cols = [r[1] for r in cur.fetchall()]

added = []
for col_name, col_def in new_columns:
    if col_name not in existing_cols:
        cur.execute(f"ALTER TABLE mstVendor ADD COLUMN {col_name} {col_def}")
        added.append(col_name)
conn.commit()

# Backfill VendorCode for any vendors already created by BOQ/Materials (which
# only ever set VendorName) and timestamps, so nothing shows up blank.
cur.execute("SELECT VendorID FROM mstVendor WHERE VendorCode IS NULL ORDER BY VendorID")
existing_vendors = cur.fetchall()
for i, (vendor_id,) in enumerate(existing_vendors, start=1):
    code = f"VEN-{vendor_id:04d}"
    cur.execute("UPDATE mstVendor SET VendorCode=?, CreatedOn=datetime('now'), ModifiedOn=datetime('now') WHERE VendorID=?",
                (code, vendor_id))
conn.commit()

# Self-register in the migration registry so "About ADS OS" correctly shows
# this migration as applied, instead of silently missing it.
cur.execute("""CREATE TABLE IF NOT EXISTS sysMigrationHistory (
    MigrationID INTEGER PRIMARY KEY AUTOINCREMENT,
    MigrationName TEXT UNIQUE NOT NULL,
    AppliedOn TEXT NOT NULL DEFAULT (datetime('now')),
    AppVersion TEXT
)""")
cur.execute("INSERT OR IGNORE INTO sysMigrationHistory (MigrationName) VALUES (?)", ("migrate_v330_vendors",))
conn.commit()

conn.close()
print(f"Added columns: {', '.join(added) if added else '(none, already present)'}")
print(f"Backfilled VendorCode for {len(existing_vendors)} existing vendor(s) created by BOQ/Materials.")
print("No existing vendor references from trxBOQItem or mstMaterial were touched.")

"""
Standalone migration for BOQ (Bill of Quantities), second of six Commercial
modules. Adds a minimal mstVendor table (VendorID, VendorName only -- the
full Vendor module with GST/contact/ratings is module #4 in the sequence;
this stays extensible via additive migration when that's built, so BOQ items
already pointing at a VendorID keep working without any data migration) and
trxBOQItem for the actual line items.

Safe to run against a database with real data -- only creates new tables.

Usage: python migrate_v310_boq.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS mstVendor (
    VendorID     INTEGER PRIMARY KEY AUTOINCREMENT,
    VendorName   TEXT NOT NULL,
    Active       INTEGER NOT NULL DEFAULT 1
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS trxBOQItem (
    BOQItemID     INTEGER PRIMARY KEY AUTOINCREMENT,
    ProjectID     INTEGER NOT NULL REFERENCES tblProject(ProjectID) ON DELETE CASCADE,
    ItemCode      TEXT,
    Description   TEXT NOT NULL,
    Category      TEXT NOT NULL DEFAULT 'Uncategorized',
    Unit          TEXT,
    Quantity      REAL NOT NULL DEFAULT 0,
    Rate          REAL NOT NULL DEFAULT 0,
    Amount        REAL NOT NULL DEFAULT 0,
    VendorID      INTEGER REFERENCES mstVendor(VendorID),
    Status        TEXT NOT NULL DEFAULT 'Not Started',
    ItemOrder     INTEGER NOT NULL DEFAULT 0,
    CreatedOn     TEXT NOT NULL DEFAULT (datetime('now')),
    ModifiedOn    TEXT NOT NULL DEFAULT (datetime('now'))
)""")


# Self-register in the migration registry so "About ADS OS" correctly
# shows this migration as applied, instead of silently missing it.
cur.execute("""CREATE TABLE IF NOT EXISTS sysMigrationHistory (
    MigrationID INTEGER PRIMARY KEY AUTOINCREMENT,
    MigrationName TEXT UNIQUE NOT NULL,
    AppliedOn TEXT NOT NULL DEFAULT (datetime('now')),
    AppVersion TEXT
)""")
cur.execute("INSERT OR IGNORE INTO sysMigrationHistory (MigrationName) VALUES (?)", ("migrate_v310_boq",))

conn.commit()
conn.close()
print("Migration complete: mstVendor and trxBOQItem created.")
print("No existing tables or data were touched.")

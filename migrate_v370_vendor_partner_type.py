"""
Standalone migration: adds PartnerType to mstVendor. Real feedback asked
"where do Contractors go?" -- rather than a separate Contractors module
(more duplicate master data, another place to keep vendor info in sync),
Contractors/Labour/Consultants/Transport are all fundamentally the same
concept as a Vendor: an external party you pay. PartnerType distinguishes
what kind, using the SAME record, contact info, and purchase history
already built for Vendors -- one master list, not several overlapping ones.

Safe to run against a database with real data -- additive column with a
sensible default, existing vendor rows are untouched beyond gaining this
new field (defaulted to 'Supplier', the most common case).

Usage: python migrate_v370_vendor_partner_type.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("PRAGMA table_info(mstVendor)")
existing_cols = [r[1] for r in cur.fetchall()]
if "PartnerType" not in existing_cols:
    cur.execute("ALTER TABLE mstVendor ADD COLUMN PartnerType TEXT NOT NULL DEFAULT 'Supplier'")
    print("Added mstVendor.PartnerType (defaulted existing vendors to 'Supplier')")
else:
    print("mstVendor.PartnerType already exists")
conn.commit()

cur.execute("""CREATE TABLE IF NOT EXISTS sysMigrationHistory (
    MigrationID INTEGER PRIMARY KEY AUTOINCREMENT,
    MigrationName TEXT UNIQUE NOT NULL,
    AppliedOn TEXT NOT NULL DEFAULT (datetime('now')),
    AppVersion TEXT
)""")
cur.execute("INSERT OR IGNORE INTO sysMigrationHistory (MigrationName) VALUES (?)", ("migrate_v370_vendor_partner_type",))
conn.commit()

conn.close()
print("No existing vendor data was touched beyond adding this column.")

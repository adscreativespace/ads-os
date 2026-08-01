"""
Standalone migration for v4.4.1 -- Business Partner field cleanup.
Fixes a real, confirmed design overlap: PartnerType and Category both
contained trade values like "Civil Contractor" and "Interior Contractor",
creating ambiguity about which field to use. Three distinct fields now:

  - PartnerType = business relationship only (Supplier, Contractor,
    Consultant, Transport, Rental Equipment, Manufacturer, Fabricator,
    Labour Agency, Architect, Engineer, Surveyor).
  - Scope of Work (NEW, many-to-many via trxVendorScope) = the actual
    trades/services performed (Furniture, False Ceiling, Flooring,
    Electrical, Civil Works, etc.) -- a vendor can have several.
  - Category, renamed in the UI to "Product Category", stays a single
    value but is now Supplier-specific (Cement, Steel, Tiles, etc.) --
    existing Category data is NOT cleared for non-Suppliers, since forcibly
    erasing real data based on a UI relabeling would be destructive; it
    just won't be shown/editable for non-Supplier partner types going
    forward.

Existing real vendor data is migrated carefully, not guessed at:
  - PartnerType 'Civil Contractor' / 'Interior Contractor' -> 'Contractor'
    (the trade detail that's lost belongs in Scope of Work, but which exact
    scope item applies isn't safely inferable from the old value alone --
    left unchecked, flagged for manual review below).
  - PartnerType 'Labour Contractor' -> 'Labour Agency' (unambiguous 1:1).
  - All other existing PartnerType values (Supplier, Consultant, Transport,
    Rental Equipment, Fabricator, Manufacturer) are unchanged -- they still
    exist in the new list exactly as before.

Safe to run against a database with real data.

Usage: python migrate_v391_partner_scope.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

SCOPE_ITEMS = [
    "Furniture", "Furniture Polishing", "False Ceiling", "POP Ceiling", "PVC Ceiling",
    "Flooring", "Marble", "Granite", "Painting", "Electrical", "Plumbing", "Aluminium",
    "Glass", "Steel Fabrication", "MS Fabrication", "SS Fabrication", "Civil Works",
    "Brick Work", "Plaster", "Waterproofing", "HVAC", "Modular Kitchen", "Signage",
    "Landscaping", "Demolition", "Cleaning",
]

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS mstScopeOfWork (
    ScopeID    INTEGER PRIMARY KEY AUTOINCREMENT,
    ScopeName  TEXT UNIQUE NOT NULL
)""")
for name in SCOPE_ITEMS:
    cur.execute("INSERT OR IGNORE INTO mstScopeOfWork (ScopeName) VALUES (?)", (name,))

cur.execute("""CREATE TABLE IF NOT EXISTS trxVendorScope (
    VendorID   INTEGER NOT NULL REFERENCES mstVendor(VendorID) ON DELETE CASCADE,
    ScopeID    INTEGER NOT NULL REFERENCES mstScopeOfWork(ScopeID) ON DELETE CASCADE,
    PRIMARY KEY (VendorID, ScopeID)
)""")
conn.commit()

migrated_to_review = []

cur.execute("SELECT VendorID, VendorName, PartnerType FROM mstVendor WHERE PartnerType IN ('Civil Contractor', 'Interior Contractor')")
rows = cur.fetchall()
for vendor_id, vendor_name, old_type in rows:
    cur.execute("UPDATE mstVendor SET PartnerType='Contractor' WHERE VendorID=?", (vendor_id,))
    migrated_to_review.append((vendor_name, old_type, "Contractor"))

cur.execute("UPDATE mstVendor SET PartnerType='Labour Agency' WHERE PartnerType='Labour Contractor'")
labour_migrated = cur.rowcount

conn.commit()

cur.execute("""CREATE TABLE IF NOT EXISTS sysMigrationHistory (
    MigrationID INTEGER PRIMARY KEY AUTOINCREMENT,
    MigrationName TEXT UNIQUE NOT NULL,
    AppliedOn TEXT NOT NULL DEFAULT (datetime('now')),
    AppVersion TEXT
)""")
cur.execute("INSERT OR IGNORE INTO sysMigrationHistory (MigrationName) VALUES (?)", ("migrate_v391_partner_scope",))
conn.commit()
conn.close()

print(f"Created mstScopeOfWork ({len(SCOPE_ITEMS)} items seeded) and trxVendorScope.")
print(f"Migrated {labour_migrated} vendor(s) from 'Labour Contractor' -> 'Labour Agency' (unambiguous, no review needed).")
if migrated_to_review:
    print(f"\nMigrated {len(migrated_to_review)} vendor(s) from a trade-specific PartnerType to plain 'Contractor':")
    for name, old, new in migrated_to_review:
        print(f"  {name}: '{old}' -> '{new}'")
    print("These vendors' Scope of Work was intentionally left UNCHECKED -- the old value doesn't map safely to "
          "one specific scope item. Please review and set Scope of Work for each of these vendors manually.")
else:
    print("\nNo vendors needed PartnerType migration.")

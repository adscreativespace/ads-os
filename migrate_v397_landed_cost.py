"""
Standalone migration: Landed Cost Management foundation.

Creates the real "Purchase Invoice" grouping this feature depends on --
until now, a multi-material purchase bill only existed as a shared text
note ("Bill: XYZ") inside each trxMaterialPurchase row, with no actual
structural link between line items bought on the same invoice. That's
fine for recording what was bought, but it's not enough to allocate a
shared Transportation/Loading charge across multiple materials on the
same bill, which is the whole point of Landed Cost.

Three purely additive changes, safe against real data:
1. trxPurchaseInvoice (NEW) -- one row per real vendor bill (Vendor,
   Invoice No, Invoice Date).
2. trxPurchaseCharge (NEW) -- one row per additional charge on that bill
   (Transportation, Loading, Handling, etc.), with its own allocation
   method.
3. trxMaterialPurchase gains a nullable PurchaseInvoiceID column --
   every existing purchase row gets NULL (no invoice to link to, since
   they predate this feature), which is exactly correct: old purchases
   simply have no landed-cost charges to allocate, not a fabricated one.

Usage: python migrate_v397_landed_cost.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS trxPurchaseInvoice (
    PurchaseInvoiceID INTEGER PRIMARY KEY AUTOINCREMENT,
    VendorID INTEGER REFERENCES mstVendor(VendorID),
    InvoiceNo TEXT,
    InvoiceDate TEXT NOT NULL DEFAULT (date('now')),
    CreatedOn TEXT NOT NULL DEFAULT (datetime('now'))
)""")
print("Created trxPurchaseInvoice (or already existed).")

cur.execute("""CREATE TABLE IF NOT EXISTS trxPurchaseCharge (
    ChargeID INTEGER PRIMARY KEY AUTOINCREMENT,
    PurchaseInvoiceID INTEGER NOT NULL REFERENCES trxPurchaseInvoice(PurchaseInvoiceID),
    ChargeType TEXT NOT NULL,
    Amount REAL NOT NULL,
    AllocationMethod TEXT NOT NULL DEFAULT 'By Value',
    CreatedOn TEXT NOT NULL DEFAULT (datetime('now'))
)""")
print("Created trxPurchaseCharge (or already existed).")

cur.execute("PRAGMA table_info(trxMaterialPurchase)")
existing_cols = {row[1] for row in cur.fetchall()}
if "PurchaseInvoiceID" not in existing_cols:
    cur.execute("ALTER TABLE trxMaterialPurchase ADD COLUMN PurchaseInvoiceID INTEGER "
               "REFERENCES trxPurchaseInvoice(PurchaseInvoiceID)")
    print("Added trxMaterialPurchase.PurchaseInvoiceID (nullable) -- existing rows are NULL, correctly "
          "meaning 'no invoice-level charges to allocate', not a fabricated link.")
else:
    print("trxMaterialPurchase.PurchaseInvoiceID already exists -- skipped.")

conn.commit()

cur.execute("""CREATE TABLE IF NOT EXISTS sysMigrationHistory (
    MigrationID INTEGER PRIMARY KEY AUTOINCREMENT,
    MigrationName TEXT UNIQUE NOT NULL,
    AppliedOn TEXT NOT NULL DEFAULT (datetime('now')),
    AppVersion TEXT
)""")
cur.execute("INSERT OR IGNORE INTO sysMigrationHistory (MigrationName) VALUES (?)", ("migrate_v397_landed_cost",))
conn.commit()
conn.close()
print("Done.")

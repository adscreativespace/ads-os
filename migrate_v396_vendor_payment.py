"""
Standalone migration: creates trxVendorPayment.

Enables genuinely real "Payments Made" and "Outstanding" figures for
vendors -- previously these were correctly NOT shown anywhere in the app,
since no table existed to record a vendor payment against real purchases.
This does not retroactively invent any payment history: the table starts
completely empty for every vendor, and every real number derived from it
(Payments Made, Outstanding) will read as real zeroes until an actual
payment is recorded through the new "Record Payment" UI -- the same
pattern already used for invoice payments (unpaid until a real payment is
logged).

Safe to run against a database with real data -- purely additive, no
existing table or column touched.

Usage: python migrate_v396_vendor_payment.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS trxVendorPayment (
    PaymentID INTEGER PRIMARY KEY AUTOINCREMENT,
    VendorID INTEGER NOT NULL REFERENCES mstVendor(VendorID),
    PurchaseID INTEGER REFERENCES trxMaterialPurchase(PurchaseID),
    Amount REAL NOT NULL,
    PaymentDate TEXT NOT NULL,
    PaymentMode TEXT,
    Reference TEXT,
    Notes TEXT,
    CreatedOn TEXT NOT NULL DEFAULT (datetime('now'))
)""")
print("Created trxVendorPayment (or already existed) -- starts empty, no payment history invented.")
conn.commit()

cur.execute("""CREATE TABLE IF NOT EXISTS sysMigrationHistory (
    MigrationID INTEGER PRIMARY KEY AUTOINCREMENT,
    MigrationName TEXT UNIQUE NOT NULL,
    AppliedOn TEXT NOT NULL DEFAULT (datetime('now')),
    AppVersion TEXT
)""")
cur.execute("INSERT OR IGNORE INTO sysMigrationHistory (MigrationName) VALUES (?)", ("migrate_v396_vendor_payment",))
conn.commit()
conn.close()
print("Done.")

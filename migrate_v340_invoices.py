"""
Standalone migration for Invoice Center, fifth of six Commercial modules.
Invoices can optionally link to a saved Fee Calculation (module #1) for their
amount, or be entered manually. Paid Amount is always computed live from
actual trxInvoicePayment records -- never a manually-typed "paid" field that could
drift out of sync with reality, matching the same discipline used for
Vendor's Total Purchase.

Safe to run against a database with real data -- only creates new tables.

Usage: python migrate_v340_invoices.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS trxInvoice (
    InvoiceID       INTEGER PRIMARY KEY AUTOINCREMENT,
    ProjectID       INTEGER NOT NULL REFERENCES tblProject(ProjectID) ON DELETE CASCADE,
    InvoiceNo       TEXT UNIQUE NOT NULL,
    InvoiceDate     TEXT NOT NULL DEFAULT (date('now')),
    DueDate         TEXT,
    InvoiceType     TEXT NOT NULL DEFAULT 'Milestone',
    Amount          REAL NOT NULL DEFAULT 0,
    Status          TEXT NOT NULL DEFAULT 'Draft',
    FeeCalculationID INTEGER REFERENCES trxFeeCalculation(CalculationID),
    Notes           TEXT,
    CreatedOn       TEXT NOT NULL DEFAULT (datetime('now')),
    ModifiedOn      TEXT NOT NULL DEFAULT (datetime('now'))
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS trxInvoicePayment (
    PaymentID     INTEGER PRIMARY KEY AUTOINCREMENT,
    InvoiceID     INTEGER NOT NULL REFERENCES trxInvoice(InvoiceID) ON DELETE CASCADE,
    PaymentDate   TEXT NOT NULL DEFAULT (date('now')),
    Amount        REAL NOT NULL,
    PaymentMode   TEXT,
    Notes         TEXT,
    CreatedOn     TEXT NOT NULL DEFAULT (datetime('now'))
)""")


# Self-register in the migration registry so "About ADS OS" correctly
# shows this migration as applied, instead of silently missing it.
cur.execute("""CREATE TABLE IF NOT EXISTS sysMigrationHistory (
    MigrationID INTEGER PRIMARY KEY AUTOINCREMENT,
    MigrationName TEXT UNIQUE NOT NULL,
    AppliedOn TEXT NOT NULL DEFAULT (datetime('now')),
    AppVersion TEXT
)""")
cur.execute("INSERT OR IGNORE INTO sysMigrationHistory (MigrationName) VALUES (?)", ("migrate_v340_invoices",))

conn.commit()
conn.close()
print("Migration complete: trxInvoice and trxInvoicePayment created.")
print("No existing tables or data were touched.")

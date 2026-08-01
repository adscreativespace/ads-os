"""
Standalone migration: creates trxSiteExpense.

Real gap this closes, flagged as a known deferred item since v4.9.7
(Landed Cost's own changelog: "Site Expense Management is treated as a
genuinely separate, later milestone... mixing two different financial
concepts (material landed cost vs. non-material site costs) into a
single pass would blur both"). This is that separate milestone.

Covers real, non-material site costs that don't belong in Materials
(which is for stocked, purchasable items) or Vendor/Contractor payments
(which are for a specific business partner's invoiced work): labour
wages, site transport, tea/refreshments, tools & consumables, site
security, and general miscellaneous site spend.

Safe to run against a database with real data -- purely additive, no
existing table or column touched.

Usage: python migrate_v399_site_expense.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS trxSiteExpense (
    ExpenseID     INTEGER PRIMARY KEY AUTOINCREMENT,
    ProjectID     INTEGER NOT NULL REFERENCES tblProject(ProjectID) ON DELETE CASCADE,
    ExpenseDate   TEXT NOT NULL DEFAULT (date('now')),
    Category      TEXT NOT NULL DEFAULT 'Miscellaneous',
    Amount        REAL NOT NULL,
    PaidTo        TEXT,
    PaymentMode   TEXT,
    Notes         TEXT,
    CreatedOn     TEXT NOT NULL DEFAULT (datetime('now')),
    ModifiedOn    TEXT NOT NULL DEFAULT (datetime('now'))
)""")
print("Created trxSiteExpense (or already existed) -- starts empty, no expense history invented.")
conn.commit()

cur.execute("""CREATE TABLE IF NOT EXISTS sysMigrationHistory (
    MigrationID INTEGER PRIMARY KEY AUTOINCREMENT,
    MigrationName TEXT UNIQUE NOT NULL,
    AppliedOn TEXT NOT NULL DEFAULT (datetime('now')),
    AppVersion TEXT
)""")
cur.execute("INSERT OR IGNORE INTO sysMigrationHistory (MigrationName) VALUES (?)", ("migrate_v399_site_expense",))
conn.commit()
conn.close()
print("Done. No existing tables or data touched.")

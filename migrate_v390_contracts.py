"""
Standalone migration for v4.4.0 -- Contract Management Foundation.
Per BUSINESS_RULES.md: no separate Contractor Master (extends mstVendor
instead, BR-001), quotations are copied not referenced (BR-002), commission
lives on the contract not the partner (BR-003), payments are additive with
computed status (BR-004), Fixed vs Running contracts are structurally
distinct (BR-005). Board Calculation (BR-006) and Weekly Labour are
deliberately NOT included -- explicitly deferred to v4.5.0/v4.6.0 per the
agreed phased roadmap.

Fully additive -- extends mstVendor with new nullable columns, and creates
five new tables. No existing table structure changed, no existing data
touched.

Safe to run against a database with real data.

Usage: python migrate_v390_contracts.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# ---------------- Business Partner (mstVendor) enhancements ----------------
new_vendor_columns = [
    ("AadhaarNo", "TEXT"),
    ("PANNo", "TEXT"),
    ("BankAccountName", "TEXT"),
    ("BankAccountNumber", "TEXT"),
    ("BankIFSC", "TEXT"),
    ("BankName", "TEXT"),
    ("IsPreferred", "INTEGER NOT NULL DEFAULT 0"),
]
cur.execute("PRAGMA table_info(mstVendor)")
existing_cols = [r[1] for r in cur.fetchall()]
added = []
for col_name, col_def in new_vendor_columns:
    if col_name not in existing_cols:
        cur.execute(f"ALTER TABLE mstVendor ADD COLUMN {col_name} {col_def}")
        added.append(col_name)
conn.commit()
print(f"mstVendor: added {', '.join(added) if added else '(none, already present)'}")

# ---------------- Default Quotation (per Business Partner, versioned) ----------------
cur.execute("""CREATE TABLE IF NOT EXISTS mstPartnerQuotation (
    QuotationID     INTEGER PRIMARY KEY AUTOINCREMENT,
    VendorID        INTEGER NOT NULL REFERENCES mstVendor(VendorID) ON DELETE CASCADE,
    VersionNumber   INTEGER NOT NULL DEFAULT 1,
    QuotationName   TEXT,
    IsActive        INTEGER NOT NULL DEFAULT 1,
    CreatedOn       TEXT NOT NULL DEFAULT (datetime('now'))
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS mstPartnerQuotationItem (
    ItemID          INTEGER PRIMARY KEY AUTOINCREMENT,
    QuotationID     INTEGER NOT NULL REFERENCES mstPartnerQuotation(QuotationID) ON DELETE CASCADE,
    ItemName        TEXT NOT NULL,
    Unit            TEXT NOT NULL DEFAULT 'Sq.ft',
    DefaultRate     REAL NOT NULL DEFAULT 0,
    Remarks         TEXT
)""")

# ---------------- Project Contract (snapshot, independent once created) ----------------
cur.execute("""CREATE TABLE IF NOT EXISTS trxContract (
    ContractID          INTEGER PRIMARY KEY AUTOINCREMENT,
    ProjectID           INTEGER NOT NULL REFERENCES tblProject(ProjectID) ON DELETE CASCADE,
    VendorID             INTEGER NOT NULL REFERENCES mstVendor(VendorID),
    SourceQuotationID    INTEGER REFERENCES mstPartnerQuotation(QuotationID),
    ContractType         TEXT NOT NULL DEFAULT 'Fixed',
    ContractAmount        REAL,
    Status                TEXT NOT NULL DEFAULT 'Active',
    CommissionType        TEXT,
    CommissionValue       REAL,
    Notes                 TEXT,
    CreatedOn             TEXT NOT NULL DEFAULT (datetime('now')),
    ModifiedOn            TEXT NOT NULL DEFAULT (datetime('now'))
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS trxContractItem (
    ContractItemID    INTEGER PRIMARY KEY AUTOINCREMENT,
    ContractID        INTEGER NOT NULL REFERENCES trxContract(ContractID) ON DELETE CASCADE,
    ItemName          TEXT NOT NULL,
    Unit              TEXT NOT NULL DEFAULT 'Sq.ft',
    Rate              REAL NOT NULL DEFAULT 0,
    DefaultRate       REAL,
    Quantity          REAL,
    Amount            REAL NOT NULL DEFAULT 0
)""")

# ---------------- Payment Ledger (additive, status computed) ----------------
cur.execute("""CREATE TABLE IF NOT EXISTS trxContractPayment (
    PaymentID      INTEGER PRIMARY KEY AUTOINCREMENT,
    ContractID     INTEGER NOT NULL REFERENCES trxContract(ContractID) ON DELETE CASCADE,
    PaymentDate    TEXT NOT NULL DEFAULT (date('now')),
    Amount         REAL NOT NULL,
    PaymentType    TEXT NOT NULL DEFAULT 'Partial',
    PaymentMode    TEXT,
    Notes          TEXT
)""")

# ---------------- Commission Ledger (multiple receipts) ----------------
cur.execute("""CREATE TABLE IF NOT EXISTS trxCommissionReceipt (
    ReceiptID      INTEGER PRIMARY KEY AUTOINCREMENT,
    ContractID     INTEGER NOT NULL REFERENCES trxContract(ContractID) ON DELETE CASCADE,
    ReceiptDate    TEXT NOT NULL DEFAULT (date('now')),
    Amount         REAL NOT NULL,
    Notes          TEXT
)""")

conn.commit()

cur.execute("""CREATE TABLE IF NOT EXISTS sysMigrationHistory (
    MigrationID INTEGER PRIMARY KEY AUTOINCREMENT,
    MigrationName TEXT UNIQUE NOT NULL,
    AppliedOn TEXT NOT NULL DEFAULT (datetime('now')),
    AppVersion TEXT
)""")
cur.execute("INSERT OR IGNORE INTO sysMigrationHistory (MigrationName) VALUES (?)", ("migrate_v390_contracts",))
conn.commit()

conn.close()
print("Migration complete: mstPartnerQuotation, mstPartnerQuotationItem, trxContract, trxContractItem, "
      "trxContractPayment, trxCommissionReceipt created. No existing data touched.")

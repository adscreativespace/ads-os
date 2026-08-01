"""
Standalone migration for v4.4.2 -- Business Partner Refinement + Board
Calculation. Two independent additions, bundled since both are small:

1. Default Scope of Work copying: trxContractScope mirrors the already-
   proven BR-002 pattern (Quotation -> Contract) -- a contract's Scope of
   Work is copied from the Business Partner's current scope at creation
   time, then can be edited per-project without touching the partner's
   master profile.

2. Board Calculation (BR-006): CalculationMethod + Length/Width/BoardQty on
   trxContractItem. Formula: Sq.ft = Length x Width x Quantity, confirmed
   and documented in BUSINESS_RULES.md. CalculationMethod on
   mstPartnerQuotationItem is a template hint only (no board dimensions
   there -- those are always real, project-specific site measurements
   entered at the contract level, never a "default").

Safe to run against a database with real data.

Usage: python migrate_v392_scope_and_board_calc.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS trxContractScope (
    ContractID   INTEGER NOT NULL REFERENCES trxContract(ContractID) ON DELETE CASCADE,
    ScopeID      INTEGER NOT NULL REFERENCES mstScopeOfWork(ScopeID) ON DELETE CASCADE,
    PRIMARY KEY (ContractID, ScopeID)
)""")
conn.commit()

new_item_columns = [
    ("CalculationMethod", "TEXT NOT NULL DEFAULT 'Direct'"),
    ("BoardLength", "REAL"),
    ("BoardWidth", "REAL"),
    ("BoardQty", "REAL"),
]
for table in ("trxContractItem", "mstPartnerQuotationItem"):
    cur.execute(f"PRAGMA table_info({table})")
    existing_cols = [r[1] for r in cur.fetchall()]
    added = []
    for col_name, col_def in new_item_columns:
        # Board dimensions only apply at the contract level (real site
        # measurements) -- the quotation template only needs the method hint.
        if table == "mstPartnerQuotationItem" and col_name != "CalculationMethod":
            continue
        if col_name not in existing_cols:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
            added.append(col_name)
    print(f"{table}: added {', '.join(added) if added else '(none, already present)'}")
conn.commit()

cur.execute("""CREATE TABLE IF NOT EXISTS sysMigrationHistory (
    MigrationID INTEGER PRIMARY KEY AUTOINCREMENT,
    MigrationName TEXT UNIQUE NOT NULL,
    AppliedOn TEXT NOT NULL DEFAULT (datetime('now')),
    AppVersion TEXT
)""")
cur.execute("INSERT OR IGNORE INTO sysMigrationHistory (MigrationName) VALUES (?)", ("migrate_v392_scope_and_board_calc",))
conn.commit()
conn.close()
print("Migration complete. No existing data touched.")

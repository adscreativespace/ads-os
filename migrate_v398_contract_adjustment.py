"""
Standalone migration: creates trxContractAdjustment.

Real gap this closes: the only way to change a Fixed contract's final
committed amount after it was set was "Edit Contract", which silently
overwrites ContractAmount with no record of what changed, by how much,
or why -- a real problem, since final amounts genuinely get negotiated
down (or up) after a contract starts (discount, scope change, rounding).

This table lets that change be recorded as its own dated, reasoned,
permanent row instead of erasing the original number. ContractAmount on
trxContract is left completely alone -- it keeps meaning "the amount
originally agreed." The contract's real, current committed amount is
now ContractAmount + SUM(trxContractAdjustment.Amount), computed by
get_contract_effective_amount() in contract_panel.py, which every
Outstanding/Status/commission calculation in this app now uses instead
of the raw ContractAmount.

Safe to run against a database with real data -- purely additive, no
existing table or column touched or renamed.

Usage: python migrate_v398_contract_adjustment.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS trxContractAdjustment (
    AdjustmentID    INTEGER PRIMARY KEY AUTOINCREMENT,
    ContractID      INTEGER NOT NULL REFERENCES trxContract(ContractID) ON DELETE CASCADE,
    AdjustmentDate  TEXT NOT NULL DEFAULT (date('now')),
    Amount          REAL NOT NULL,
    Reason          TEXT NOT NULL,
    CreatedOn       TEXT NOT NULL DEFAULT (datetime('now'))
)""")
print("Created trxContractAdjustment (or already existed) -- starts empty, no adjustment history invented.")
conn.commit()

cur.execute("""CREATE TABLE IF NOT EXISTS sysMigrationHistory (
    MigrationID INTEGER PRIMARY KEY AUTOINCREMENT,
    MigrationName TEXT UNIQUE NOT NULL,
    AppliedOn TEXT NOT NULL DEFAULT (datetime('now')),
    AppVersion TEXT
)""")
cur.execute("INSERT OR IGNORE INTO sysMigrationHistory (MigrationName) VALUES (?)", ("migrate_v398_contract_adjustment",))
conn.commit()
conn.close()
print("Done. No existing tables or data touched.")

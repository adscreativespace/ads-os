"""
Standalone migration for Materials, third of six Commercial modules.
Scoped to a materials master list with stock tracking and simple purchase
logging -- NOT the full Purchase Order -> Goods Receipt -> Stock Transfer ->
Return/Damage pipeline shown in the reference mockup, which is a genuinely
separate, larger procurement workflow deserving its own future build.

Safe to run against a database with real data -- only creates new tables.

Usage: python migrate_v320_materials.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS mstMaterial (
    MaterialID     INTEGER PRIMARY KEY AUTOINCREMENT,
    ProjectID      INTEGER NOT NULL REFERENCES tblProject(ProjectID) ON DELETE CASCADE,
    MaterialCode   TEXT UNIQUE,
    MaterialName   TEXT NOT NULL,
    Category       TEXT NOT NULL DEFAULT 'Uncategorized',
    Brand          TEXT,
    Unit           TEXT,
    UnitCost       REAL NOT NULL DEFAULT 0,
    CurrentStock   REAL NOT NULL DEFAULT 0,
    ReorderLevel   REAL NOT NULL DEFAULT 0,
    Location       TEXT,
    VendorID       INTEGER REFERENCES mstVendor(VendorID),
    Active         INTEGER NOT NULL DEFAULT 1,
    CreatedOn      TEXT NOT NULL DEFAULT (datetime('now')),
    ModifiedOn     TEXT NOT NULL DEFAULT (datetime('now'))
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS trxMaterialPurchase (
    PurchaseID    INTEGER PRIMARY KEY AUTOINCREMENT,
    MaterialID    INTEGER NOT NULL REFERENCES mstMaterial(MaterialID) ON DELETE CASCADE,
    Quantity      REAL NOT NULL,
    UnitCost      REAL NOT NULL,
    TotalCost     REAL NOT NULL,
    PurchaseDate  TEXT NOT NULL DEFAULT (datetime('now')),
    Notes         TEXT
)""")


# Self-register in the migration registry so "About ADS OS" correctly
# shows this migration as applied, instead of silently missing it.
cur.execute("""CREATE TABLE IF NOT EXISTS sysMigrationHistory (
    MigrationID INTEGER PRIMARY KEY AUTOINCREMENT,
    MigrationName TEXT UNIQUE NOT NULL,
    AppliedOn TEXT NOT NULL DEFAULT (datetime('now')),
    AppVersion TEXT
)""")
cur.execute("INSERT OR IGNORE INTO sysMigrationHistory (MigrationName) VALUES (?)", ("migrate_v320_materials",))

conn.commit()
conn.close()
print("Migration complete: mstMaterial and trxMaterialPurchase created.")
print("No existing tables or data were touched.")

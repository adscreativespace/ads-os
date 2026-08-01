"""
Standalone migration for the Fee Calculator (Commercial module, first of six).
Adds two new tables -- trxFeeCalculation (the saved calculation header) and
trxFeeCalculationItem (one row per service type applied). Safe to run against
a database with real data: only creates new tables, touches nothing existing.

Usage: python migrate_v300_fee_calculator.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS trxFeeCalculation (
    CalculationID       INTEGER PRIMARY KEY AUTOINCREMENT,
    ProjectID            INTEGER NOT NULL REFERENCES tblProject(ProjectID) ON DELETE CASCADE,
    CalculationName      TEXT NOT NULL,
    BuiltUpArea          REAL NOT NULL,
    AdditionalArea        REAL NOT NULL DEFAULT 0,
    DiscountPercent      REAL NOT NULL DEFAULT 0,
    AdditionalDiscount   REAL NOT NULL DEFAULT 0,
    GSTPercent           REAL NOT NULL DEFAULT 18,
    RoundingAdjustment   REAL NOT NULL DEFAULT 0,
    TotalFee              REAL NOT NULL DEFAULT 0,
    IsSaved              INTEGER NOT NULL DEFAULT 1,
    CreatedOn            TEXT NOT NULL DEFAULT (datetime('now')),
    ModifiedOn           TEXT NOT NULL DEFAULT (datetime('now'))
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS trxFeeCalculationItem (
    ItemID          INTEGER PRIMARY KEY AUTOINCREMENT,
    CalculationID   INTEGER NOT NULL REFERENCES trxFeeCalculation(CalculationID) ON DELETE CASCADE,
    ServiceID       INTEGER NOT NULL REFERENCES mstService(ServiceID),
    RatePerSqft     REAL NOT NULL DEFAULT 0,
    ScopePercent    REAL NOT NULL DEFAULT 100,
    Amount          REAL NOT NULL DEFAULT 0
)""")


# Self-register in the migration registry so "About ADS OS" correctly
# shows this migration as applied, instead of silently missing it.
cur.execute("""CREATE TABLE IF NOT EXISTS sysMigrationHistory (
    MigrationID INTEGER PRIMARY KEY AUTOINCREMENT,
    MigrationName TEXT UNIQUE NOT NULL,
    AppliedOn TEXT NOT NULL DEFAULT (datetime('now')),
    AppVersion TEXT
)""")
cur.execute("INSERT OR IGNORE INTO sysMigrationHistory (MigrationName) VALUES (?)", ("migrate_v300_fee_calculator",))

conn.commit()
conn.close()
print("Migration complete: trxFeeCalculation and trxFeeCalculationItem created.")
print("No existing tables or data were touched.")

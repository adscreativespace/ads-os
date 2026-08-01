"""
Standalone migration for Proposal Builder, the module completing the
Fee Calculation -> Proposal -> Invoice chain. Everything starts from a saved
Fee Calculation (module #1) -- no duplicate fee entry. Deliverables are
pulled from the REAL Package/Deliverable assembly logic built in Sprint 1
(get_assembled_package, mstDeliverable) -- not fabricated checkboxes.

RevisionNo is included from day one so version history can be added later
without a schema redesign, even though full version-comparison UI is not
built in this pass.

Safe to run against a database with real data -- only creates new tables.

Usage: python migrate_v350_proposals.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS trxProposal (
    ProposalID       INTEGER PRIMARY KEY AUTOINCREMENT,
    ProjectID        INTEGER NOT NULL REFERENCES tblProject(ProjectID) ON DELETE CASCADE,
    CalculationID    INTEGER REFERENCES trxFeeCalculation(CalculationID),
    ProposalNo       TEXT UNIQUE NOT NULL,
    ProposalDate     TEXT NOT NULL DEFAULT (date('now')),
    ValidTill        TEXT,
    RevisionNo       INTEGER NOT NULL DEFAULT 0,
    Status           TEXT NOT NULL DEFAULT 'Draft',
    CoverLetter      TEXT,
    ScopeOfWork      TEXT,
    TermsConditions  TEXT,
    CreatedOn        TEXT NOT NULL DEFAULT (datetime('now')),
    ModifiedOn       TEXT NOT NULL DEFAULT (datetime('now'))
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS trxProposalPaymentTerm (
    TermID       INTEGER PRIMARY KEY AUTOINCREMENT,
    ProposalID   INTEGER NOT NULL REFERENCES trxProposal(ProposalID) ON DELETE CASCADE,
    StageName    TEXT NOT NULL,
    Percent      REAL NOT NULL DEFAULT 0,
    StageOrder   INTEGER NOT NULL DEFAULT 0
)""")


# Self-register in the migration registry so "About ADS OS" correctly
# shows this migration as applied, instead of silently missing it.
cur.execute("""CREATE TABLE IF NOT EXISTS sysMigrationHistory (
    MigrationID INTEGER PRIMARY KEY AUTOINCREMENT,
    MigrationName TEXT UNIQUE NOT NULL,
    AppliedOn TEXT NOT NULL DEFAULT (datetime('now')),
    AppVersion TEXT
)""")
cur.execute("INSERT OR IGNORE INTO sysMigrationHistory (MigrationName) VALUES (?)", ("migrate_v350_proposals",))

conn.commit()
conn.close()
print("Migration complete: trxProposal and trxProposalPaymentTerm created.")
print("No existing tables or data were touched.")

"""
Standalone migration for v4.4.3 -- adds PackageID to trxProposal.
Fixes a confirmed, reproducible correctness bug: proposals were reading the
PROJECT's live DefaultPackageID instead of snapshotting which package was
actually selected at creation time -- exactly the same "copy, don't
reference live" problem BR-002 already solved for quotations. If a
project's package changed after a proposal was created, reprinting that
proposal would silently show a different package's deliverables than what
the client actually received.

Nullable and additive -- existing proposals get PackageID=NULL (no way to
know retroactively what package they were actually created with); the PDF
generator falls back to the project's current package for those specific
legacy rows only, with the gap visible rather than silently guessed at.

Safe to run against a database with real data.

Usage: python migrate_v393_proposal_package_snapshot.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("PRAGMA table_info(trxProposal)")
existing_cols = [r[1] for r in cur.fetchall()]
if "PackageID" not in existing_cols:
    cur.execute("ALTER TABLE trxProposal ADD COLUMN PackageID INTEGER REFERENCES mstPackage(PackageID)")
    print("Added trxProposal.PackageID")
else:
    print("trxProposal.PackageID already exists")
conn.commit()

cur.execute("""CREATE TABLE IF NOT EXISTS sysMigrationHistory (
    MigrationID INTEGER PRIMARY KEY AUTOINCREMENT,
    MigrationName TEXT UNIQUE NOT NULL,
    AppliedOn TEXT NOT NULL DEFAULT (datetime('now')),
    AppVersion TEXT
)""")
cur.execute("INSERT OR IGNORE INTO sysMigrationHistory (MigrationName) VALUES (?)", ("migrate_v393_proposal_package_snapshot",))
conn.commit()
conn.close()
print("Migration complete. Existing proposals have PackageID=NULL (no retroactive fix possible -- "
      "the PDF generator falls back to the project's current package for these specific legacy rows).")

"""
Standalone migration: adds tblClient.NextFollowUpDate.

A genuinely new concept -- no follow-up/reminder tracking exists anywhere
in this app currently. Added as a real, nullable field rather than
fabricated: every existing client starts with NextFollowUpDate=NULL (shown
as "-" in the UI), and only gets a real value once Atish actually sets one
for a real client going forward. Nothing here invents a date for any
existing client.

Safe to run against a database with real data -- purely additive, no
existing column touched, no row's other data altered.

Usage: python migrate_v395_client_followup.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("PRAGMA table_info(tblClient)")
existing_cols = [r[1] for r in cur.fetchall()]
if "NextFollowUpDate" not in existing_cols:
    cur.execute("ALTER TABLE tblClient ADD COLUMN NextFollowUpDate TEXT")
    print("Added tblClient.NextFollowUpDate (nullable -- every existing client starts unset, not fabricated)")
else:
    print("tblClient.NextFollowUpDate already exists")
conn.commit()

cur.execute("""CREATE TABLE IF NOT EXISTS sysMigrationHistory (
    MigrationID INTEGER PRIMARY KEY AUTOINCREMENT,
    MigrationName TEXT UNIQUE NOT NULL,
    AppliedOn TEXT NOT NULL DEFAULT (datetime('now')),
    AppVersion TEXT
)""")
cur.execute("INSERT OR IGNORE INTO sysMigrationHistory (MigrationName) VALUES (?)", ("migrate_v395_client_followup",))
conn.commit()
conn.close()
print("Done.")

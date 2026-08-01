"""
Standalone migration for v0.8.0's Lead Source table.
Safe to run against a database with real clients/projects -- only adds the
new table and seeds defaults; never touches existing rows.

Usage: python migrate_v080_lead_source.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS mstLeadSource (
    SourceID INTEGER PRIMARY KEY AUTOINCREMENT,
    SourceName TEXT UNIQUE NOT NULL,
    Active INTEGER NOT NULL DEFAULT 1
)""")

sources = ["Instagram", "Facebook", "Google", "Website", "Referral", "Walk-in", "WhatsApp",
           "JustDial", "LinkedIn", "Architect", "Contractor", "Existing Client", "Other"]
for s in sources:
    cur.execute("INSERT OR IGNORE INTO mstLeadSource (SourceName) VALUES (?)", (s,))

conn.commit()

# If any existing clients have a Source value not yet in the list (e.g. a custom
# one entered before this table existed), add it so it isn't lost from the dropdown
cur.execute("SELECT DISTINCT Source FROM tblClient WHERE Source IS NOT NULL AND Source != ''")
existing_sources = [r[0] for r in cur.fetchall()]
added = []
for s in existing_sources:
    cur.execute("INSERT OR IGNORE INTO mstLeadSource (SourceName) VALUES (?)", (s,))
    if cur.rowcount:
        added.append(s)
conn.commit()

cur.execute("SELECT SourceName FROM mstLeadSource ORDER BY SourceID")
print("Lead sources now available:", [r[0] for r in cur.fetchall()])
if added:
    print("Preserved existing custom source(s) found in your client data:", added)

conn.close()
print("\nMigration complete. Existing clients, projects, and all other data are untouched.")

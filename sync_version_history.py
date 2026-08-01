"""
Syncs the in-app version history (Settings > click version number) to match
version.py's CHANGELOG. Only touches the sysVersion table -- pure metadata
about what each version changed, not your client/project data. Safe to run
anytime; does not read or modify tblClient, tblProject, or any other table.
"""
import sqlite3
import os
from version import CHANGELOG

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("DELETE FROM sysVersion")
for ver, notes in CHANGELOG:
    cur.execute("INSERT INTO sysVersion (VersionNumber, Notes) VALUES (?,?)", (ver, notes))
conn.commit()
conn.close()
print(f"Synced {len(CHANGELOG)} version entries. Client/Project data untouched.")

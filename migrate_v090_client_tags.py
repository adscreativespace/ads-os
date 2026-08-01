"""
Standalone migration for v0.9.0's Client Tags feature.
Safe to run against a database with real clients -- only adds new tables and
seeds default tags; never touches existing client/project data.

Usage: python migrate_v090_client_tags.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS mstClientTag (
    TagID INTEGER PRIMARY KEY AUTOINCREMENT,
    TagName TEXT UNIQUE NOT NULL,
    Active INTEGER NOT NULL DEFAULT 1
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS tblClientTagLink (
    LinkID INTEGER PRIMARY KEY AUTOINCREMENT,
    ClientID INTEGER NOT NULL REFERENCES tblClient(ClientID) ON DELETE CASCADE,
    TagID INTEGER NOT NULL REFERENCES mstClientTag(TagID) ON DELETE CASCADE,
    UNIQUE(ClientID, TagID)
)""")

tags = ["VIP", "Repeat Client", "Builder", "Developer", "Government", "Hospital",
        "Interior", "Architecture", "High Priority", "International"]
for t in tags:
    cur.execute("INSERT OR IGNORE INTO mstClientTag (TagName) VALUES (?)", (t,))

conn.commit()
cur.execute("SELECT TagName FROM mstClientTag ORDER BY TagID")
print("Tags available:", [r[0] for r in cur.fetchall()])
conn.close()
print("\nMigration complete. Existing clients, projects, and all other data are untouched.")

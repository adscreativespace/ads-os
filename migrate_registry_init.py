"""
Migration Registry -- initializes sysMigrationHistory and backfills it with
every migration shipped so far, on the assumption they've been applied in
order (matches the sequence of hand-off prompts this session). This is a
reasonable assumption, not a certainty -- if you skipped any migration along
the way, this backfill would be wrong for that one entry. Worth a quick sanity
check: open the app's "About ADS OS" panel afterward and confirm nothing
looks obviously wrong (e.g. a feature you know isn't there being listed as
applied).

From this point forward, every NEW migration script self-registers when it
runs successfully -- no more backfilling needed after this one.

Safe to run against a database with real data -- only adds the new registry
table and rows describing which migrations ran; never touches client/project
data.

Usage: python migrate_registry_init.py
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

# In the order they were actually shipped this session
MIGRATIONS_IN_ORDER = [
    ("migrate_packages", "0.4.0 (backfilled -- original run date not tracked, this predates the registry itself)"),
    ("migrate_v061_floor_fields", "0.6.1"),
    ("migrate_v080_lead_source", "0.8.0"),
    ("migrate_v090_client_tags", "0.9.0"),
    ("migrate_space_library_v2", "1.1.0"),
    ("migrate_v120_floor_usage", "1.2.0"),
    ("migrate_common_spaces", "1.4.0"),
    ("migrate_sector_service_split", "2.0.0"),
    ("migrate_v270_floor_default_height", "2.7.0"),
    ("migrate_v280_future_proofing", "2.8.0"),
]

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS sysMigrationHistory (
    MigrationID INTEGER PRIMARY KEY AUTOINCREMENT,
    MigrationName TEXT UNIQUE NOT NULL,
    AppliedOn TEXT NOT NULL DEFAULT (datetime('now')),
    AppVersion TEXT
)""")
conn.commit()

registered = 0
for name, app_version in MIGRATIONS_IN_ORDER:
    cur.execute("INSERT OR IGNORE INTO sysMigrationHistory (MigrationName, AppVersion) VALUES (?,?)",
                (name, app_version))
    if cur.rowcount:
        registered += 1
conn.commit()

cur.execute("SELECT MigrationName, AppVersion, AppliedOn FROM sysMigrationHistory ORDER BY MigrationID")
print(f"Registered {registered} migration(s) as applied (backfilled). Full registry now:")
for name, ver, applied in cur.fetchall():
    print(f"  {name} (v{ver}) -- {applied}")

conn.close()
print("\nFrom here on, new migrations self-register automatically -- no more backfilling.")

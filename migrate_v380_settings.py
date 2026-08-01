"""
Standalone migration for v4.2 -- Current Project infrastructure.
Adds a generic key-value settings table (for persisting current_project_id
across app restarts, and reusable for any future setting) and nothing else.
No business logic tables touched, no existing data affected.

Safe to run against a database with real data.

Usage: python migrate_v380_settings.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS sysSettings (
    SettingKey    TEXT PRIMARY KEY,
    SettingValue  TEXT,
    ModifiedOn    TEXT NOT NULL DEFAULT (datetime('now'))
)""")
conn.commit()

cur.execute("""CREATE TABLE IF NOT EXISTS sysMigrationHistory (
    MigrationID INTEGER PRIMARY KEY AUTOINCREMENT,
    MigrationName TEXT UNIQUE NOT NULL,
    AppliedOn TEXT NOT NULL DEFAULT (datetime('now')),
    AppVersion TEXT
)""")
cur.execute("INSERT OR IGNORE INTO sysMigrationHistory (MigrationName) VALUES (?)", ("migrate_v380_settings",))
conn.commit()

conn.close()
print("Migration complete: sysSettings created. No existing data touched.")

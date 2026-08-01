"""
ADS OS -- Database Health Check
Runs concrete, verifiable checks against the live database: SQLite integrity,
foreign key consistency, orphaned records, duplicate codes, migration status,
and backup recency. Returns a structured result the UI can render, rather than
a fake "score" -- every item here is something genuinely checkable, not
gamified.
"""
import os
import sqlite3
import glob
from datetime import datetime, timedelta

import db
import version

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(BASE_DIR, "Backups")


def run_health_check():
    """Returns a list of (check_name, status, detail) tuples. status is 'ok', 'warning', or 'error'."""
    results = []

    # ---------------- SQLite integrity ----------------
    conn = sqlite3.connect(db.DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA integrity_check")
    integrity = cur.fetchone()[0]
    if integrity == "ok":
        results.append(("SQLite Integrity", "ok", "No corruption detected."))
    else:
        results.append(("SQLite Integrity", "error", integrity))

    # ---------------- Foreign key consistency ----------------
    cur.execute("PRAGMA foreign_key_check")
    fk_violations = cur.fetchall()
    if not fk_violations:
        results.append(("Foreign Key Consistency", "ok", "No orphaned references found."))
    else:
        results.append(("Foreign Key Consistency", "error",
                        f"{len(fk_violations)} foreign key violation(s) found -- data integrity is compromised."))
    conn.close()

    # ---------------- Migration status ----------------
    applied = db.get_applied_migrations()
    expected = set(version.EXPECTED_MIGRATIONS)
    missing = expected - applied
    if not missing:
        results.append(("Migrations", "ok", f"All {len(expected)} expected migrations applied."))
    else:
        results.append(("Migrations", "warning",
                        f"Missing: {', '.join(sorted(missing))}"))

    # ---------------- Orphaned records (belt-and-suspenders beyond FK check) ----------------
    orphan_floors = db.fetch_one("""
        SELECT COUNT(*) AS n FROM tblFloor f
        WHERE NOT EXISTS (SELECT 1 FROM tblProject p WHERE p.ProjectID = f.ProjectID)
    """)["n"]
    orphan_spaces = db.fetch_one("""
        SELECT COUNT(*) AS n FROM tblRoom r
        WHERE NOT EXISTS (SELECT 1 FROM tblFloor f WHERE f.FloorID = r.FloorID)
    """)["n"]
    if orphan_floors == 0 and orphan_spaces == 0:
        results.append(("Orphaned Records", "ok", "No floors or spaces reference a missing parent."))
    else:
        results.append(("Orphaned Records", "warning",
                        f"{orphan_floors} orphaned floor(s), {orphan_spaces} orphaned space(s)."))

    # ---------------- Duplicate codes ----------------
    dup_clients = db.fetch_all(
        "SELECT ClientCode, COUNT(*) AS n FROM tblClient GROUP BY ClientCode HAVING n > 1")
    dup_projects = db.fetch_all(
        "SELECT ProjectCode, COUNT(*) AS n FROM tblProject GROUP BY ProjectCode HAVING n > 1")
    if not dup_clients and not dup_projects:
        results.append(("Duplicate Codes", "ok", "All Client and Project codes are unique."))
    else:
        details = []
        if dup_clients:
            details.append(f"{len(dup_clients)} duplicate Client Code(s)")
        if dup_projects:
            details.append(f"{len(dup_projects)} duplicate Project Code(s)")
        results.append(("Duplicate Codes", "error", ", ".join(details)))

    # ---------------- Backup recency ----------------
    if os.path.exists(BACKUP_DIR):
        backups = sorted(glob.glob(os.path.join(BACKUP_DIR, "ads_office_suite_*.db")))
        if backups:
            latest = backups[-1]
            mtime = datetime.fromtimestamp(os.path.getmtime(latest))
            age = datetime.now() - mtime
            if age < timedelta(days=7):
                results.append(("Backup Recency", "ok", f"Most recent backup: {mtime.strftime('%d %b %Y, %I:%M %p')}"))
            else:
                results.append(("Backup Recency", "warning",
                                f"Most recent backup is {age.days} day(s) old ({mtime.strftime('%d %b %Y')}). "
                                f"Consider running backup_database.py."))
        else:
            results.append(("Backup Recency", "warning", "No backups found. Run backup_database.py."))
    else:
        results.append(("Backup Recency", "warning", "Backups folder doesn't exist yet. Run backup_database.py."))

    return results

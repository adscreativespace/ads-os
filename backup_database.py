"""
ADS OS -- Database Backup
Copies ads_office_suite.db to a timestamped file in a Backups folder.
Never modifies the original -- purely a safety copy.

Usage: python backup_database.py
Recommended: run this before applying any update, and occasionally otherwise
(e.g. once a week).
"""
import shutil
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "ads_office_suite.db")
BACKUP_DIR = os.path.join(BASE_DIR, "Backups")


def backup():
    if not os.path.exists(DB_PATH):
        print(f"No database found at {DB_PATH} -- nothing to back up.")
        return

    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"ads_office_suite_{timestamp}.db")

    shutil.copy2(DB_PATH, backup_path)
    size_kb = os.path.getsize(backup_path) / 1024

    print(f"Backup created: {backup_path}")
    print(f"Size: {size_kb:.1f} KB")

    # Keep the last 20 backups only, so this folder doesn't grow forever
    all_backups = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.startswith("ads_office_suite_") and f.endswith(".db")]
    )
    if len(all_backups) > 20:
        for old_backup in all_backups[:-20]:
            os.remove(os.path.join(BACKUP_DIR, old_backup))
        print(f"Removed {len(all_backups) - 20} old backup(s), keeping the most recent 20.")


if __name__ == "__main__":
    backup()
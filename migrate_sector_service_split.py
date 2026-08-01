"""
Decision 017 -- Sector / Service Split Migration
Fixes a real data normalization issue: mstProjectType mixed "what the project
IS" (Residential, Airport, Healthcare -- a Sector) with "what we're doing"
(Interior Design, Renovation -- a Service) in one flat list. Confirmed by
inspection: 18 of the 20 existing rows are genuine sectors; "Interior Design"
and "Renovation" are services that were incorrectly living in the same list.

This migration:
  1. Creates mstSector and mstService as separate master tables.
  2. Seeds mstSector from the 18 genuine sector rows already in mstProjectType.
  3. Seeds mstService with a starter list (Architectural Design, Interior
     Design, Renovation, etc.) from Decision 017.
  4. Adds SectorID/ServiceID to tblProject (new columns, nullable).
  5. Adds SectorID to mstRoomLibrary (the Space Library is sector-based --
     what spaces exist depends on Residential vs Healthcare, not on which
     service you're providing).
  6. Backfills SectorID everywhere from the old ProjectTypeID via name
     matching, so nothing breaks for any project/space created before this.

Old mstProjectType / ProjectTypeID columns are left in place (deprecated, not
dropped) rather than risking a full table rebuild in SQLite. No app code
should write to ProjectTypeID going forward -- SectorID/ServiceID replace it.

Safe to re-run.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

# The 18 rows that are genuinely sectors (excludes Interior Design, Renovation)
SECTOR_NAMES = [
    "Residential", "Commercial", "Office", "Retail / Showroom", "Restaurant / Café",
    "Hospitality", "Healthcare", "Educational", "Industrial", "Government", "Airport",
    "Infrastructure", "Mixed Use", "Landscape", "Master Planning", "Religious",
    "Sports", "Entertainment",
]

SERVICE_NAMES = [
    "Architectural Design", "Interior Design", "Landscape Design", "Renovation",
    "Planning Consultancy", "Structural Consultancy", "MEP Consultancy",
    "Project Management Consultancy (PMC)", "Turnkey Interior", "Design & Build",
    "Quantity Surveying", "BOQ & Estimation", "Working Drawings", "3D Visualization",
    "Construction Supervision", "Approval Drawings", "Tender Documentation",
]


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS mstSector (
        SectorID INTEGER PRIMARY KEY AUTOINCREMENT,
        SectorName TEXT UNIQUE NOT NULL,
        Active INTEGER NOT NULL DEFAULT 1
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS mstService (
        ServiceID INTEGER PRIMARY KEY AUTOINCREMENT,
        ServiceName TEXT UNIQUE NOT NULL,
        Active INTEGER NOT NULL DEFAULT 1
    )""")
    conn.commit()

    for name in SECTOR_NAMES:
        cur.execute("INSERT OR IGNORE INTO mstSector (SectorName) VALUES (?)", (name,))
    for name in SERVICE_NAMES:
        cur.execute("INSERT OR IGNORE INTO mstService (ServiceName) VALUES (?)", (name,))
    conn.commit()

    # tblProject: add SectorID, ServiceID
    cur.execute("PRAGMA table_info(tblProject)")
    cols = [r[1] for r in cur.fetchall()]
    if "SectorID" not in cols:
        cur.execute("ALTER TABLE tblProject ADD COLUMN SectorID INTEGER REFERENCES mstSector(SectorID)")
    if "ServiceID" not in cols:
        cur.execute("ALTER TABLE tblProject ADD COLUMN ServiceID INTEGER REFERENCES mstService(ServiceID)")
    conn.commit()

    # mstRoomLibrary: add SectorID (the Space Library is sector-based)
    cur.execute("PRAGMA table_info(mstRoomLibrary)")
    cols = [r[1] for r in cur.fetchall()]
    if "SectorID" not in cols:
        cur.execute("ALTER TABLE mstRoomLibrary ADD COLUMN SectorID INTEGER REFERENCES mstSector(SectorID)")
    conn.commit()

    # Backfill: for every old ProjectTypeID that matches a real Sector name,
    # set the new SectorID accordingly. Rows under "Interior Design"/"Renovation"
    # (if any ever existed -- confirmed none do for Space Library) are left
    # with SectorID NULL since those aren't sectors.
    cur.execute("SELECT ProjectTypeID, ProjectType FROM mstProjectType")
    old_types = cur.fetchall()
    name_to_sector_id = {}
    for sid, sname in cur.execute("SELECT SectorID, SectorName FROM mstSector").fetchall():
        name_to_sector_id[sname] = sid

    backfilled_projects = 0
    backfilled_library = 0
    for old_id, old_name in old_types:
        new_sector_id = name_to_sector_id.get(old_name)
        if not new_sector_id:
            continue  # Interior Design / Renovation -- not a sector, skip
        cur.execute("UPDATE tblProject SET SectorID=? WHERE ProjectTypeID=? AND SectorID IS NULL", (new_sector_id, old_id))
        backfilled_projects += cur.rowcount
        cur.execute("UPDATE mstRoomLibrary SET SectorID=? WHERE ProjectTypeID=? AND SectorID IS NULL", (new_sector_id, old_id))
        backfilled_library += cur.rowcount
    conn.commit()

    # tblFloor.FloorUsage stores a name (was a ProjectType name) -- no schema
    # change needed, but note it now conceptually stores a Sector name.

    print(f"mstSector: {len(SECTOR_NAMES)} sectors seeded")
    print(f"mstService: {len(SERVICE_NAMES)} services seeded")
    print(f"Backfilled SectorID on {backfilled_projects} existing project(s)")
    print(f"Backfilled SectorID on {backfilled_library} existing Space Library row(s)")

    conn.close()
    print("\nMigration complete. Old mstProjectType/ProjectTypeID data is untouched (deprecated, not deleted).")


if __name__ == "__main__":
    migrate()

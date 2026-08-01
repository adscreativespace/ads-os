"""
Marks the 'most common' spaces per project type -- used to build a short,
manageable checklist in the Add Space dialog instead of showing the full
100+ item library. Full library remains accessible via 'Show Full Library'.

Curated fully for Residential and Commercial (your most active project
types). Other project types get a smaller best-effort common set; if a type
has zero common-flagged spaces, the Add Space dialog falls back to showing
its full library so nothing is ever empty.

Safe to re-run.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

COMMON_SPACES = {
    "Residential": [
        "Living Room", "Family Living", "Dining Room", "Kitchen", "Open Kitchen", "Utility",
        "Master Bedroom", "Bedroom", "Guest Bedroom", "Kids Bedroom",
        "Attached Toilet", "Common Toilet", "Powder Toilet",
        "Balcony", "Terrace", "Study Room", "Home Office", "Walk-In Closet",
        "Staircase", "Store", "Pooja Room",
    ],
    "Commercial": [
        "Reception", "Open Office", "Workstation", "Cabin", "Meeting Room", "Conference Room",
        "Pantry", "Store", "Server Room", "Toilet", "Staircase", "Lift Lobby",
    ],
    "Office": [
        "Reception", "Open Office", "Workstation", "Manager Cabin", "Meeting Room", "Conference Room",
        "Board Room", "Pantry", "Café", "Server Room", "Toilets", "Staircase", "Lift Lobby",
    ],
    "Retail / Showroom": [
        "Display Area", "Billing Counter", "Trial Room", "Store", "Stock Room", "Manager Cabin",
        "Customer Lounge",
    ],
    "Healthcare": [
        "Reception", "Waiting", "Consultation Room", "OPD", "Examination Room", "General Ward",
        "Private Room", "ICU", "Nurses Station", "Pharmacy", "Laboratory", "Doctors Room",
    ],
    "Hospitality": [
        "Lobby", "Reception", "Standard Room", "Deluxe Room", "Suite", "Restaurant", "Café",
        "Bar", "Banquet", "Main Kitchen", "Gym", "Pool",
    ],
    "Educational": [
        "Reception", "Classroom", "Smart Classroom", "Laboratory", "Library", "Staff Room",
        "Auditorium", "Principal",
    ],
    "Airport": [
        "Departure Hall", "Arrival Hall", "Check-in", "Security Check", "Boarding Gate",
        "Baggage Claim", "Retail Shop", "Food Court", "VIP Lounge",
    ],
}


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    marked = 0
    for pt_name, spaces in COMMON_SPACES.items():
        cur.execute("SELECT ProjectTypeID FROM mstProjectType WHERE ProjectType=?", (pt_name,))
        row = cur.fetchone()
        if not row:
            print(f"WARNING: '{pt_name}' not found, skipping")
            continue
        pt_id = row[0]
        for space_name in spaces:
            cur.execute(
                "UPDATE mstRoomLibrary SET IsCommon=1 WHERE ProjectTypeID=? AND RoomName=?",
                (pt_id, space_name)
            )
            if cur.rowcount:
                marked += 1
            else:
                print(f"  Note: '{space_name}' not found in {pt_name} library, skipped")
    conn.commit()
    print(f"\nMarked {marked} spaces as common.")

    cur.execute("""
        SELECT pt.ProjectType, COUNT(*) as n FROM mstRoomLibrary rl
        JOIN mstProjectType pt ON rl.ProjectTypeID = pt.ProjectTypeID
        WHERE rl.IsCommon=1 GROUP BY pt.ProjectType
    """)
    print("\nCommon spaces per type:")
    for pt_name, n in cur.fetchall():
        print(f"  {pt_name}: {n}")
    conn.close()


if __name__ == "__main__":
    migrate()

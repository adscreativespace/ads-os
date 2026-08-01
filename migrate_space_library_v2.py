"""
Master Space Library seed -- Version 1.0
Fills in the Space Library for every project type. Previously only Residential
(21 spaces) and Commercial (17 spaces) had any data; every other project type
(Office, Retail, Healthcare, Hospitality, Educational, Industrial, Airport,
Infrastructure, Landscape) was completely empty, which is why "+ Create Custom
Space" was the only option when adding a space to those project types.

This is standard architectural terminology (ICU, Reception, Nursing Station),
not ADS-specific business/vendor data -- safe to seed with confidence, unlike
a Materials/Furniture library which would need your actual product/vendor
choices to be genuinely useful rather than generic placeholders.

Safe to re-run: uses INSERT OR IGNORE against the existing
UNIQUE(ProjectTypeID, RoomName) constraint, so it never duplicates or
overwrites anything already there.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")

# project_type_name -> [(category, [space names]), ...]
SPACE_LIBRARY = {
    "Residential": [
        ("Entrance & Circulation", ["Entrance Gate", "Front Porch", "Foyer", "Entrance Lobby", "Passage",
                                     "Corridor", "Staircase", "Lift Lobby", "Lift", "Ramp"]),
        ("Living", ["Family Living", "Drawing Room", "Formal Lounge", "Informal Lounge", "TV Lounge"]),
        ("Dining", ["Dining Room", "Breakfast Area"]),
        ("Kitchen", ["Open Kitchen", "Closed Kitchen", "Dirty Kitchen", "Dry Kitchen", "Wet Kitchen", "Island Kitchen"]),
        ("Bedrooms", ["Guest Bedroom", "Kids Bedroom", "Parents Bedroom", "Elder Bedroom", "Nursery", "Servant Room"]),
        ("Dressing", ["Walk-In Closet", "Dressing Room", "Vanity Area"]),
        ("Study & Work", ["Study Room", "Home Office", "Library", "Reading Room"]),
        ("Entertainment", ["Home Theatre", "Gaming Room", "Music Room", "Bar Lounge", "Recreation Room"]),
        ("Wellness", ["Gym", "Yoga Room", "Meditation Room", "Prayer Room", "Spa", "Sauna", "Steam Room"]),
        ("Toilets", ["Powder Toilet", "Accessible Toilet"]),
        ("Service", ["Linen Room", "Inverter Room", "Generator Room", "Security Room"]),
        ("Outdoor", ["Courtyard", "Verandah", "Patio", "Deck", "Garden", "Gazebo", "Swimming Pool", "Pool Deck"]),
        ("Parking", ["Two Wheeler Parking", "EV Charging", "Driver Room"]),
        ("Complex Amenities", ["Apartment Lobby", "Common Corridor", "Refuge Area", "Club House", "Community Hall",
                                "Indoor Games", "Outdoor Games", "Yoga Hall", "Kids Play Area", "Jogging Track",
                                "Landscape Garden", "Security Cabin", "Society Office", "Maintenance Office",
                                "Fire Pump Room", "STP", "WTP", "Transformer Yard"]),
    ],
    "Office": [
        ("Reception", ["Reception", "Waiting Lounge"]),
        ("Office", ["Open Office", "Workstation", "Cubicle", "Hot Desk"]),
        ("Cabins", ["CEO Cabin", "Director Cabin", "Partner Cabin", "Manager Cabin", "Executive Cabin"]),
        ("Meetings", ["Meeting Room", "Conference Room", "Board Room", "Interview Room", "Discussion Room"]),
        ("Staff", ["HR", "Accounts", "Finance", "Admin", "Legal", "IT Department"]),
        ("Support", ["Pantry", "Café", "Printing Room", "Record Room", "Store"]),
        ("Technical", ["Server Room", "UPS Room", "Electrical Room", "AHU Room"]),
        ("Utilities", ["Toilets", "Accessible Toilet", "Staircase", "Lift Lobby"]),
    ],
    "Retail / Showroom": [
        ("Sales", ["Display Area", "Product Display", "Billing Counter", "Cash Counter", "Customer Lounge", "Trial Room"]),
        ("Back of House", ["Store", "Stock Room", "Packing Area", "Manager Cabin", "Office", "Pantry",
                            "Loading Area", "Delivery Area"]),
    ],
    "Healthcare": [
        ("Public", ["Reception", "Registration", "Waiting", "Billing", "Help Desk"]),
        ("Clinical", ["Consultation Room", "OPD", "Examination Room", "Treatment Room", "Injection Room", "Dressing Room"]),
        ("Emergency", ["Emergency", "Trauma Bay", "Triage"]),
        ("Surgery", ["Minor OT", "Major OT", "Modular OT", "Scrub Area", "Sterile Store", "CSSD", "Recovery Room"]),
        ("Diagnostics", ["Laboratory", "Blood Collection", "Pathology", "MRI", "CT Scan", "X-Ray", "Ultrasound", "ECG", "EEG"]),
        ("Inpatient", ["General Ward", "Private Room", "Deluxe Room", "ICU", "NICU", "PICU", "HDU", "Isolation Room"]),
        ("Staff", ["Doctors Room", "Duty Doctor", "Nurses Station", "Staff Lounge", "Staff Changing", "Conference Room"]),
        ("Pharmacy", ["Pharmacy", "Drug Store"]),
        ("Support", ["Biomedical Store", "Linen", "Housekeeping", "Waste Room", "Mortuary"]),
        ("Services", ["Electrical", "AHU", "Medical Gas", "Pump Room", "Generator"]),
    ],
    "Hospitality": [
        ("Front Office", ["Lobby", "Reception", "Waiting Lounge", "Concierge"]),
        ("Accommodation", ["Standard Room", "Deluxe Room", "Executive Room", "Suite", "Presidential Suite",
                            "Family Suite", "Dormitory"]),
        ("Dining", ["Restaurant", "Café", "Coffee Shop", "Bar", "Lounge", "Banquet"]),
        ("Kitchen", ["Main Kitchen", "Pantry", "Bakery", "Cold Kitchen", "Hot Kitchen", "Dish Wash"]),
        ("Recreation", ["Gym", "Spa", "Pool", "Salon", "Kids Play Room"]),
        ("Service", ["Laundry", "Housekeeping", "Linen", "Store"]),
    ],
    "Educational": [
        ("General", ["Reception", "Principal", "Vice Principal", "Office"]),
        ("Academic", ["Classroom", "Smart Classroom", "Laboratory", "Physics Lab", "Chemistry Lab", "Biology Lab",
                      "Computer Lab", "Language Lab"]),
        ("Library & Assembly", ["Library", "Reading Hall", "Auditorium", "Seminar Hall", "Staff Room"]),
        ("Residential & Dining", ["Hostel Room", "Dining Hall", "Kitchen"]),
        ("Recreation", ["Sports Room", "Playground"]),
    ],
    "Industrial": [
        ("Production", ["Production", "Assembly", "Manufacturing", "Packaging"]),
        ("Storage", ["Raw Material Store", "Finished Goods Store"]),
        ("Quality & Dispatch", ["Quality Control", "Testing Lab", "Dispatch", "Loading Dock"]),
        ("Utilities", ["Boiler", "DG Room", "Compressor Room", "Utility Room"]),
        ("Support", ["Security", "Parking"]),
    ],
    "Airport": [
        ("Passenger", ["Departure Hall", "Arrival Hall", "Check-in", "Security Check", "Immigration", "Customs",
                       "Boarding Gate", "Baggage Claim", "Transfer Lounge"]),
        ("VIP", ["VIP Lounge", "Business Lounge", "Airline Lounge"]),
        ("Retail", ["Duty Free", "Retail Shop", "Food Court", "Restaurant", "Prayer Room"]),
        ("Operations", ["ATC", "Airline Office", "Baggage Handling", "Security Office", "Fire Station"]),
    ],
    "Religious": [
        ("Worship", ["Main Prayer Hall", "Sanctum", "Meditation Hall"]),
        ("Community", ["Community Hall", "Kitchen", "Dining Hall", "Priest Room"]),
        ("Support", ["Store", "Library", "Office", "Donation Counter", "Shoe Rack Area", "Wash Area"]),
    ],
    "Sports": [
        ("Playing Areas", ["Stadium", "Arena", "Indoor Court", "Swimming Pool"]),
        ("Fitness", ["Gym", "Fitness Area"]),
        ("Support", ["Locker Room", "Coaches Room", "Medical Room", "Equipment Store", "Spectator Seating", "VIP Lounge"]),
    ],
    "Entertainment": [
        ("Performance", ["Cinema Hall", "Multiplex Screen", "Stage", "Green Room", "Control Room", "Projection Room"]),
        ("Exhibition", ["Gallery", "Exhibition Hall", "Museum Display", "Workshop", "Gift Shop"]),
    ],
    "Infrastructure": [
        ("Transit", ["Bus Bay", "Waiting Hall", "Ticket Counter", "Platform"]),
        ("Operations", ["Control Room", "Station Office", "Security"]),
        ("Services", ["Electrical Room", "Maintenance Room"]),
    ],
    "Landscape": [
        ("Open Areas", ["Lawn", "Garden", "Courtyard", "Water Feature", "Amphitheatre"]),
        ("Structures", ["Pergola", "Gazebo"]),
        ("Recreation", ["Walking Track", "Jogging Track", "Seating Area", "Children's Play Area"]),
    ],
}

# Applied to every project type (existing and new) -- common across all building types.
UNIVERSAL_SPACES = [
    "Staircase", "Lift", "Lift Lobby", "Corridor", "Lobby", "Waiting Area", "Reception",
    "Security Room", "Store", "Pantry", "Toilet", "Accessible Toilet", "Electrical Room",
    "AHU Room", "Pump Room", "DG Room", "Fire Control Room", "Server Room", "Housekeeping",
    "Janitor Closet", "Waste Collection Room", "Loading / Unloading Area", "Parking", "Ramp",
]

NEW_PROJECT_TYPES = ["Religious", "Sports", "Entertainment"]


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Add any missing project types
    for pt_name in NEW_PROJECT_TYPES:
        cur.execute("INSERT OR IGNORE INTO mstProjectType (ProjectType) VALUES (?)", (pt_name,))
    conn.commit()

    inserted_count = 0
    for pt_name, categories in SPACE_LIBRARY.items():
        cur.execute("SELECT ProjectTypeID FROM mstProjectType WHERE ProjectType=?", (pt_name,))
        row = cur.fetchone()
        if not row:
            print(f"WARNING: Project type '{pt_name}' not found, skipping")
            continue
        pt_id = row[0]
        for category, spaces in categories:
            for space_name in spaces:
                cur.execute(
                    "INSERT OR IGNORE INTO mstRoomLibrary (ProjectTypeID, RoomName, RoomCategory) VALUES (?,?,?)",
                    (pt_id, space_name, category)
                )
                if cur.rowcount:
                    inserted_count += 1

    # Universal spaces -- add to every project type, including ones not covered above
    cur.execute("SELECT ProjectTypeID, ProjectType FROM mstProjectType")
    all_types = cur.fetchall()
    for pt_id, pt_name in all_types:
        for space_name in UNIVERSAL_SPACES:
            cur.execute(
                "INSERT OR IGNORE INTO mstRoomLibrary (ProjectTypeID, RoomName, RoomCategory) VALUES (?,?,?)",
                (pt_id, space_name, "Universal")
            )
            if cur.rowcount:
                inserted_count += 1

    conn.commit()
    print(f"Inserted {inserted_count} new space library rows.")

    cur.execute("""
        SELECT pt.ProjectType, COUNT(rl.RoomLibraryID) as n
        FROM mstProjectType pt LEFT JOIN mstRoomLibrary rl ON pt.ProjectTypeID = rl.ProjectTypeID
        GROUP BY pt.ProjectType ORDER BY pt.ProjectType
    """)
    print("\nSpace count per project type:")
    for pt_name, n in cur.fetchall():
        print(f"  {pt_name}: {n}")

    conn.close()


if __name__ == "__main__":
    migrate()

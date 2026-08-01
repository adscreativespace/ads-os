"""
ADS OS -- Package Deliverable Inheritance Migration
Rebuilds mstPackage / mstDeliverable per the 5-tier structure with inheritance:
Building Planning -> Essential -> Essential Plus -> Signature -> Complete.
Each package stores only NEW/changed deliverables; assembling the full list
for a package walks the ParentPackageID chain and applies SupersedesDeliverableID
overrides so upgraded items don't appear twice.

Safe to re-run: wipes and rebuilds mstPackage, mstDeliverable, mstPackageService,
mstRevisionPolicy only. Does not touch tblClient/tblProject/transaction data.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")


def migrate():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF")  # temporarily, while we rebuild in dependency order
    cur = conn.cursor()

    # --- Schema additions ---
    cur.execute("PRAGMA table_info(mstPackage)")
    pkg_cols = [r[1] for r in cur.fetchall()]
    if "PackageOrder" not in pkg_cols:
        cur.execute("ALTER TABLE mstPackage ADD COLUMN PackageOrder INTEGER")
    if "ParentPackageID" not in pkg_cols:
        cur.execute("ALTER TABLE mstPackage ADD COLUMN ParentPackageID INTEGER REFERENCES mstPackage(PackageID)")
    if "CalculationBasis" not in pkg_cols:
        cur.execute("ALTER TABLE mstPackage ADD COLUMN CalculationBasis TEXT")

    cur.execute("PRAGMA table_info(mstDeliverable)")
    del_cols = [r[1] for r in cur.fetchall()]
    if "SupersedesDeliverableID" not in del_cols:
        cur.execute("ALTER TABLE mstDeliverable ADD COLUMN SupersedesDeliverableID INTEGER REFERENCES mstDeliverable(DeliverableID)")

    cur.execute("""CREATE TABLE IF NOT EXISTS mstPackageService (
        PackageServiceID INTEGER PRIMARY KEY AUTOINCREMENT,
        PackageID INTEGER NOT NULL REFERENCES mstPackage(PackageID),
        ServiceID INTEGER NOT NULL REFERENCES mstProfessionalService(ServiceID),
        InclusionType TEXT NOT NULL DEFAULT 'NotIncluded',
        Notes TEXT
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS mstRevisionPolicy (
        PolicyID INTEGER PRIMARY KEY AUTOINCREMENT,
        PackageID INTEGER NOT NULL REFERENCES mstPackage(PackageID),
        Category TEXT NOT NULL,
        RevisionCount INTEGER,
        RevisionRule TEXT
    )""")

    # --- Wipe and rebuild package-related data only ---
    cur.execute("DELETE FROM mstDeliverable")
    cur.execute("DELETE FROM mstPackageService")
    cur.execute("DELETE FROM mstRevisionPolicy")
    cur.execute("DELETE FROM mstPackage")
    conn.commit()

    # --- Packages, in tier order ---
    packages = [
        ("Building Planning", 20, 10000, "Planning approval and architectural layout.",
         "New residential, commercial and institutional planning projects.", 1, None, "BuiltUpArea"),
        ("Essential", 25, 15000, "Everything in Building Planning, plus exterior design and basic working drawings.",
         "Clients wanting core planning & drawings with a basic exterior look.", 2, "Building Planning", "BuiltUpArea"),
        ("Essential Plus", 30, 20000, "Everything in Essential, plus upgraded 3D exterior design and high-res renders.",
         "Clients wanting a stronger visual presentation before committing to full interior design.", 3, "Essential", "BuiltUpArea"),
        ("Signature", 70, 45000, "Everything in Essential Plus, plus full interior design and complete working drawings.",
         "Clients wanting full interior design with working drawings.", 4, "Essential Plus", "InteriorDesignedArea"),
        ("Complete", 110, 75000, "Everything in Signature, plus premium exterior design and construction support.",
         "Clients wanting end-to-end design, 3D visualization & site supervision.", 5, "Signature", "InteriorDesignedArea"),
    ]
    pkg_ids = {}
    for name, rate, min_fee, philosophy, ideal_for, order, parent_name, calc_basis in packages:
        parent_id = pkg_ids.get(parent_name)
        cur.execute(
            """INSERT INTO mstPackage (PackageName, Rate, MinimumFee, Philosophy, IdealFor,
               PackageOrder, ParentPackageID, CalculationBasis, Active)
               VALUES (?,?,?,?,?,?,?,?,1)""",
            (name, rate, min_fee, philosophy, ideal_for, order, parent_id, calc_basis)
        )
        pkg_ids[name] = cur.lastrowid
    conn.commit()

    # --- Deliverables: only NEW items introduced at each tier ---
    def add_deliverable(pkg_name, category, text, order, optional=0, supersedes_text=None, supersedes_pkg=None):
        supersedes_id = None
        if supersedes_text:
            cur.execute(
                "SELECT DeliverableID FROM mstDeliverable WHERE PackageID=? AND Deliverable=?",
                (pkg_ids[supersedes_pkg], supersedes_text)
            )
            row = cur.fetchone()
            if row:
                supersedes_id = row[0]
        cur.execute(
            """INSERT INTO mstDeliverable (PackageID, Category, Deliverable, DisplayOrder, IsOptional,
               SupersedesDeliverableID, Active) VALUES (?,?,?,?,?,?,1)""",
            (pkg_ids[pkg_name], category, text, order, optional, supersedes_id)
        )

    # Building Planning
    add_deliverable("Building Planning", "Planning", "2D Floor Plan", 1)
    add_deliverable("Building Planning", "Planning", "Dimensioned Floor Plan", 2)
    add_deliverable("Building Planning", "Planning", "Furniture Layout Plan", 3)
    add_deliverable("Building Planning", "Planning", "Door & Window Schedule", 4)
    add_deliverable("Building Planning", "Planning", "Vastu Compliance", 5, optional=1)

    # Essential (new only)
    add_deliverable("Essential", "Exterior Design", "1 Photorealistic Exterior Design", 1)
    add_deliverable("Essential", "Exterior Design", "Exterior Colour Scheme", 2)
    add_deliverable("Essential", "Exterior Design", "Material Recommendation", 3)
    add_deliverable("Essential", "Technical Drawings", "Basic Working Drawings", 4)

    # Essential Plus (new/upgraded only)
    add_deliverable("Essential Plus", "Exterior Design", "1 Photorealistic 3D Exterior Design", 1,
                     supersedes_text="1 Photorealistic Exterior Design", supersedes_pkg="Essential")
    add_deliverable("Essential Plus", "Exterior Design", "Material & Finish Recommendation", 2,
                     supersedes_text="Material Recommendation", supersedes_pkg="Essential")
    add_deliverable("Essential Plus", "Technical Drawings", "Working Drawings", 3,
                     supersedes_text="Basic Working Drawings", supersedes_pkg="Essential")
    add_deliverable("Essential Plus", "Presentation", "High Resolution Render (JPG)", 4)

    # Signature (new/upgraded only)
    add_deliverable("Signature", "Interior Design", "Interior Design for Approved Areas", 1)
    add_deliverable("Signature", "Technical Drawings", "Complete Working Drawing Set", 2,
                     supersedes_text="Working Drawings", supersedes_pkg="Essential Plus")
    add_deliverable("Signature", "Presentation", "Walkthrough Video", 3, optional=1)

    # Complete (new/upgraded only)
    add_deliverable("Complete", "Exterior Design", "Premium Exterior Design", 1,
                     supersedes_text="1 Photorealistic 3D Exterior Design", supersedes_pkg="Essential Plus")
    add_deliverable("Complete", "Interior Design", "Complete Interior Design", 2,
                     supersedes_text="Interior Design for Approved Areas", supersedes_pkg="Signature")
    add_deliverable("Complete", "Construction Support", "Periodic Site Supervision (As Agreed)", 3)
    conn.commit()

    # --- Professional Services per package ---
    def set_service(pkg_name, service_name, inclusion, notes=None):
        cur.execute("SELECT ServiceID FROM mstProfessionalService WHERE ServiceName=?", (service_name,))
        row = cur.fetchone()
        if not row:
            return
        cur.execute(
            "INSERT INTO mstPackageService (PackageID, ServiceID, InclusionType, Notes) VALUES (?,?,?,?)",
            (pkg_ids[pkg_name], row[0], inclusion, notes)
        )

    base_services = [
        ("Consultation", "NotIncluded", None),
        ("Site Visit", "Included", None),
        ("Site Supervision", "Optional", None),
        ("Structural Design", "Optional", None),
        ("Exterior Design", "Optional", None),
    ]
    for pkg_name in ["Building Planning", "Essential", "Essential Plus"]:
        for service_name, inclusion, notes in base_services:
            set_service(pkg_name, service_name, inclusion, notes)

    for service_name, inclusion, notes in base_services:
        if service_name == "Site Supervision":
            set_service("Signature", service_name, "Included", "Periodic, as agreed")
        else:
            set_service("Signature", service_name, inclusion, notes)

    cur.execute("SELECT ServiceID, ServiceName FROM mstProfessionalService")
    for service_id, service_name in cur.fetchall():
        cur.execute(
            "INSERT INTO mstPackageService (PackageID, ServiceID, InclusionType, Notes) VALUES (?,?,?,?)",
            (pkg_ids["Complete"], service_id, "Included", "All available services")
        )
    conn.commit()

    # --- Revision Policy ---
    def set_revision(pkg_name, category, count=None, rule=None):
        cur.execute(
            "INSERT INTO mstRevisionPolicy (PackageID, Category, RevisionCount, RevisionRule) VALUES (?,?,?,?)",
            (pkg_ids[pkg_name], category, count, rule)
        )

    set_revision("Building Planning", "Planning", count=2)
    set_revision("Essential", "Planning", count=2)
    set_revision("Essential", "Exterior", count=1)
    set_revision("Essential Plus", "Planning", count=2)
    set_revision("Essential Plus", "Exterior", count=1)
    set_revision("Signature", "Planning", count=2)
    set_revision("Signature", "Exterior", count=1)
    set_revision("Signature", "Interior", rule="As per Package Policy")
    set_revision("Complete", "Planning", count=2)
    set_revision("Complete", "Exterior", count=2)
    set_revision("Complete", "Interior", rule="As per Package Policy")
    conn.commit()

    conn.execute("PRAGMA foreign_keys = ON")
    conn.close()
    print("Migration complete.")


def get_assembled_package(package_id):
    """
    Walks the ParentPackageID inheritance chain from root to the given package,
    unioning all deliverables and applying SupersedesDeliverableID overrides so
    upgraded items replace their older version instead of duplicating.
    Returns a dict: {category: [deliverable strings]}
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    chain = []
    current_id = package_id
    while current_id is not None:
        cur.execute("SELECT * FROM mstPackage WHERE PackageID=?", (current_id,))
        pkg = cur.fetchone()
        if not pkg:
            break
        chain.append(pkg)
        current_id = pkg["ParentPackageID"]
    chain.reverse()  # root first

    superseded_ids = set()
    all_deliverables = []
    for pkg in chain:
        cur.execute("SELECT * FROM mstDeliverable WHERE PackageID=? AND Active=1", (pkg["PackageID"],))
        for d in cur.fetchall():
            if d["SupersedesDeliverableID"]:
                superseded_ids.add(d["SupersedesDeliverableID"])
            all_deliverables.append(d)

    result = {}
    for d in all_deliverables:
        if d["DeliverableID"] in superseded_ids:
            continue
        result.setdefault(d["Category"], []).append(
            d["Deliverable"] + (" (Optional)" if d["IsOptional"] else "")
        )
    conn.close()
    return result


if __name__ == "__main__":
    migrate()
    import json
    for name in ["Building Planning", "Essential", "Essential Plus", "Signature", "Complete"]:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT PackageID FROM mstPackage WHERE PackageName=?", (name,))
        pid = cur.fetchone()[0]
        conn.close()
        print(f"\n=== {name} (assembled) ===")
        print(json.dumps(get_assembled_package(pid), indent=2))

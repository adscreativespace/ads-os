"""
ADS OS Desktop -- Floor & Space Manager (Sprint 3)
Embedded inside the Project Workspace's Planning tab as a single split view:
Floors on the left, the selected floor's Spaces inline on the right.

Terminology: "Space" is used in all user-facing text instead of "Room" -- not
every entry is a room (Balcony, Parking, Staircase aren't rooms), so "Space
Type"/"Space Name"/"Space Status" is the technically correct term across every
project type ADS handles. Database column/table names (tblRoom, RoomName,
mstRoomLibrary, etc.) are left as-is -- that's an internal detail, not
something users see, and renaming it now would be pure churn with real risk.

Floor identity: Floor Level (structural, mstFloorLibrary) + Display Name
(what shows on quotations/drawings) + Floor Code (drawing sheet numbering).
"""
import os
import shutil
import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
import db
import theme
from constants import apply_decimal_only

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "room_photos")

SPACE_STATUS_OPTIONS = ["Not Started", "Measurement Done", "Planning Done", "Concept Design",
                         "3D Design", "Working Drawings", "Approved", "Completed"]

# Small icon set for common space types -- a scan-at-a-glance aid, not a
# curated architectural database. Falls back to a generic icon.
SPACE_ICONS = {
    "Living Room": "🛋", "Family Living": "🛋", "Dining": "🍽", "Kitchen": "🍳",
    "Master Bedroom": "🛏", "Bedroom": "🛏", "Guest Bedroom": "🛏", "Kids Bedroom": "🛏",
    "Toilet": "🚿", "Attached Toilet": "🚿", "Common Toilet": "🚿",
    "Balcony": "🌿", "Terrace": "🌳", "Parking": "🚗", "Store Room": "📦",
    "Staircase": "🪜", "Pooja Room": "🕉", "Home Office": "💻", "Reception": "🛎",
    "Conference Room": "👥", "Meeting Room": "👥", "Pantry": "🍴", "Server Room": "🖥",
}
DEFAULT_SPACE_ICON = "📐"

# A modest starter set of "these usually go together" suggestions -- not a
# comprehensive space-relationship database, just a few common, safe defaults
# worth expanding later as real project patterns emerge.
COMPANION_SPACES = {
    "Master Bedroom": ["Attached Toilet", "Walk-In Area"],
    "Bedroom": ["Attached Toilet"],
    "Kitchen": ["Utility"],
}

CREATE_CUSTOM_SPACE = "+ Create Custom Space..."


def space_icon(name):
    return SPACE_ICONS.get(name, DEFAULT_SPACE_ICON)


def get_floor_usage_project_type_id(floor_id, fallback_project_type_id):
    """
    Resolves which Space Library applies to a specific floor. Each floor has
    its own FloorUsage (a Sector name, e.g. 'Commercial'), defaulting to the
    project's own sector -- this is what lets a mixed-use building's Ground
    Floor (Commercial) and First Floor (Residential) each show the right
    Space Type list, instead of one fixed list for the whole project.
    Returns a SectorID (mstSector), not the old deprecated ProjectTypeID.
    """
    floor = db.fetch_one("SELECT FloorUsage FROM tblFloor WHERE FloorID=?", (floor_id,))
    if floor and floor["FloorUsage"]:
        sector = db.fetch_one("SELECT SectorID FROM mstSector WHERE SectorName=?", (floor["FloorUsage"],))
        if sector:
            return sector["SectorID"]
    return fallback_project_type_id


def insert_custom_space_library_row(sector_id, room_name, category="Custom"):
    """
    Gets or creates a mstRoomLibrary row for a custom space. Two legacy
    constraints from before the Sector/Service split (v2.0.0) still apply and
    SQLite can't drop them without a full table rebuild:
      - ProjectTypeID is NOT NULL
      - UNIQUE(ProjectTypeID, RoomName)
    The second one matters more than it looks: names like "Parking" already
    exist under the old ProjectTypeID from the Universal Spaces seed (v1.1.0),
    so a naive insert fails with a UNIQUE violation the moment someone adds a
    custom space whose name happens to already exist there. Instead: reuse an
    existing row (by SectorID first, then by the legacy ProjectTypeID) rather
    than trying to insert a duplicate.
    """
    existing = db.fetch_one("SELECT RoomLibraryID FROM mstRoomLibrary WHERE SectorID=? AND RoomName=?",
                            (sector_id, room_name))
    if existing:
        return existing["RoomLibraryID"]

    sector = db.fetch_one("SELECT SectorName FROM mstSector WHERE SectorID=?", (sector_id,))
    legacy_type_id = None
    if sector:
        legacy = db.fetch_one("SELECT ProjectTypeID FROM mstProjectType WHERE ProjectType=?", (sector["SectorName"],))
        legacy_type_id = legacy["ProjectTypeID"] if legacy else None
    if legacy_type_id is None:
        legacy_type_id = db.fetch_one("SELECT ProjectTypeID FROM mstProjectType LIMIT 1")["ProjectTypeID"]

    legacy_existing = db.fetch_one("SELECT RoomLibraryID FROM mstRoomLibrary WHERE ProjectTypeID=? AND RoomName=?",
                                    (legacy_type_id, room_name))
    if legacy_existing:
        db.execute("UPDATE mstRoomLibrary SET SectorID=? WHERE RoomLibraryID=? AND SectorID IS NULL",
                   (sector_id, legacy_existing["RoomLibraryID"]))
        return legacy_existing["RoomLibraryID"]

    return db.execute(
        "INSERT INTO mstRoomLibrary (ProjectTypeID, SectorID, RoomName, RoomCategory) VALUES (?,?,?,?)",
        (legacy_type_id, sector_id, room_name, category)
    )


def get_unique_space_name(floor_id, base_name, exclude_room_id=None):
    """If base_name already exists on this floor, returns 'base_name 2' (or 3, 4...)."""
    existing_names = {r["RoomName"].strip().lower() for r in
                       db.fetch_all("SELECT RoomName FROM tblRoom WHERE FloorID=? AND RoomID != ?",
                                    (floor_id, exclude_room_id or -1))}
    if base_name.strip().lower() not in existing_names:
        return base_name
    n = 2
    while f"{base_name} {n}".strip().lower() in existing_names:
        n += 1
    return f"{base_name} {n}"


class FloorRoomPanel(ctk.CTkFrame):
    def __init__(self, master, project_id, project_type_id, default_package_id):
        super().__init__(master, fg_color="transparent")
        self.project_id = project_id
        self.project_type_id = project_type_id
        self.default_package_id = default_package_id
        self.selected_floor_id = None
        sector_row = db.fetch_one("SELECT SectorName FROM mstSector WHERE SectorID=?", (project_type_id,))
        self.project_sector_name = sector_row["SectorName"] if sector_row else None
        self._build_ui()
        self.refresh_floors()

    def _build_ui(self):
        split = ctk.CTkFrame(self, fg_color="transparent")
        split.pack(fill="both", expand=True)

        # ---------- Left: Floor list ----------
        left = ctk.CTkFrame(split, fg_color=theme.WHITE, width=240)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)

        ctk.CTkLabel(left, text="Floors", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=10, pady=(10, 5))

        self.floor_tree = ttk.Treeview(left, columns=("name",), show="tree", height=14, selectmode="browse")
        self.floor_tree.pack(fill="both", expand=True, padx=10)
        self.floor_tree.bind("<<TreeviewSelect>>", self._on_floor_select)

        floor_btns = ctk.CTkFrame(left, fg_color="transparent")
        floor_btns.pack(fill="x", padx=10, pady=10)
        ctk.CTkButton(floor_btns, text="+ Add Floor", command=self.open_add_floor,
                      fg_color=theme.BRASS, hover_color=theme.INK, font=theme.FONT_SMALL,
                      height=26).pack(fill="x", pady=(0, 5))
        row_btns = ctk.CTkFrame(floor_btns, fg_color="transparent")
        row_btns.pack(fill="x")
        ctk.CTkButton(row_btns, text="Edit", command=self.open_edit_floor,
                      fg_color=theme.INK, font=theme.FONT_SMALL, height=26, width=85).pack(side="left", padx=(0, 5))
        ctk.CTkButton(row_btns, text="Delete", command=self.delete_floor,
                      fg_color="#8B2E2E", hover_color="#5E1F1F", font=theme.FONT_SMALL,
                      height=26, width=85).pack(side="left")

        # ---------- Right: Selected floor's details + inline Spaces ----------
        right = ctk.CTkFrame(split, fg_color=theme.WHITE)
        right.pack(side="left", fill="both", expand=True)

        self.floor_header = ctk.CTkLabel(right, text="Select a floor", font=theme.FONT_SUBHEADING,
                                         text_color=theme.INK)
        self.floor_header.pack(anchor="w", padx=15, pady=(15, 2))
        self.floor_summary_label = ctk.CTkLabel(right, text="", font=theme.FONT_SMALL, text_color=theme.MUTED,
                                                justify="left")
        self.floor_summary_label.pack(anchor="w", padx=15, pady=(0, 10))

        room_header = ctk.CTkFrame(right, fg_color="transparent")
        room_header.pack(fill="x", padx=15)
        ctk.CTkLabel(room_header, text="Spaces", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(side="left")
        self.add_room_btn = ctk.CTkButton(room_header, text="+ Add Space", command=self.open_add_room,
                                          fg_color=theme.BRASS, hover_color=theme.INK,
                                          font=theme.FONT_SMALL, height=26, state="disabled")
        self.add_room_btn.pack(side="right")

        room_table_frame = ctk.CTkFrame(right, fg_color=theme.PARCHMENT)
        room_table_frame.pack(fill="both", expand=True, padx=15, pady=10)

        cols = ("name", "area", "dims", "package", "status")
        self.room_tree = ttk.Treeview(room_table_frame, columns=cols, show="headings", height=10)
        headings = {"name": "Space", "area": "Area", "dims": "Dimensions", "package": "Package", "status": "Status"}
        widths = {"name": 160, "area": 80, "dims": 130, "package": 100, "status": 130}
        for c in cols:
            self.room_tree.heading(c, text=headings[c])
            self.room_tree.column(c, width=widths[c])
        self.room_tree.pack(fill="both", expand=True, side="left")
        self.room_tree.bind("<Double-1>", lambda e: self.open_edit_room())

        # Colored status badges via row tags -- Not Started/similar early
        # stages read as neutral gray, active design stages as blue, Approved
        # as a distinct teal, Completed as green.
        self.room_tree.tag_configure("status_notstarted", foreground="#6B6B6B")
        self.room_tree.tag_configure("status_inprogress", foreground="#1E5FA8")
        self.room_tree.tag_configure("status_approved", foreground="#0E7C7B")
        self.room_tree.tag_configure("status_completed", foreground="#2E8B57")

        room_scrollbar = ttk.Scrollbar(room_table_frame, orient="vertical", command=self.room_tree.yview)
        self.room_tree.configure(yscroll=room_scrollbar.set)
        room_scrollbar.pack(side="right", fill="y")

        room_footer = ctk.CTkFrame(right, fg_color="transparent")
        room_footer.pack(fill="x", padx=15, pady=(0, 15))
        ctk.CTkButton(room_footer, text="Edit", command=self.open_edit_room,
                      fg_color=theme.INK, font=theme.FONT_SMALL, height=26).pack(side="left", padx=(0, 8))
        ctk.CTkButton(room_footer, text="Duplicate", command=self.duplicate_room,
                      fg_color=theme.BRASS, hover_color=theme.INK, font=theme.FONT_SMALL, height=26).pack(side="left", padx=(0, 8))
        ctk.CTkButton(room_footer, text="Delete", command=self.delete_room,
                      fg_color="#8B2E2E", hover_color="#5E1F1F", font=theme.FONT_SMALL, height=26).pack(side="left")

        self.warning_label = ctk.CTkLabel(self, text="", font=theme.FONT_SMALL, text_color="#8B2E2E", justify="left")
        self.warning_label.pack(anchor="w", pady=(10, 0))

    # ---------------- Floors ----------------

    def refresh_floors(self):
        for row in self.floor_tree.get_children():
            self.floor_tree.delete(row)
        floors = db.fetch_all(
            "SELECT * FROM tblFloor WHERE ProjectID=? ORDER BY FloorOrder", (self.project_id,))
        total_floor_area = 0
        total_room_area = 0
        zero_area_spaces = 0
        total_spaces = 0
        for f in floors:
            label = f["DisplayName"] or f["FloorName"]
            if f["FloorCode"]:
                label = f"[{f['FloorCode']}] {label}"
            # Only show usage when it differs from the project's own sector --
            # showing "Ground Floor -- Residential" on every floor of a plain
            # Residential project is pure repetition; it earns its place only
            # for a genuine mixed-use override.
            if f["FloorUsage"] and f["FloorUsage"] != self.project_sector_name:
                label = f"{label} — {f['FloorUsage']}"
            self.floor_tree.insert("", "end", iid=f["FloorID"], text=label)
            total_floor_area += f["BuiltUpArea"] or 0
            room_area = db.fetch_one("SELECT COALESCE(SUM(Area),0) AS s FROM tblRoom WHERE FloorID=?",
                                      (f["FloorID"],))["s"]
            total_room_area += room_area or 0
            space_count_row = db.fetch_one("SELECT COUNT(*) AS n FROM tblRoom WHERE FloorID=?", (f["FloorID"],))
            total_spaces += space_count_row["n"]
            zero_area_spaces += db.fetch_one(
                "SELECT COUNT(*) AS n FROM tblRoom WHERE FloorID=? AND (Area IS NULL OR Area=0)", (f["FloorID"],))["n"]

        self._render_warning(total_spaces, zero_area_spaces)

        if self.selected_floor_id and any(f["FloorID"] == self.selected_floor_id for f in floors):
            self.floor_tree.selection_set(str(self.selected_floor_id))
        else:
            self.selected_floor_id = None
            self._clear_room_panel()

    def _render_warning(self, total_spaces, zero_area_spaces):
        if total_spaces == 0:
            self.warning_label.configure(text="")
            return
        complete = total_spaces - zero_area_spaces
        pct = int(round(complete / total_spaces * 100))
        if zero_area_spaces == 0:
            self.warning_label.configure(text=f"Planning Complete — all {total_spaces} space(s) have an area set.",
                                         text_color="#2E8B57")
        else:
            self.warning_label.configure(
                text=f"⚠ Planning Incomplete — {zero_area_spaces} space(s) missing area. Completion: {pct}%",
                text_color="#8B2E2E")

    def _on_floor_select(self, _event=None):
        sel = self.floor_tree.selection()
        if not sel:
            self.selected_floor_id = None
            self._clear_room_panel()
            return
        self.selected_floor_id = int(sel[0])
        self.refresh_rooms()

    def _clear_room_panel(self):
        self.floor_header.configure(text="Select a floor")
        self.floor_summary_label.configure(text="")
        self.add_room_btn.configure(state="disabled")
        for row in self.room_tree.get_children():
            self.room_tree.delete(row)

    def open_add_floor(self):
        FloorForm(self, self.project_id, self.project_type_id, on_save=self.refresh_floors)

    def open_edit_floor(self):
        if self.selected_floor_id is None:
            messagebox.showinfo("Select a floor", "Please select a floor from the list first.", parent=self)
            return
        floor = db.fetch_one("SELECT * FROM tblFloor WHERE FloorID=?", (self.selected_floor_id,))
        FloorForm(self, self.project_id, self.project_type_id, on_save=self.refresh_floors, existing=floor)

    def delete_floor(self):
        if self.selected_floor_id is None:
            messagebox.showinfo("Select a floor", "Please select a floor from the list first.", parent=self)
            return
        room_count = db.fetch_one("SELECT COUNT(*) AS n FROM tblRoom WHERE FloorID=?", (self.selected_floor_id,))["n"]
        if room_count > 0:
            if not messagebox.askyesno("Spaces exist on this floor",
                                        f"This floor has {room_count} space(s). Deleting the floor removes them too. Continue?", parent=self):
                return
        else:
            if not messagebox.askyesno("Confirm delete", "Delete this floor permanently?", parent=self):
                return
        db.execute("DELETE FROM tblRoom WHERE FloorID=?", (self.selected_floor_id,))
        db.execute("DELETE FROM tblFloor WHERE FloorID=?", (self.selected_floor_id,))
        db.log_activity("Floor", self.selected_floor_id, "Deleted")
        self.selected_floor_id = None
        self.refresh_floors()

    # ---------------- Spaces (inline, no popup window) ----------------

    @staticmethod
    def _status_tag(status):
        if status in ("Completed",):
            return "status_completed"
        if status in ("Approved",):
            return "status_approved"
        if status in ("Not Started",):
            return "status_notstarted"
        return "status_inprogress"  # Measurement Done, Planning Done, Concept Design, 3D Design, Working Drawings

    def refresh_rooms(self):
        if self.selected_floor_id is None:
            self._clear_room_panel()
            return
        floor = db.fetch_one("SELECT * FROM tblFloor WHERE FloorID=?", (self.selected_floor_id,))
        if not floor:
            self._clear_room_panel()
            return
        display = floor["DisplayName"] or floor["FloorName"]
        self.floor_header.configure(text=display)
        self.add_room_btn.configure(state="normal")

        for row in self.room_tree.get_children():
            self.room_tree.delete(row)
        rooms = db.fetch_all("""
            SELECT r.*, p.PackageName FROM tblRoom r
            LEFT JOIN mstPackage p ON r.PackageID = p.PackageID
            WHERE r.FloorID=? ORDER BY r.RoomID
        """, (self.selected_floor_id,))
        allocated = 0
        for r in rooms:
            dims = f"{r['Length'] or '-'} x {r['Width'] or '-'} x {r['CeilingHeight'] or '-'}"
            name_display = f"{space_icon(r['RoomName'])} {r['RoomName']}"
            pkg_display = (r["PackageName"] or "-").replace("Building Planning", "Planning")
            allocated += r["Area"] or 0
            self.room_tree.insert("", "end", iid=r["RoomID"], tags=(self._status_tag(r["DesignStatus"]),),
                                  values=(name_display, f"{r['Area']} sq.ft.", dims,
                                          pkg_display, r["DesignStatus"]))

        # Floor Summary dashboard: Floor Area / Allocated / Remaining / Coverage % / Spaces
        floor_area = floor["BuiltUpArea"] or 0
        remaining = floor_area - allocated
        coverage = int(round(allocated / floor_area * 100)) if floor_area else 0
        self.floor_summary_label.configure(
            text=f"Floor Area: {floor_area:.2f} sq.ft.   |   Allocated: {allocated:.2f} sq.ft.   |   "
                 f"Remaining: {remaining:.2f} sq.ft.   |   Coverage: {coverage}%   |   Spaces: {len(rooms)}"
        )

        self.refresh_warning_only()

    def refresh_warning_only(self):
        """
        Recomputes just the Planning Incomplete banner across all floors,
        without touching the floor list/selection. Calling refresh_floors()
        from here instead would re-trigger the floor selection event and risk
        an infinite refresh loop (selection_set fires <<TreeviewSelect>>).
        """
        floors = db.fetch_all("SELECT FloorID FROM tblFloor WHERE ProjectID=?", (self.project_id,))
        total_spaces = 0
        zero_area_spaces = 0
        for f in floors:
            total_spaces += db.fetch_one("SELECT COUNT(*) AS n FROM tblRoom WHERE FloorID=?", (f["FloorID"],))["n"]
            zero_area_spaces += db.fetch_one(
                "SELECT COUNT(*) AS n FROM tblRoom WHERE FloorID=? AND (Area IS NULL OR Area=0)", (f["FloorID"],))["n"]
        self._render_warning(total_spaces, zero_area_spaces)

    def _selected_room_id(self):
        sel = self.room_tree.selection()
        if not sel:
            messagebox.showinfo("Select a space", "Please select a space from the list first.", parent=self)
            return None
        return int(sel[0])

    def open_add_room(self):
        if self.selected_floor_id is None:
            return
        effective_type_id = get_floor_usage_project_type_id(self.selected_floor_id, self.project_type_id)
        SpaceSelectionForm(self, self.selected_floor_id, effective_type_id,
                           self.default_package_id, on_save=self.refresh_rooms)

    def open_edit_room(self):
        room_id = self._selected_room_id()
        if room_id is None:
            return
        room = db.fetch_one("SELECT * FROM tblRoom WHERE RoomID=?", (room_id,))
        effective_type_id = get_floor_usage_project_type_id(self.selected_floor_id, self.project_type_id)
        RoomForm(self, self.selected_floor_id, effective_type_id, self.project_id,
                 self.default_package_id, on_save=self.refresh_rooms, existing=room)

    def delete_room(self):
        room_id = self._selected_room_id()
        if room_id is None:
            return
        if messagebox.askyesno("Confirm delete", "Delete this space permanently?", parent=self):
            db.execute("DELETE FROM tblRoom WHERE RoomID=?", (room_id,))
            db.log_activity("Room", room_id, "Deleted")
            self.refresh_rooms()

    def duplicate_room(self):
        """
        Copies the selected space's full details (Area, Ceiling Height,
        Package, Status, Remarks) into a new space with an auto-numbered name
        ('Bedroom' -> 'Bedroom 2'). This is the everyday workflow for adding
        another similar space -- create one well-configured space, duplicate
        it, then only edit what's different.
        """
        room_id = self._selected_room_id()
        if room_id is None:
            return
        room = db.fetch_one("SELECT * FROM tblRoom WHERE RoomID=?", (room_id,))
        new_name = get_unique_space_name(self.selected_floor_id, room["RoomName"])
        new_id = db.execute(
            """INSERT INTO tblRoom (FloorID, RoomLibraryID, RoomName, Length, Width, CeilingHeight, Area,
               PackageID, DesignStatus, Remarks) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (self.selected_floor_id, room["RoomLibraryID"], new_name, room["Length"], room["Width"],
             room["CeilingHeight"], room["Area"], room["PackageID"], room["DesignStatus"], room["Remarks"])
        )
        db.log_activity("Room", new_id, "Created (duplicate)")
        self.refresh_rooms()


class FloorForm(ctk.CTkToplevel):
    """
    Floor Level = structural level (used for ordering, drawing calculations).
    Display Name = what appears on quotations/drawings/reports (defaults to the
    level's name, but editable -- e.g. Ground Floor -> "OPD Block" for a hospital).
    Floor Code = short code for drawing sheet numbering (e.g. GF, B1, FF).
    """
    def __init__(self, master, project_id, project_type_id, on_save, existing=None):
        super().__init__(master)
        self.project_id = project_id
        self.on_save = on_save
        self.existing = existing
        self.title("Edit Floor" if existing else "Add Floor")
        self.geometry("440x580")
        self.configure(fg_color=theme.PARCHMENT)
        self.grab_set()

        self.floor_libs = db.fetch_all(
            "SELECT FloorLibraryID, FloorName, FloorOrder, DefaultCode FROM mstFloorLibrary WHERE Active=1 ORDER BY FloorOrder")
        lib_names = [f["FloorName"] for f in self.floor_libs]
        self.sectors = db.fetch_all("SELECT SectorID, SectorName FROM mstSector WHERE Active=1 ORDER BY SectorName")
        usage_names = [s["SectorName"] for s in self.sectors]
        project_default_sector = db.fetch_one("""
            SELECT sec.SectorName FROM tblProject p JOIN mstSector sec ON p.SectorID = sec.SectorID
            WHERE p.ProjectID=?
        """, (project_id,))
        default_usage = existing["FloorUsage"] if existing and existing["FloorUsage"] else \
            (project_default_sector["SectorName"] if project_default_sector else (usage_names[0] if usage_names else ""))

        row = 0
        ctk.CTkLabel(self, text=self.title(), font=theme.FONT_SUBHEADING, text_color=theme.INK).grid(
            row=row, column=0, columnspan=2, padx=15, pady=(15, 10), sticky="w")
        row += 1

        ctk.CTkLabel(self, text="Floor Level *", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        default_lib = next((f["FloorName"] for f in self.floor_libs
                            if existing and f["FloorLibraryID"] == existing["FloorLibraryID"]),
                           lib_names[0] if lib_names else "")
        self.lib_var = ctk.StringVar(value=default_lib)
        ctk.CTkOptionMenu(self, values=lib_names, variable=self.lib_var, width=220,
                          command=self._on_level_change).grid(row=row, column=1, padx=15, pady=6)
        row += 1

        ctk.CTkLabel(self, text="Floor Usage *", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        self.usage_var = ctk.StringVar(value=default_usage)
        ctk.CTkOptionMenu(self, values=usage_names, variable=self.usage_var, width=220).grid(
            row=row, column=1, padx=15, pady=6)
        row += 1
        ctk.CTkLabel(self, text="Which Space Library applies to this floor -- defaults to the project's own "
                                 "type, override for mixed-use floors (e.g. a Commercial ground floor in a "
                                 "Residential building)",
                     font=theme.FONT_SMALL, text_color=theme.MUTED, wraplength=380, justify="left").grid(
            row=row, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 6))
        row += 1

        ctk.CTkLabel(self, text="Display Name", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        self.display_entry = ctk.CTkEntry(self, width=220)
        self.display_entry.grid(row=row, column=1, padx=15, pady=6)
        self.display_entry.insert(0, (existing["DisplayName"] or existing["FloorName"]) if existing else default_lib)
        row += 1
        ctk.CTkLabel(self, text="Shown on quotations, drawings, and reports (e.g. \"OPD Block\" for a hospital's Ground Floor)",
                     font=theme.FONT_SMALL, text_color=theme.MUTED, wraplength=380, justify="left").grid(
            row=row, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 6))
        row += 1

        ctk.CTkLabel(self, text="Floor Code", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        self.code_entry = ctk.CTkEntry(self, width=100)
        self.code_entry.grid(row=row, column=1, padx=15, pady=6, sticky="w")
        default_code = next((f["DefaultCode"] for f in self.floor_libs
                            if f["FloorName"] == default_lib), "")
        self.code_entry.insert(0, existing["FloorCode"] if existing and existing["FloorCode"] else (default_code or ""))
        row += 1
        ctk.CTkLabel(self, text="Used internally and on drawing sheet numbers (e.g. GF, B1, FF)",
                     font=theme.FONT_SMALL, text_color=theme.MUTED, wraplength=380, justify="left").grid(
            row=row, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 6))
        row += 1

        ctk.CTkLabel(self, text="Built-up Area (sq.ft.)", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        self.area_entry = ctk.CTkEntry(self, width=220)
        apply_decimal_only(self, self.area_entry)
        if existing:
            self.area_entry.insert(0, str(existing["BuiltUpArea"]))
        self.area_entry.grid(row=row, column=1, padx=15, pady=6)
        row += 1

        # Floor Default Ceiling Height: new spaces on this floor inherit this
        # value automatically (via UsesFloorDefaultHeight on tblRoom). Changing
        # it here cascades to every space still using the default -- spaces
        # that were given a custom height are never touched.
        ctk.CTkLabel(self, text="Default Ceiling Height (ft)", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        self.default_height_entry = ctk.CTkEntry(self, width=220)
        apply_decimal_only(self, self.default_height_entry)
        self.default_height_entry.insert(0, str(existing["DefaultCeilingHeight"]) if existing and existing["DefaultCeilingHeight"] else "10")
        self.default_height_entry.grid(row=row, column=1, padx=15, pady=6)
        row += 1
        ctk.CTkLabel(self, text="New spaces on this floor inherit this automatically. Changing it updates every "
                                 "space still using the floor default -- spaces with a custom height are untouched.",
                     font=theme.FONT_SMALL, text_color=theme.MUTED, wraplength=380, justify="left").grid(
            row=row, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 6))
        row += 1

        ctk.CTkLabel(self, text="Status", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        self.status_var = ctk.StringVar(value=(existing["Status"] if existing else "Not Started"))
        ctk.CTkOptionMenu(self, values=["Not Started", "In Progress", "Completed"],
                          variable=self.status_var, width=220).grid(row=row, column=1, padx=15, pady=6)
        row += 1

        ctk.CTkButton(self, text="Save", command=self.save, fg_color=theme.BRASS,
                      hover_color=theme.INK, font=theme.FONT_BODY_BOLD).grid(
            row=row, column=0, columnspan=2, pady=20)

    def _on_level_change(self, choice):
        self.display_entry.delete(0, "end")
        self.display_entry.insert(0, choice)
        lib = next((f for f in self.floor_libs if f["FloorName"] == choice), None)
        if lib:
            self.code_entry.delete(0, "end")
            self.code_entry.insert(0, lib["DefaultCode"] or "")

    def save(self):
        display_name = self.display_entry.get().strip()
        if not display_name:
            messagebox.showerror("Missing field", "Display Name is required.", parent=self)
            return
        try:
            area = float(self.area_entry.get().strip() or 0)
            default_height = float(self.default_height_entry.get().strip() or 10)
        except ValueError:
            messagebox.showerror("Invalid number", "Built-up Area and Default Ceiling Height must be numbers.", parent=self)
            return

        lib = next(f for f in self.floor_libs if f["FloorName"] == self.lib_var.get())
        floor_code = self.code_entry.get().strip()

        if self.existing:
            old_default_height = self.existing["DefaultCeilingHeight"]
            db.execute(
                """UPDATE tblFloor SET FloorLibraryID=?, FloorName=?, DisplayName=?, FloorCode=?,
                   FloorOrder=?, FloorUsage=?, BuiltUpArea=?, DefaultCeilingHeight=?, Status=? WHERE FloorID=?""",
                (lib["FloorLibraryID"], lib["FloorName"], display_name, floor_code, lib["FloorOrder"],
                 self.usage_var.get(), area, default_height, self.status_var.get(), self.existing["FloorID"])
            )
            db.log_activity("Floor", self.existing["FloorID"], "Updated")

            # Cascade: update every space still using the floor default --
            # spaces with a custom height (UsesFloorDefaultHeight=0) are
            # never touched.
            if default_height != old_default_height:
                db.execute(
                    "UPDATE tblRoom SET CeilingHeight=? WHERE FloorID=? AND UsesFloorDefaultHeight=1",
                    (default_height, self.existing["FloorID"])
                )
        else:
            new_id = db.execute(
                """INSERT INTO tblFloor (ProjectID, FloorLibraryID, FloorName, DisplayName, FloorCode,
                   FloorOrder, FloorUsage, BuiltUpArea, DefaultCeilingHeight, Status) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (self.project_id, lib["FloorLibraryID"], lib["FloorName"], display_name, floor_code,
                 lib["FloorOrder"], self.usage_var.get(), area, default_height, self.status_var.get())
            )
            db.log_activity("Floor", new_id, "Created")

        self.on_save()
        self.destroy()


class RoomForm(ctk.CTkToplevel):
    def __init__(self, master, floor_id, project_type_id, project_id, default_package_id, on_save, existing=None):
        super().__init__(master)
        self.floor_id = floor_id
        self.project_id = project_id
        self.on_save = on_save
        self.existing = existing
        # Site Photo removed from this dialog -- photos belong to site
        # measurement/execution, not space creation. PhotoPath column is left
        # in the schema (untouched, no data lost for existing spaces) in case
        # a future Execution module wants to attach photos there instead.
        self.photo_path = existing["PhotoPath"] if existing else None
        self.title("Edit Space" if existing else "Add Space")
        self.geometry("880x560")
        self.configure(fg_color=theme.PARCHMENT)
        self.grab_set()

        ctk.CTkLabel(self, text=self.title(), font=theme.FONT_SUBHEADING, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 10))

        columns = ctk.CTkFrame(self, fg_color="transparent")
        columns.pack(fill="both", expand=True, padx=20)

        left = ctk.CTkFrame(columns, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=(0, 35))
        right = ctk.CTkFrame(columns, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        self.room_libs = db.fetch_all(
            "SELECT RoomLibraryID, RoomName FROM mstRoomLibrary WHERE SectorID=? AND Active=1 ORDER BY RoomName",
            (project_type_id,))
        self.project_type_id = project_type_id
        self.packages = db.fetch_all("SELECT PackageID, PackageName FROM mstPackage WHERE Active=1 ORDER BY PackageOrder")
        self.project_default_package_id = default_package_id
        lib_names = [r["RoomName"] for r in self.room_libs] + [CREATE_CUSTOM_SPACE]
        pkg_names = ["-- None --"] + [p["PackageName"] for p in self.packages]

        SELECT_PLACEHOLDER = "-- Select Space Type --"
        FIELD_WIDTH = 300

        # ---------------- LEFT: Space identity + measurements ----------------
        row = 0
        ctk.CTkLabel(left, text="Space Type *", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", pady=10)
        default_room_type = next((r["RoomName"] for r in self.room_libs
                                  if existing and r["RoomLibraryID"] == existing["RoomLibraryID"]),
                                 None)
        if default_room_type is None:
            default_room_type = SELECT_PLACEHOLDER if not existing else (lib_names[0] if lib_names else "")
        menu_values = ([SELECT_PLACEHOLDER] if not existing else []) + lib_names
        self.room_type_var = ctk.StringVar(value=default_room_type)
        if existing:
            # Space Type is locked once a space exists -- changing what a space
            # fundamentally *is* after creation is a data-integrity risk (it
            # would silently disconnect the space from its library entry and
            # any future package/deliverable rules tied to that type). Space
            # Name stays editable for renames like "Bedroom 2" -> "Guest Room".
            self.room_type_menu = ctk.CTkEntry(left, width=FIELD_WIDTH)
            self.room_type_menu.insert(0, default_room_type)
            self.room_type_menu.configure(state="disabled")
        else:
            self.room_type_menu = ctk.CTkOptionMenu(left, values=menu_values if menu_values else ["No spaces defined for this project type"],
                                                    variable=self.room_type_var, width=FIELD_WIDTH,
                                                    command=self._on_room_type_change)
        self.room_type_menu.grid(row=row, column=1, pady=10)
        row += 1

        ctk.CTkLabel(left, text="Space Name", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", pady=10)
        self.name_entry = ctk.CTkEntry(left, width=FIELD_WIDTH)
        self.name_entry.insert(0, existing["RoomName"] if existing else default_room_type)
        self.name_entry.grid(row=row, column=1, pady=10)
        row += 1

        ctk.CTkLabel(left, text="Area Entry Mode", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", pady=10)
        default_mode = "Calculate" if (existing and existing["Length"]) else "Enter Area"
        self.area_mode_var = ctk.StringVar(value=default_mode)
        ctk.CTkSegmentedButton(left, values=["Enter Area", "Calculate"],
                               variable=self.area_mode_var, command=self._on_area_mode_change,
                               fg_color=theme.WHITE, selected_color=theme.BRASS,
                               unselected_color=theme.WHITE, text_color=theme.INK,
                               selected_hover_color=theme.INK, width=FIELD_WIDTH).grid(row=row, column=1, pady=10)
        row += 1

        self.dims_frame = ctk.CTkFrame(left, fg_color="transparent")
        self.dims_frame.grid(row=row, column=0, columnspan=2, sticky="w", pady=0)
        row += 1

        d_row = 0
        ctk.CTkLabel(self.dims_frame, text="Length (ft)", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=d_row, column=0, sticky="w", pady=10)
        self.length_entry = ctk.CTkEntry(self.dims_frame, width=FIELD_WIDTH)
        apply_decimal_only(self, self.length_entry)
        if existing and existing["Length"]:
            self.length_entry.insert(0, str(existing["Length"]))
        self.length_entry.grid(row=d_row, column=1, pady=10)
        self.length_entry.bind("<KeyRelease>", self._recalc_area)
        d_row += 1

        ctk.CTkLabel(self.dims_frame, text="Width (ft)", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=d_row, column=0, sticky="w", pady=10)
        self.width_entry = ctk.CTkEntry(self.dims_frame, width=FIELD_WIDTH)
        apply_decimal_only(self, self.width_entry)
        if existing and existing["Width"]:
            self.width_entry.insert(0, str(existing["Width"]))
        self.width_entry.grid(row=d_row, column=1, pady=10)
        self.width_entry.bind("<KeyRelease>", self._recalc_area)
        d_row += 1

        floor = db.fetch_one("SELECT DefaultCeilingHeight FROM tblFloor WHERE FloorID=?", (self.floor_id,))
        floor_default_height = floor["DefaultCeilingHeight"] if floor and floor["DefaultCeilingHeight"] else 10

        ctk.CTkLabel(left, text="Use Floor Default Ceiling Height", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", pady=10)
        uses_default = bool(existing["UsesFloorDefaultHeight"]) if existing else True
        self.uses_floor_default_var = ctk.BooleanVar(value=uses_default)
        ctk.CTkCheckBox(left, text="", variable=self.uses_floor_default_var,
                        command=self._on_floor_default_toggle, width=20).grid(row=row, column=1, sticky="w", pady=10)
        row += 1

        ctk.CTkLabel(left, text="Ceiling Height (ft)", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", pady=10)
        self.height_entry = ctk.CTkEntry(left, width=FIELD_WIDTH)
        apply_decimal_only(self, self.height_entry)
        initial_height = existing["CeilingHeight"] if existing and existing["CeilingHeight"] else floor_default_height
        self.height_entry.insert(0, str(initial_height))
        self.height_entry.grid(row=row, column=1, pady=10)
        row += 1
        self._floor_default_height = floor_default_height

        ctk.CTkLabel(left, text="Area (sq.ft.)", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", pady=10)
        self.area_entry = ctk.CTkEntry(left, width=FIELD_WIDTH)
        apply_decimal_only(self, self.area_entry)
        if existing:
            self.area_entry.insert(0, str(existing["Area"]))
        self.area_entry.grid(row=row, column=1, pady=10)
        row += 1

        # ---------------- RIGHT: Package, status, remarks ----------------
        row2 = 0
        is_using_project_default = (not existing and default_package_id is not None) or \
                                    (existing and existing["PackageID"] == default_package_id and default_package_id is not None)
        self.use_project_package_var = ctk.BooleanVar(value=bool(is_using_project_default))
        ctk.CTkCheckBox(right, text="Use Default Project Package", variable=self.use_project_package_var,
                        command=self._on_use_project_package_toggle, font=theme.FONT_BODY,
                        text_color=theme.INK).grid(row=row2, column=0, columnspan=2, sticky="w", pady=10)
        row2 += 1

        ctk.CTkLabel(right, text="Package", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row2, column=0, sticky="w", pady=10)
        default_pkg_name = "-- None --"
        if existing and existing["PackageID"]:
            default_pkg_name = next((p["PackageName"] for p in self.packages if p["PackageID"] == existing["PackageID"]),
                                    "-- None --")
        elif not existing and default_package_id:
            default_pkg_name = next((p["PackageName"] for p in self.packages if p["PackageID"] == default_package_id),
                                    "-- None --")
        self.package_var = ctk.StringVar(value=default_pkg_name)
        # Widened so the longest package name ("Essential Plus") always shows
        # in full, never truncated -- worth a bit more width than other fields.
        self.package_menu = ctk.CTkOptionMenu(right, values=pkg_names, variable=self.package_var, width=FIELD_WIDTH + 40)
        self.package_menu.grid(row=row2, column=1, pady=10)
        row2 += 1

        ctk.CTkLabel(right, text="Space Status", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row2, column=0, sticky="w", pady=10)
        self.status_var = ctk.StringVar(value=(existing["DesignStatus"] if existing else "Not Started"))
        ctk.CTkOptionMenu(right, values=SPACE_STATUS_OPTIONS,
                          variable=self.status_var, width=FIELD_WIDTH).grid(row=row2, column=1, pady=10)
        row2 += 1

        ctk.CTkLabel(right, text="Remarks", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row2, column=0, sticky="nw", pady=10)
        self.remarks_entry = ctk.CTkTextbox(right, width=FIELD_WIDTH, height=90)
        if existing and existing["Remarks"]:
            self.remarks_entry.insert("1.0", existing["Remarks"])
        self.remarks_entry.grid(row=row2, column=1, pady=10)
        row2 += 1

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20)
        ctk.CTkButton(btn_frame, text="Save", command=self.save, fg_color=theme.BRASS,
                      hover_color=theme.INK, font=theme.FONT_BODY_BOLD, width=120).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Cancel", command=self.destroy,
                      fg_color=theme.MUTED, font=theme.FONT_BODY, width=120).pack(side="left", padx=10)

        self._on_area_mode_change(default_mode)
        self._on_use_project_package_toggle()
        self._on_floor_default_toggle()

    def _on_room_type_change(self, choice):
        if choice == "-- Select Space Type --":
            return
        if choice == CREATE_CUSTOM_SPACE:
            dialog = ctk.CTkInputDialog(text="Enter the new Space Type name:", title="Create Custom Space")
            new_name = dialog.get_input()
            if new_name and new_name.strip():
                new_name = new_name.strip()
                new_id = insert_custom_space_library_row(self.project_type_id, new_name)
                self.room_libs = db.fetch_all(
                    "SELECT RoomLibraryID, RoomName FROM mstRoomLibrary WHERE SectorID=? AND Active=1 ORDER BY RoomName",
                    (self.project_type_id,))
                lib_names = [r["RoomName"] for r in self.room_libs] + [CREATE_CUSTOM_SPACE]
                self.room_type_menu.configure(values=lib_names)
                self.room_type_var.set(new_name)
                self.name_entry.delete(0, "end")
                self.name_entry.insert(0, new_name)
            else:
                self.room_type_var.set(self.room_libs[0]["RoomName"] if self.room_libs else "")
            return
        self.name_entry.delete(0, "end")
        self.name_entry.insert(0, choice)

    def _on_area_mode_change(self, mode):
        if mode == "Calculate":
            self.dims_frame.grid()
            self.area_entry.configure(state="disabled", fg_color=theme.PARCHMENT)
            self._recalc_area()
        else:
            self.dims_frame.grid_remove()
            self.area_entry.configure(state="normal", fg_color=theme.WHITE)

    def _on_use_project_package_toggle(self):
        if self.use_project_package_var.get():
            if self.project_default_package_id:
                pkg_name = next((p["PackageName"] for p in self.packages
                                  if p["PackageID"] == self.project_default_package_id), "-- None --")
                self.package_var.set(pkg_name)
            self.package_menu.configure(state="disabled")
        else:
            self.package_menu.configure(state="normal")

    def _on_floor_default_toggle(self):
        if self.uses_floor_default_var.get():
            self.height_entry.configure(state="normal")
            self.height_entry.delete(0, "end")
            self.height_entry.insert(0, str(self._floor_default_height))
            self.height_entry.configure(state="disabled")
        else:
            self.height_entry.configure(state="normal")

    def _recalc_area(self, _event=None):
        try:
            length = float(self.length_entry.get() or 0)
            width = float(self.width_entry.get() or 0)
            if length and width:
                # area_entry is disabled (read-only) in Calculate mode -- must
                # temporarily re-enable to update it programmatically, then
                # restore the disabled state.
                self.area_entry.configure(state="normal")
                self.area_entry.delete(0, "end")
                self.area_entry.insert(0, f"{length * width:.2f}")
                self.area_entry.configure(state="disabled")
        except ValueError:
            pass

    def save(self):
        if self.room_type_var.get() == "-- Select Space Type --":
            messagebox.showerror("Missing field", "Please select a Space Type.", parent=self)
            return
        room_name = self.name_entry.get().strip()
        if not room_name:
            messagebox.showerror("Missing field", "Space Name is required.", parent=self)
            return

        # Duplicate detection (new spaces only) -- offer an auto-numbered name,
        # but never block; the person may genuinely want two spaces named alike.
        if not self.existing:
            suggested = get_unique_space_name(self.floor_id, room_name)
            if suggested != room_name:
                use_suggested = messagebox.askyesno(
                    "Space already exists",
                    f"'{room_name}' already exists on this floor. Create it as '{suggested}' instead?"
                , parent=self)
                if use_suggested:
                    room_name = suggested

        try:
            if self.area_mode_var.get() == "Calculate":
                length = float(self.length_entry.get().strip() or 0) or None
                width = float(self.width_entry.get().strip() or 0) or None
            else:
                length = None
                width = None
            height = float(self.height_entry.get().strip() or 0) or None
            area = float(self.area_entry.get().strip() or 0)
        except ValueError:
            messagebox.showerror("Invalid number", "Dimensions, Height, and Area must be numbers.", parent=self)
            return

        room_lib = next((r for r in self.room_libs if r["RoomName"] == self.room_type_var.get()), None)
        room_lib_id = room_lib["RoomLibraryID"] if room_lib else None

        if self.use_project_package_var.get():
            package_id = self.project_default_package_id
        else:
            pkg_name = self.package_var.get()
            package_id = None
            if pkg_name != "-- None --":
                package_id = next((p["PackageID"] for p in self.packages if p["PackageName"] == pkg_name), None)

        remarks = self.remarks_entry.get("1.0", "end").strip()

        uses_floor_default = self.uses_floor_default_var.get()

        if self.existing:
            db.execute(
                """UPDATE tblRoom SET RoomLibraryID=?, RoomName=?, Length=?, Width=?, CeilingHeight=?, Area=?,
                   PackageID=?, DesignStatus=?, PhotoPath=?, Remarks=?, UsesFloorDefaultHeight=? WHERE RoomID=?""",
                (room_lib_id, room_name, length, width, height, area, package_id,
                 self.status_var.get(), self.photo_path, remarks, uses_floor_default, self.existing["RoomID"])
            )
            db.log_activity("Room", self.existing["RoomID"], "Updated")
        else:
            new_id = db.execute(
                """INSERT INTO tblRoom (FloorID, RoomLibraryID, RoomName, Length, Width, CeilingHeight, Area,
                   PackageID, DesignStatus, PhotoPath, Remarks, UsesFloorDefaultHeight)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (self.floor_id, room_lib_id, room_name, length, width, height, area,
                 package_id, self.status_var.get(), self.photo_path, remarks, uses_floor_default)
            )
            db.log_activity("Room", new_id, "Created")

            # Smart Suggestions: offer common companion spaces, if missing
            companions = COMPANION_SPACES.get(room_lib["RoomName"] if room_lib else "", [])
            if companions:
                existing_names = {r["RoomName"] for r in
                                   db.fetch_all("SELECT RoomName FROM tblRoom WHERE FloorID=?", (self.floor_id,))}
                missing = [c for c in companions if c not in existing_names]
                if missing:
                    SuggestionPopup(self.master, self.floor_id, self.project_type_id,
                                    self.project_default_package_id, missing, on_save=self.on_save)

        self._check_area_warning(area)
        self.on_save()
        self.destroy()

    def _check_area_warning(self, this_area):
        floor = db.fetch_one("SELECT BuiltUpArea FROM tblFloor WHERE FloorID=?", (self.floor_id,))
        if not floor or not floor["BuiltUpArea"]:
            return
        total = db.fetch_one("SELECT COALESCE(SUM(Area),0) AS s FROM tblRoom WHERE FloorID=?", (self.floor_id,))["s"]
        if total > floor["BuiltUpArea"]:
            messagebox.showwarning(
                "Area exceeds floor built-up area",
                f"Total space area on this floor ({total:.2f} sq.ft.) now exceeds its "
                f"built-up area ({floor['BuiltUpArea']:.2f} sq.ft.). This isn't blocked -- "
                f"just worth double-checking your measurements."
            , parent=self)


class SuggestionPopup(ctk.CTkToplevel):
    """After saving a space with known companions (e.g. Master Bedroom -> Attached
    Toilet, Walk-In Area), offers to add the missing ones with one click."""
    def __init__(self, master, floor_id, project_type_id, default_package_id, suggestions, on_save):
        super().__init__(master)
        self.floor_id = floor_id
        self.project_type_id = project_type_id
        self.default_package_id = default_package_id
        self.on_save = on_save
        self.title("Add Related Spaces?")
        self.geometry("340x260")
        self.configure(fg_color=theme.PARCHMENT)
        self.grab_set()

        ctk.CTkLabel(self, text="Would you like to also add:", font=theme.FONT_BODY_BOLD,
                     text_color=theme.INK).pack(anchor="w", padx=20, pady=(20, 10))

        self.vars = {}
        for name in suggestions:
            var = ctk.BooleanVar(value=True)
            self.vars[name] = var
            ctk.CTkCheckBox(self, text=name, variable=var, font=theme.FONT_BODY,
                            text_color=theme.INK).pack(anchor="w", padx=30, pady=4)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20)
        ctk.CTkButton(btn_frame, text="Add Selected", command=self._add_selected,
                      fg_color=theme.BRASS, hover_color=theme.INK, font=theme.FONT_BODY_BOLD).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Skip", command=self.destroy,
                      fg_color=theme.MUTED, font=theme.FONT_BODY).pack(side="left", padx=10)

    def _add_selected(self):
        room_libs = db.fetch_all(
            "SELECT RoomLibraryID, RoomName FROM mstRoomLibrary WHERE SectorID=? AND Active=1", (self.project_type_id,))
        for name, var in self.vars.items():
            if not var.get():
                continue
            lib = next((r for r in room_libs if r["RoomName"] == name), None)
            unique_name = get_unique_space_name(self.floor_id, name)
            new_id = db.execute(
                "INSERT INTO tblRoom (FloorID, RoomLibraryID, RoomName, PackageID, DesignStatus, Area) VALUES (?,?,?,?,?,?)",
                (self.floor_id, lib["RoomLibraryID"] if lib else None, unique_name,
                 self.default_package_id, "Not Started", 0)
            )
            db.log_activity("Room", new_id, "Created (suggested companion space)")
        self.on_save()
        self.destroy()


class SpaceSelectionForm(ctk.CTkToplevel):
    """
    Add Space, kept deliberately minimal: check any spaces you want, click
    Generate. No Area, Package, or Status during creation -- those are edited
    afterward, once the space actually exists. Checking a space that already
    exists on this floor auto-numbers it ('Bedroom' -> 'Bedroom 2'), the same
    pattern as Windows' "New Folder (2)" -- no dialog, no quantity field.
    A Custom row covers anything not in the common list; 'Show Full Library'
    reveals everything when the common list doesn't have what you need.
    """
    def __init__(self, master, floor_id, project_type_id, default_package_id, on_save):
        super().__init__(master)
        self.floor_id = floor_id
        self.project_type_id = project_type_id
        self.default_package_id = default_package_id
        self.on_save = on_save
        self.showing_full_library = False
        # Persisted across re-renders (search filtering, library toggle) --
        # previously, re-rendering silently discarded both checked selections
        # and any custom rows the user had added. Fixed here since search
        # filtering hits the exact same re-render path.
        self.checked_lib_ids = set()
        self.custom_rows = []  # list of (synthetic_id, name)
        self.title("Add Space")
        self.geometry("420x640")
        self.configure(fg_color=theme.PARCHMENT)
        self.grab_set()

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(15, 5))
        ctk.CTkLabel(header, text="Add Space", font=theme.FONT_SUBHEADING, text_color=theme.INK).pack(side="left")
        self.toggle_library_btn = ctk.CTkButton(header, text="Show Full Library", command=self._toggle_library,
                                                fg_color=theme.MUTED, font=theme.FONT_SMALL, height=26)
        self.toggle_library_btn.pack(side="right")

        self.search_entry = ctk.CTkEntry(self, placeholder_text="Search spaces...")
        self.search_entry.pack(fill="x", padx=20, pady=(0, 8))
        self.search_entry.bind("<KeyRelease>", lambda e: self._render_rows())

        ctk.CTkLabel(self, text="Check any spaces you want to add. Checking one that already exists on this "
                                 "floor creates the next one automatically (Bedroom -> Bedroom 2). Set area, "
                                 "package, and other details afterward via Edit Space.",
                     font=theme.FONT_SMALL, text_color=theme.MUTED, wraplength=380, justify="left").pack(
            anchor="w", padx=20, pady=(0, 10))

        self.scroll = ctk.CTkScrollableFrame(self, fg_color=theme.WHITE)
        self.scroll.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # row data: RoomLibraryID (or a synthetic negative ID for custom rows) ->
        # {"check": BooleanVar, "name_widget", "name", "is_custom"}
        self.rows = {}
        self._next_custom_id = -1
        self._render_rows()

        custom_frame = ctk.CTkFrame(self, fg_color="transparent")
        custom_frame.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkButton(custom_frame, text="+ Custom Space", command=self._add_custom_row,
                      fg_color=theme.INK, hover_color=theme.BRASS, font=theme.FONT_SMALL, height=26).pack(anchor="w")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=15)
        ctk.CTkButton(btn_frame, text="Generate Selected", command=self._generate,
                      fg_color=theme.BRASS, hover_color=theme.INK, font=theme.FONT_BODY_BOLD, width=160).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Cancel", command=self.destroy,
                      fg_color=theme.MUTED, font=theme.FONT_BODY, width=120).pack(side="left", padx=10)

    def _get_library(self, common_only):
        if common_only:
            libs = db.fetch_all(
                "SELECT RoomLibraryID, RoomName FROM mstRoomLibrary WHERE SectorID=? AND Active=1 AND IsCommon=1 ORDER BY RoomName",
                (self.project_type_id,))
            if libs:
                return libs
            # No curated common list for this project type yet -- fall back to
            # the full library rather than showing an empty dialog.
        return db.fetch_all(
            "SELECT RoomLibraryID, RoomName FROM mstRoomLibrary WHERE SectorID=? AND Active=1 ORDER BY RoomName",
            (self.project_type_id,))

    def _toggle_library(self):
        self.showing_full_library = not self.showing_full_library
        self.toggle_library_btn.configure(text="Show Common Only" if self.showing_full_library else "Show Full Library")
        self._render_rows()

    def _render_rows(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        self.rows = {}
        search_term = self.search_entry.get().strip().lower()
        libs = self._get_library(common_only=not self.showing_full_library)
        if search_term:
            libs = [lib for lib in libs if search_term in lib["RoomName"].lower()]
        for lib in libs:
            self._add_row(lib["RoomLibraryID"], lib["RoomName"])
        # Custom rows persist across re-renders (search/library toggle) and
        # are also filtered by the search term when one is active.
        for custom_id, name in self.custom_rows:
            if not search_term or search_term in name.lower():
                self._add_row(custom_id, name, is_custom=True)

    def _add_row(self, lib_id, name, is_custom=False, checked=None):
        row_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        row_frame.pack(fill="x", pady=3, padx=5)

        is_checked = (lib_id in self.checked_lib_ids) if checked is None else checked
        check_var = ctk.BooleanVar(value=is_checked)
        check_var.trace_add("write", lambda *_, lid=lib_id, v=check_var: self._on_check_toggle(lid, v))
        label = f"{space_icon(name)} {name}" + (" (Custom)" if is_custom else "")
        ctk.CTkCheckBox(row_frame, text=label, variable=check_var,
                        font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w")

        self.rows[lib_id] = {"check": check_var, "name": name, "is_custom": is_custom}

    def _on_check_toggle(self, lib_id, check_var):
        if check_var.get():
            self.checked_lib_ids.add(lib_id)
        else:
            self.checked_lib_ids.discard(lib_id)

    def _add_custom_row(self):
        # Custom spaces are added exactly like predefined ones: name it once,
        # it appears as a real checked checkbox in the same list. No separate
        # "is this checked?" inference from whether a textbox happens to be
        # non-empty -- that ambiguity is exactly what caused Generate to
        # sometimes not pick up a typed custom space.
        dialog = ctk.CTkInputDialog(text="Enter the custom space name:", title="Custom Space")
        name = dialog.get_input()
        if not name or not name.strip():
            return
        name = name.strip()

        # Prevent duplicate entries within this dialog's own checklist (a
        # separate concern from floor-level duplicates, which get auto-numbered
        # at Generate time via get_unique_space_name).
        existing_names_in_dialog = {r["name"] for r in self.rows.values()} | {name for _, name in self.custom_rows}
        candidate = name
        n = 2
        while candidate in existing_names_in_dialog:
            candidate = f"{name} {n}"
            n += 1

        lib_id = self._next_custom_id
        self._next_custom_id -= 1
        self.custom_rows.append((lib_id, candidate))
        self.checked_lib_ids.add(lib_id)
        self._add_row(lib_id, candidate, is_custom=True, checked=True)

    def _generate(self):
        created = 0
        for lib_id, row in self.rows.items():
            if not row["check"].get():
                continue
            space_name = row["name"]
            if not space_name:
                continue

            real_lib_id = lib_id if lib_id > 0 else None
            if row["is_custom"] and real_lib_id is None:
                # Persist custom spaces into the library too, so they're
                # available for future floors/projects of this sector.
                real_lib_id = insert_custom_space_library_row(self.project_type_id, space_name)

            # Auto-numbering: checking "Bedroom" when it already exists on this
            # floor creates "Bedroom 2" automatically -- same pattern as
            # Windows' "New Folder (2)". No dialog, no quantity field.
            unique_name = get_unique_space_name(self.floor_id, space_name)
            new_id = db.execute(
                """INSERT INTO tblRoom (FloorID, RoomLibraryID, RoomName, Area, CeilingHeight, PackageID, DesignStatus)
                   VALUES (?,?,?,?,?,?,?)""",
                (self.floor_id, real_lib_id, unique_name, 0, 10, self.default_package_id, "Not Started")
            )
            db.log_activity("Room", new_id, "Created")
            created += 1

        if created:
            self.on_save()
            self.destroy()
        else:
            messagebox.showinfo("Nothing selected", "Check at least one space (or add a Custom Space) before generating.", parent=self)

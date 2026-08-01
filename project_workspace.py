"""
ADS OS Desktop -- Project Workspace ("Project Command Center")
Opens a single project as its own workspace with tabs, instead of scattering
project-related work across separate top-level modules. Floors & Rooms and
Quotation tabs are placeholders until Sprint 3 / Sprint 4 build them out.
"""
import customtkinter as ctk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
import datetime
import os
import subprocess
import sys
import db
import theme
from constants import apply_decimal_only
from floor_room_manager import FloorRoomPanel
from commercial_panel import CommercialPanel
import report_engine

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Reports")

SITEVISIT_STATUS = ["Scheduled", "Completed", "Cancelled"]
SITEVISIT_PURPOSE_OPTIONS = ["Progress Review", "Measurement", "Contractor Meeting", "Client Meeting",
                            "Material Inspection", "Quality Check", "Billing Verification", "Handover",
                            "Snag List", "Other"]
MILESTONE_STATUS = ["Pending", "In Progress", "Completed"]


class ProjectWorkspace(ctk.CTkToplevel):
    def __init__(self, master, project_id, on_close=None, initial_tab=None):
        super().__init__(master)
        self.project_id = project_id
        self.on_close = on_close
        self.initial_tab = initial_tab
        self.project = db.fetch_one("""
            SELECT p.*, c.ClientName, sec.SectorName, svc.ServiceName
            FROM tblProject p
            JOIN tblClient c ON p.ClientID = c.ClientID
            LEFT JOIN mstSector sec ON p.SectorID = sec.SectorID
            LEFT JOIN mstService svc ON p.ServiceID = svc.ServiceID
            WHERE p.ProjectID = ?
        """, (project_id,))

        self.title(f"{self.project['ProjectName']} — {self.project['ProjectCode']}")
        self.geometry("1050x750")
        self.minsize(900, 600)
        self.configure(fg_color=theme.PARCHMENT)
        self.protocol("WM_DELETE_WINDOW", self._close)

        # Explicit window activation -- this Toplevel previously had zero
        # lift()/focus_force() calls anywhere, relying entirely on the OS/
        # window manager to raise and focus it by default. That's a known,
        # plausible source of a newly-created Toplevel briefly appearing
        # then falling behind its parent, particularly from a busy parent
        # window -- matches the reported symptom exactly. Deferred via
        # after(), not called immediately: lift()/focus_force() called
        # before the window is actually mapped/realized are unreliable: a
        # small delay lets the window manager finish placing the window
        # first, which is the standard, more robust pattern for this.
        self.after(10, lambda: (self.lift(), self.focus_force()))

        header = ctk.CTkFrame(self, fg_color=theme.INK, height=90, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        header_left = ctk.CTkFrame(header, fg_color="transparent")
        header_left.pack(side="left", fill="y", padx=20, pady=12)
        ctk.CTkLabel(header_left, text=self.project["ProjectName"], font=("Georgia", 20, "bold"),
                     text_color=theme.BRASS).pack(anchor="w")
        ctk.CTkLabel(header_left,
                     text=f"{self.project['ClientName']}  ·  {self.project['SectorName'] or '—'} / {self.project['ServiceName'] or '—'}  ·  {self.project['ProjectStatus']}",
                     font=theme.FONT_SMALL, text_color=theme.WHITE).pack(anchor="w")

        pkg_name = "No Default Package"
        if self.project["DefaultPackageID"]:
            pkg_row = db.fetch_one("SELECT PackageName FROM mstPackage WHERE PackageID=?", (self.project["DefaultPackageID"],))
            if pkg_row:
                pkg_name = pkg_row["PackageName"]

        header_right = ctk.CTkFrame(header, fg_color="transparent")
        header_right.pack(side="right", fill="y", padx=20, pady=12)
        report_btn = ctk.CTkButton(header, text="📄 Generate Report", command=self._generate_report,
                                   fg_color=theme.BRASS, hover_color=theme.WHITE,
                                   text_color=theme.INK, font=theme.FONT_SMALL, height=30, width=140)
        report_btn.pack(side="right", padx=(0, 15), pady=12)
        # Available regardless of which tab is active (Planning/Commercial/
        # etc.) -- a floating utility, not tied to any one module. Opens a
        # new instance each time rather than tracking a single reused
        # window, since re-parenting/refocusing an existing CTkToplevel
        # reliably across tab switches is more fragile than just opening
        # a fresh one -- the calculator has no state worth preserving
        # between opens anyway (no history/persistence, by design).
        calc_btn = ctk.CTkButton(header, text="🧮 Calculator", command=self._open_calculator,
                                 fg_color="transparent", hover_color=theme.BRASS, border_width=1,
                                 border_color=theme.BRASS, text_color=theme.WHITE, font=theme.FONT_SMALL,
                                 height=30, width=120)
        calc_btn.pack(side="right", padx=(0, 10), pady=12)
        ctk.CTkLabel(header_right, text=self.project["ProjectCode"], font=theme.FONT_SMALL,
                     text_color=theme.MUTED).pack(anchor="e")
        ctk.CTkLabel(header_right, text=f"{self.project['TotalBuiltUpArea']} {self.project['Unit']}  ·  {pkg_name}",
                     font=theme.FONT_SMALL, text_color=theme.WHITE).pack(anchor="e")
        started_text = f"Started {self.project['StartDate']}" if self.project["StartDate"] else "Start date not set"
        ctk.CTkLabel(header_right, text=started_text, font=theme.FONT_SMALL,
                     text_color=theme.MUTED).pack(anchor="e")

        self.tabs = ctk.CTkTabview(self, fg_color=theme.WHITE, segmented_button_fg_color=theme.INK,
                                    segmented_button_selected_color=theme.BRASS,
                                    segmented_button_unselected_color=theme.INK,
                                    command=self._on_tab_change)
        self.tabs.pack(fill="both", expand=True, padx=15, pady=15)

        for name in ["Overview", "Planning", "Design", "Commercial", "Execution", "Activity"]:
            self.tabs.add(name)

        # Wrap each real (non-placeholder) tab's content in a scrollable frame.
        # Without this, content taller than the window gets clipped with no way
        # to reach it except manually resizing the window -- CTkTabview tabs
        # don't scroll on their own.
        overview_scroll = ctk.CTkScrollableFrame(self.tabs.tab("Overview"), fg_color="transparent")
        overview_scroll.pack(fill="both", expand=True)
        self._build_overview(overview_scroll)

        planning_scroll = ctk.CTkScrollableFrame(self.tabs.tab("Planning"), fg_color="transparent")
        planning_scroll.pack(fill="both", expand=True)
        self._build_planning(planning_scroll)

        design_scroll = ctk.CTkScrollableFrame(self.tabs.tab("Design"), fg_color="transparent")
        design_scroll.pack(fill="both", expand=True)
        self._build_design_overview(design_scroll)
        commercial_scroll = ctk.CTkScrollableFrame(self.tabs.tab("Commercial"), fg_color="transparent")
        commercial_scroll.pack(fill="both", expand=True)
        self.commercial_panel_ref = CommercialPanel(commercial_scroll, self.project_id)
        self.commercial_panel_ref.pack(fill="both", expand=True)

        execution_scroll = ctk.CTkScrollableFrame(self.tabs.tab("Execution"), fg_color="transparent")
        execution_scroll.pack(fill="both", expand=True)
        self._build_site_visits(execution_scroll)

        activity_scroll = ctk.CTkScrollableFrame(self.tabs.tab("Activity"), fg_color="transparent")
        activity_scroll.pack(fill="both", expand=True)
        self._build_activity(activity_scroll)

        # Quick-open support: jump directly to a specific tab (e.g. from a
        # "View Floors" link on the Projects card) instead of always landing
        # on Overview. Reuses the same _on_tab_change refresh logic that
        # already keeps Overview/Design/Activity current, so the target tab
        # is guaranteed fresh even if it's not one of those three.
        if self.initial_tab and self.initial_tab in ["Overview", "Planning", "Design", "Commercial", "Execution", "Activity"]:
            self.tabs.set(self.initial_tab)
            self._on_tab_change()

    def _open_calculator(self):
        from calculator_dialog import CalculatorDialog
        CalculatorDialog(self)

    def _on_tab_change(self):
        """
        Bug fix: Overview/Design/Activity were only ever built once, when the
        workspace window first opened. If you added spaces via Planning
        *after* opening the workspace, Design's stat cards (Total Spaces,
        Design Started, etc.) went stale and never updated -- this is what
        actually caused "Planning shows 13, Design shows 10": not a query bug
        (both counting queries were verified to agree), but a UI staleness
        bug. Fix: rebuild these tabs' content fresh every time you actually
        switch to them, so they always reflect Planning's current data --
        the single source of truth the underlying data model already is.
        """
        current = self.tabs.get()
        if current == "Design":
            for w in self.tabs.tab("Design").winfo_children():
                w.destroy()
            design_scroll = ctk.CTkScrollableFrame(self.tabs.tab("Design"), fg_color="transparent")
            design_scroll.pack(fill="both", expand=True)
            self._build_design_overview(design_scroll)
        elif current == "Overview":
            self.project = db.fetch_one("""
                SELECT p.*, c.ClientName, sec.SectorName, svc.ServiceName
                FROM tblProject p JOIN tblClient c ON p.ClientID = c.ClientID
                LEFT JOIN mstSector sec ON p.SectorID = sec.SectorID
                LEFT JOIN mstService svc ON p.ServiceID = svc.ServiceID WHERE p.ProjectID = ?
            """, (self.project_id,))
            for w in self.tabs.tab("Overview").winfo_children():
                w.destroy()
            overview_scroll = ctk.CTkScrollableFrame(self.tabs.tab("Overview"), fg_color="transparent")
            overview_scroll.pack(fill="both", expand=True)
            self._build_overview(overview_scroll)
        elif current == "Activity":
            for w in self.tabs.tab("Activity").winfo_children():
                w.destroy()
            activity_scroll = ctk.CTkScrollableFrame(self.tabs.tab("Activity"), fg_color="transparent")
            activity_scroll.pack(fill="both", expand=True)
            self._build_activity(activity_scroll)
        elif current == "Commercial":
            # Real root cause of the "blank until something forces a
            # redraw, then duplicates" report: Commercial was built exactly
            # ONCE at workspace __init__ time (unlike Overview/Design/
            # Activity above, which already got this same fix for an
            # analogous staleness bug) -- its CTkScrollableFrame canvas
            # could end up with a stale/never-computed scrollregion if it
            # wasn't the visible tab at construction time. Opening the
            # Calculator (any new Toplevel) was very likely just an
            # incidental trigger for Tkinter to finally recompute geometry,
            # not an actual cause -- matches "this is not a Calculator bug."
            # Preserve whichever Commercial sub-module (Dashboard/Vendors/
            # BOQ/etc.) the user was already on, so switching away and back
            # doesn't reset them to the Dashboard every time.
            previous_module = None
            if hasattr(self, "commercial_panel_ref"):
                previous_module = self.commercial_panel_ref.switcher_var.get()
            for w in self.tabs.tab("Commercial").winfo_children():
                w.destroy()
            commercial_scroll = ctk.CTkScrollableFrame(self.tabs.tab("Commercial"), fg_color="transparent")
            commercial_scroll.pack(fill="both", expand=True)
            self.commercial_panel_ref = CommercialPanel(commercial_scroll, self.project_id,
                                                         initial_module=previous_module)
            self.commercial_panel_ref.pack(fill="both", expand=True)

    def _generate_report(self):
        os.makedirs(REPORTS_DIR, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() or c in " -_" else "" for c in self.project["ProjectName"])
        filename = f"{self.project['ProjectCode']}_{safe_name}_{timestamp}.pdf"
        output_path = os.path.join(REPORTS_DIR, filename)

        try:
            report_engine.generate_project_summary_report(self.project_id, output_path)
        except Exception as e:
            messagebox.showerror("Report generation failed", f"Could not generate the report:\n{e}", parent=self)
            return

        db.log_activity("Project", self.project_id, "Report Generated", filename)

        if messagebox.askyesno("Report generated",
                                f"Saved to:\n{output_path}\n\nOpen it now?", parent=self):
            try:
                if sys.platform == "win32":
                    os.startfile(output_path)
                elif sys.platform == "darwin":
                    subprocess.run(["open", output_path])
                else:
                    subprocess.run(["xdg-open", output_path])
            except Exception as e:
                messagebox.showwarning("Couldn't open automatically",
                                       f"The report was saved, but couldn't be opened automatically:\n{e}\n\n"
                                       f"Find it at: {output_path}", parent=self)

    def _close(self):
        if self.on_close:
            self.on_close()
        self.destroy()

    def _build_design_overview(self, tab):
        ctk.CTkLabel(tab, text="Design & Documentation", font=theme.FONT_HEADING,
                     text_color=theme.INK).pack(anchor="w", padx=20, pady=(15, 5))

        total_spaces = db.fetch_one("""
            SELECT COUNT(*) AS n FROM tblRoom r JOIN tblFloor f ON r.FloorID = f.FloorID
            WHERE f.ProjectID=?
        """, (self.project_id,))["n"]

        if total_spaces == 0:
            ctk.CTkLabel(tab, text="No spaces defined yet. Add floors and spaces in the Planning tab first --\n"
                                    "design tracking starts once there's a project structure to track.",
                         font=theme.FONT_BODY, text_color=theme.MUTED, justify="left").pack(
                anchor="w", padx=20, pady=20)
            return

        not_started = db.fetch_one("""
            SELECT COUNT(*) AS n FROM tblRoom r JOIN tblFloor f ON r.FloorID = f.FloorID
            WHERE f.ProjectID=? AND r.DesignStatus = 'Not Started'
        """, (self.project_id,))["n"]
        started_or_beyond = total_spaces - not_started
        approved_or_completed = db.fetch_one("""
            SELECT COUNT(*) AS n FROM tblRoom r JOIN tblFloor f ON r.FloorID = f.FloorID
            WHERE f.ProjectID=? AND r.DesignStatus IN ('Approved', 'Completed')
        """, (self.project_id,))["n"]

        stats_frame = ctk.CTkFrame(tab, fg_color="transparent")
        stats_frame.pack(fill="x", padx=20, pady=10)
        for label, value in [("Total Spaces", total_spaces), ("Design Started", started_or_beyond),
                              ("Not Started", not_started), ("Approved / Completed", approved_or_completed)]:
            card = ctk.CTkFrame(stats_frame, fg_color=theme.WHITE, corner_radius=8, width=170, height=90)
            card.pack(side="left", padx=(0, 12))
            card.pack_propagate(False)
            ctk.CTkLabel(card, text=str(value), font=("Georgia", 24, "bold"),
                         text_color=theme.BRASS).pack(pady=(12, 0))
            ctk.CTkLabel(card, text=label, font=theme.FONT_SMALL, text_color=theme.MUTED).pack()

        # Per-space status breakdown, grouped by floor
        ctk.CTkLabel(tab, text="Spaces by Status", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 5))
        table_frame = ctk.CTkFrame(tab, fg_color=theme.WHITE)
        table_frame.pack(fill="x", padx=20, pady=(0, 20))
        spaces = db.fetch_all("""
            SELECT r.RoomName, r.DesignStatus, f.DisplayName, f.FloorName FROM tblRoom r
            JOIN tblFloor f ON r.FloorID = f.FloorID WHERE f.ProjectID=? ORDER BY f.FloorOrder, r.RoomID
        """, (self.project_id,))
        cols = ("floor", "space", "status")
        tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=min(12, len(spaces)))
        headings = {"floor": "Floor", "space": "Space", "status": "Design Status"}
        for c in cols:
            tree.heading(c, text=headings[c])
            tree.column(c, width=200)
        tree.pack(fill="both", expand=True, side="left")
        for s in spaces:
            tree.insert("", "end", values=(s["DisplayName"] or s["FloorName"], s["RoomName"], s["DesignStatus"]))

        ctk.CTkLabel(tab, text="Deliverables, Drawing Register, and Client Approvals will build on this same "
                                "structure once the Deliverables Engine and Drawing Register are built.",
                     font=theme.FONT_SMALL, text_color=theme.MUTED, wraplength=600, justify="left").pack(
            anchor="w", padx=20, pady=(0, 20))

    def _build_placeholder(self, tab, text):
        ctk.CTkLabel(tab, text=text, font=theme.FONT_BODY, text_color=theme.MUTED,
                     justify="left").pack(padx=20, pady=40)

    def _build_overview(self, tab):
        p = self.project
        upcoming_visit = db.fetch_one("""
            SELECT VisitDate, Purpose FROM trxSiteVisit
            WHERE ProjectID=? AND Status='Scheduled' AND VisitDate >= date('now')
            ORDER BY VisitDate ASC LIMIT 1
        """, (self.project_id,))
        upcoming_display = f"{upcoming_visit['VisitDate']} — {upcoming_visit['Purpose'] or 'No purpose noted'}" \
            if upcoming_visit else "None scheduled"

        fields = [
            ("Client", p["ClientName"]), ("Sector", p["SectorName"] or "—"), ("Service", p["ServiceName"] or "—"),
            ("Status", p["ProjectStatus"]), ("Site Address", p["SiteAddress"] or "—"),
            ("City / State", f"{p['City'] or '—'} / {p['State'] or '—'}"),
            ("Total Built-up Area", f"{p['TotalBuiltUpArea']} {p['Unit']}"),
            ("Start Date", p["StartDate"] or "—"),
            ("Expected Completion", p["ExpectedCompletion"] or "—"),
            ("Upcoming Site Visit", upcoming_display),
            ("Remarks", p["Remarks"] or "—"),
        ]
        for i, (label, value) in enumerate(fields):
            ctk.CTkLabel(tab, text=label, font=theme.FONT_BODY_BOLD, text_color=theme.INK).grid(
                row=i, column=0, sticky="w", padx=20, pady=8)
            ctk.CTkLabel(tab, text=str(value), font=theme.FONT_BODY, text_color=theme.INK).grid(
                row=i, column=1, sticky="w", padx=20, pady=8)

        ctk.CTkButton(tab, text="Edit Project Details", fg_color=theme.BRASS, hover_color=theme.INK,
                      font=theme.FONT_BODY_BOLD, command=self._edit_project).grid(
            row=len(fields), column=0, columnspan=2, pady=20, padx=20, sticky="w")

    def _edit_project(self):
        # Local import avoids a circular import (project_screen already imports this module's caller)
        from project_screen import ProjectForm
        ProjectForm(self, on_save=self._reload, existing=self.project)

    def _reload(self):
        self.project = db.fetch_one("""
            SELECT p.*, c.ClientName, sec.SectorName, svc.ServiceName
            FROM tblProject p JOIN tblClient c ON p.ClientID = c.ClientID
            LEFT JOIN mstSector sec ON p.SectorID = sec.SectorID
            LEFT JOIN mstService svc ON p.ServiceID = svc.ServiceID WHERE p.ProjectID = ?
        """, (self.project_id,))

    # ---------------- Planning (Milestones + Floors & Rooms placeholder) ----------------

    def _build_planning(self, tab):
        ctk.CTkLabel(tab, text="Project Milestones", font=theme.FONT_BODY_BOLD,
                     text_color=theme.INK).pack(anchor="w", padx=20, pady=(15, 5))
        milestone_container = ctk.CTkFrame(tab, fg_color="transparent")
        milestone_container.pack(fill="x", padx=0, pady=0)
        self.milestone_frame = milestone_container
        self._refresh_milestones()

        ctk.CTkFrame(tab, fg_color=theme.MUTED, height=1).pack(fill="x", padx=20, pady=15)

        ctk.CTkLabel(tab, text="Planning Summary", font=theme.FONT_BODY_BOLD,
                     text_color=theme.INK).pack(anchor="w", padx=20, pady=(0, 5))
        self.planning_summary_frame = ctk.CTkFrame(tab, fg_color=theme.WHITE, corner_radius=6)
        self.planning_summary_frame.pack(fill="x", padx=20, pady=(0, 15))
        self._refresh_planning_summary()

        ctk.CTkFrame(tab, fg_color=theme.MUTED, height=1).pack(fill="x", padx=20, pady=15)

        ctk.CTkLabel(tab, text="Floors & Spaces", font=theme.FONT_BODY_BOLD,
                     text_color=theme.INK).pack(anchor="w", padx=20, pady=(0, 5))
        floor_room_container = ctk.CTkFrame(tab, fg_color="transparent")
        floor_room_container.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        self.floor_room_panel = FloorRoomPanel(floor_room_container, self.project_id, self.project["SectorID"],
                      self.project["DefaultPackageID"])
        self.floor_room_panel.pack(fill="both", expand=True)
        # Refresh the summary whenever floors/spaces change, by wrapping the panel's
        # own refresh methods rather than polling -- keeps the summary always current.
        original_refresh_floors = self.floor_room_panel.refresh_floors
        original_refresh_rooms = self.floor_room_panel.refresh_rooms

        def refresh_floors_and_summary():
            original_refresh_floors()
            self._refresh_planning_summary()

        def refresh_rooms_and_summary():
            original_refresh_rooms()
            self._refresh_planning_summary()

        self.floor_room_panel.refresh_floors = refresh_floors_and_summary
        self.floor_room_panel.refresh_rooms = refresh_rooms_and_summary

    def _refresh_planning_summary(self):
        for w in self.planning_summary_frame.winfo_children():
            w.destroy()

        floors = db.fetch_all("SELECT FloorID, DisplayName, FloorName, BuiltUpArea FROM tblFloor WHERE ProjectID=?",
                              (self.project_id,))
        floor_count = len(floors)
        space_count = db.fetch_one("""
            SELECT COUNT(*) AS n FROM tblRoom r JOIN tblFloor f ON r.FloorID = f.FloorID
            WHERE f.ProjectID=?
        """, (self.project_id,))["n"]
        total_floor_area = sum(f["BuiltUpArea"] or 0 for f in floors)
        total_space_area = 0
        warnings = []
        for f in floors:
            if not f["BuiltUpArea"]:
                warnings.append(f"'{f['DisplayName'] or f['FloorName']}' has no Built-up Area set")
            space_area = db.fetch_one("SELECT COALESCE(SUM(Area),0) AS s FROM tblRoom WHERE FloorID=?",
                                      (f["FloorID"],))["s"]
            total_space_area += space_area or 0
        zero_area_spaces = db.fetch_one("""
            SELECT COUNT(*) AS n FROM tblRoom r JOIN tblFloor f ON r.FloorID = f.FloorID
            WHERE f.ProjectID=? AND (r.Area IS NULL OR r.Area = 0)
        """, (self.project_id,))["n"]
        if zero_area_spaces:
            warnings.append(f"{zero_area_spaces} space(s) have no Area set")

        stats = [
            ("Floors", str(floor_count)), ("Spaces", str(space_count)),
            ("Total Built-up Area", f"{total_floor_area:.2f} sq.ft."),
            ("Total Space Area", f"{total_space_area:.2f} sq.ft."),
        ]
        for i, (label, value) in enumerate(stats):
            ctk.CTkLabel(self.planning_summary_frame, text=label, font=theme.FONT_SMALL,
                         text_color=theme.MUTED).grid(row=0, column=i, padx=15, pady=(10, 0), sticky="w")
            ctk.CTkLabel(self.planning_summary_frame, text=value, font=theme.FONT_BODY_BOLD,
                         text_color=theme.INK).grid(row=1, column=i, padx=15, pady=(0, 10), sticky="w")

        if warnings:
            warning_text = "⚠ " + "  |  ".join(warnings)
            ctk.CTkLabel(self.planning_summary_frame, text=warning_text, font=theme.FONT_SMALL,
                         text_color="#8B2E2E", wraplength=600, justify="left").grid(
                row=2, column=0, columnspan=len(stats), padx=15, pady=(0, 10), sticky="w")

    # ---------------- Activity (live feed from logActivity) ----------------

    def _build_activity(self, tab):
        table_frame = ctk.CTkFrame(tab, fg_color=theme.WHITE)
        table_frame.pack(fill="both", expand=True, padx=20, pady=15)

        cols = ("when", "action", "details")
        tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=16)
        headings = {"when": "When", "action": "Action", "details": "Details"}
        widths = {"when": 150, "action": 150, "details": 400}
        for c in cols:
            tree.heading(c, text=headings[c])
            tree.column(c, width=widths[c])
        tree.pack(fill="both", expand=True, side="left")

        # Activity log is keyed by EntityType/EntityID -- this project's own record plus
        # any milestone/site-visit rows that reference it indirectly via the same project
        entries = db.fetch_all("""
            SELECT LoggedOn, Action, Details FROM logActivity
            WHERE (EntityType='Project' AND EntityID=?)
               OR (EntityType='SiteVisit' AND EntityID IN (SELECT SiteVisitID FROM trxSiteVisit WHERE ProjectID=?))
            ORDER BY LoggedOn DESC
        """, (self.project_id, self.project_id))
        for e in entries:
            tree.insert("", "end", values=(e["LoggedOn"], e["Action"], e["Details"] or ""))

    # ---------------- Milestones ----------------

    def _refresh_milestones(self):
        for w in self.milestone_frame.winfo_children():
            w.destroy()
        milestones = db.fetch_all(
            "SELECT * FROM tblMilestone WHERE ProjectID=? ORDER BY MilestoneOrder", (self.project_id,))
        for i, m in enumerate(milestones):
            ctk.CTkLabel(self.milestone_frame, text=f"{m['MilestoneOrder']}. {m['MilestoneName']}",
                         font=theme.FONT_BODY, text_color=theme.INK).grid(
                row=i, column=0, sticky="w", padx=20, pady=6)
            if m["MilestoneName"] == "Project Closed":
                var = ctk.StringVar(value="Yes" if m["Status"] == "Completed" else "No")
                menu = ctk.CTkOptionMenu(self.milestone_frame, values=["Yes", "No"], variable=var, width=140,
                                         command=lambda choice, mid=m["MilestoneID"]: self._update_milestone(
                                             mid, "Completed" if choice == "Yes" else "Pending"))
            else:
                var = ctk.StringVar(value=m["Status"])
                menu = ctk.CTkOptionMenu(self.milestone_frame, values=MILESTONE_STATUS, variable=var, width=140,
                                         command=lambda choice, mid=m["MilestoneID"]: self._update_milestone(mid, choice))
            menu.grid(row=i, column=1, padx=20, pady=6)

    def _update_milestone(self, milestone_id, status):
        completed_on = datetime.date.today().isoformat() if status == "Completed" else None
        db.execute("UPDATE tblMilestone SET Status=?, CompletedOn=? WHERE MilestoneID=?",
                   (status, completed_on, milestone_id))
        db.log_activity("Project", self.project_id, "MilestoneUpdated", f"{milestone_id} -> {status}")

    # ---------------- Site Visits ----------------

    def _build_site_visits(self, tab):
        btn_row = ctk.CTkFrame(tab, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(15, 5))
        ctk.CTkButton(btn_row, text="+ Log Site Visit", fg_color=theme.BRASS, hover_color=theme.INK,
                      font=theme.FONT_BODY_BOLD, command=self._open_site_visit_form).pack(side="left")
        ctk.CTkButton(btn_row, text="View Details", fg_color=theme.INK, hover_color=theme.BRASS,
                      font=theme.FONT_BODY, command=self._open_site_visit_details).pack(side="left", padx=(8, 0))

        table_frame = ctk.CTkFrame(tab, fg_color=theme.WHITE)
        table_frame.pack(fill="both", expand=True, padx=20, pady=10)

        cols = ("date", "purpose", "distance", "charge", "status", "notes")
        self.visit_tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=10)
        headings = {"date": "Date", "purpose": "Purpose", "distance": "Distance (km)",
                    "charge": "Charge", "status": "Status", "notes": "Notes"}
        widths = {"date": 100, "purpose": 150, "distance": 110, "charge": 90, "status": 100, "notes": 70}
        for c in cols:
            self.visit_tree.heading(c, text=headings[c])
            self.visit_tree.column(c, width=widths[c])
        self.visit_tree.pack(fill="both", expand=True, side="left")
        self.visit_tree.bind("<Double-1>", lambda e: self._open_site_visit_details())
        self._refresh_site_visits()

    def _refresh_site_visits(self):
        for row in self.visit_tree.get_children():
            self.visit_tree.delete(row)
        visits = db.fetch_all(
            "SELECT * FROM trxSiteVisit WHERE ProjectID=? ORDER BY VisitDate DESC", (self.project_id,))
        for v in visits:
            has_findings = "📝 Yes" if (v["Findings"] or "").strip() else "—"
            self.visit_tree.insert("", "end", iid=v["SiteVisitID"],
                                   values=(v["VisitDate"], v["Purpose"] or "",
                                           v["Distance"] or "", v["Charge"] or "", v["Status"], has_findings))

    def _open_site_visit_form(self):
        SiteVisitForm(self, self.project_id, on_save=self._refresh_site_visits)

    def _open_site_visit_details(self):
        sel = self.visit_tree.selection()
        if not sel:
            messagebox.showinfo("Select a visit", "Please select a site visit from the list first.", parent=self)
            return
        visit = db.fetch_one("SELECT * FROM trxSiteVisit WHERE SiteVisitID=?", (int(sel[0]),))
        SiteVisitDetailsDialog(self, visit)


class SiteVisitForm(ctk.CTkToplevel):
    def __init__(self, master, project_id, on_save):
        super().__init__(master)
        self.project_id = project_id
        self.on_save = on_save
        self.title("Log Site Visit")
        self.geometry("420x680")
        self.configure(fg_color=theme.PARCHMENT)
        self.transient(self.master.winfo_toplevel())
        self.grab_set()

        ctk.CTkLabel(self, text="Visit Date", font=theme.FONT_BODY, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 0))
        self.visit_date_entry = DateEntry(self, width=20, date_pattern="yyyy-mm-dd",
                                          background=theme.BRASS, foreground="white",
                                          borderwidth=1, headersbackground=theme.INK,
                                          headersforeground="white", selectbackground=theme.BRASS)
        self.visit_date_entry.pack(anchor="w", padx=20, pady=(0, 10))

        ctk.CTkLabel(self, text="Purpose", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.purpose_var = ctk.StringVar(value=SITEVISIT_PURPOSE_OPTIONS[0])
        ctk.CTkOptionMenu(self, values=SITEVISIT_PURPOSE_OPTIONS, variable=self.purpose_var, width=250,
                          command=self._on_purpose_change).pack(anchor="w", padx=20, pady=(0, 6))
        self.purpose_other_entry = ctk.CTkEntry(self, width=250, placeholder_text="Specify purpose...")

        row_frame = ctk.CTkFrame(self, fg_color="transparent")
        row_frame.pack(fill="x", padx=20, pady=(4, 10))
        ctk.CTkLabel(row_frame, text="Distance (km)", font=theme.FONT_BODY, text_color=theme.INK).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(row_frame, text="Charge (₹)", font=theme.FONT_BODY, text_color=theme.INK).grid(row=0, column=1, sticky="w", padx=(15, 0))
        self.distance_entry = ctk.CTkEntry(row_frame, width=110)
        self.charge_entry = ctk.CTkEntry(row_frame, width=110)
        apply_decimal_only(self, self.distance_entry)
        apply_decimal_only(self, self.charge_entry)
        self.distance_entry.grid(row=1, column=0)
        self.charge_entry.grid(row=1, column=1, padx=(15, 0))

        # Multi-line -- site observations are rarely one sentence, and the
        # old single-line Entry made this effectively unusable for real notes.
        ctk.CTkLabel(self, text="Findings", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.findings_text = ctk.CTkTextbox(self, width=370, height=120)
        self.findings_text.pack(padx=20, pady=(0, 10))

        ctk.CTkLabel(self, text="Next Action Date", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        ctk.CTkLabel(self, text="(optional -- when the next visit or follow-up is expected)",
                     font=("Segoe UI", 9), text_color=theme.MUTED).pack(anchor="w", padx=20)
        next_action_row = ctk.CTkFrame(self, fg_color="transparent")
        next_action_row.pack(anchor="w", padx=20, pady=(0, 10))
        self.has_next_action_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(next_action_row, text="Set a date", variable=self.has_next_action_var,
                       command=self._toggle_next_action, font=theme.FONT_SMALL).pack(side="left", padx=(0, 10))
        self.next_action_entry = DateEntry(next_action_row, width=18, date_pattern="yyyy-mm-dd",
                                           background=theme.BRASS, foreground="white", borderwidth=1,
                                           headersbackground=theme.INK, headersforeground="white",
                                           selectbackground=theme.BRASS, state="disabled")
        self.next_action_entry.pack(side="left")

        self.status_var = ctk.StringVar(value="Completed")
        ctk.CTkLabel(self, text="Status", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        ctk.CTkOptionMenu(self, values=SITEVISIT_STATUS, variable=self.status_var, width=250).pack(
            anchor="w", padx=20, pady=(0, 15))

        ctk.CTkButton(self, text="Save", command=self.save, fg_color=theme.BRASS,
                      hover_color=theme.INK, font=theme.FONT_BODY_BOLD).pack(pady=10)

    def _on_purpose_change(self, choice):
        if choice == "Other":
            self.purpose_other_entry.pack(anchor="w", padx=20, pady=(0, 6))
        else:
            self.purpose_other_entry.pack_forget()

    def _toggle_next_action(self):
        self.next_action_entry.configure(state="normal" if self.has_next_action_var.get() else "disabled")

    def save(self):
        purpose = self.purpose_other_entry.get().strip() if self.purpose_var.get() == "Other" else self.purpose_var.get()
        findings = self.findings_text.get("1.0", "end").strip()
        next_action_date = self.next_action_entry.get_date().isoformat() if self.has_next_action_var.get() else None
        visit_date = self.visit_date_entry.get_date().isoformat()
        try:
            distance = float(self.distance_entry.get().strip() or 0)
            charge = float(self.charge_entry.get().strip() or 0)
        except ValueError:
            messagebox.showerror("Invalid number", "Distance and Charge must be numbers.", parent=self)
            return
        new_id = db.execute(
            """INSERT INTO trxSiteVisit (ProjectID, VisitDate, Purpose, Findings, NextActionDate,
               Distance, Charge, Status) VALUES (?,?,?,?,?,?,?,?)""",
            (self.project_id, visit_date, purpose, findings,
             next_action_date, distance, charge, self.status_var.get())
        )
        db.log_activity("SiteVisit", new_id, "Created")
        self.on_save()
        self.destroy()


class SiteVisitDetailsDialog(ctk.CTkToplevel):
    """
    Real usability fix: Findings was captured on save but never viewable
    afterward -- not in the table (too long for a column), not anywhere
    else. This is the missing read path, opened via double-click or the
    View Details button.
    """
    def __init__(self, master, visit):
        super().__init__(master)
        self.transient(self.master.winfo_toplevel())
        self.title(f"Site Visit — {visit['VisitDate']}")
        self.geometry("460x520")
        self.configure(fg_color=theme.PARCHMENT)
        self.grab_set()

        ctk.CTkLabel(self, text="Site Visit", font=theme.FONT_SUBHEADING, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 10))

        info_lines = [
            f"Visit Date: {visit['VisitDate']}",
            f"Purpose: {visit['Purpose'] or '-'}",
            f"Distance: {visit['Distance'] or 0} km",
            f"Charge: ₹{visit['Charge'] or 0:,.2f}",
            f"Status: {visit['Status']}",
        ]
        ctk.CTkLabel(self, text="\n".join(info_lines), font=theme.FONT_BODY, text_color=theme.INK,
                    justify="left", anchor="w").pack(anchor="w", padx=20, pady=(0, 10))

        ctk.CTkFrame(self, fg_color=theme.MUTED, height=1).pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(self, text="Findings", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(5, 5))
        findings_box = ctk.CTkTextbox(self, width=400, height=180, fg_color=theme.WHITE)
        findings_box.pack(padx=20, pady=(0, 10))
        findings_box.insert("1.0", visit["Findings"] or "No findings recorded for this visit.")
        findings_box.configure(state="disabled")

        if visit["NextActionDate"]:
            ctk.CTkFrame(self, fg_color=theme.MUTED, height=1).pack(fill="x", padx=20, pady=5)
            ctk.CTkLabel(self, text=f"Next Action Date: {visit['NextActionDate']}", font=theme.FONT_BODY,
                        text_color=theme.INK).pack(anchor="w", padx=20, pady=(5, 15))

        ctk.CTkButton(self, text="Close", command=self.destroy, fg_color=theme.INK,
                     hover_color=theme.BRASS, font=theme.FONT_BODY).pack(pady=10)

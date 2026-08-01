"""
ADS OS Desktop -- Project Screen (Master List, modernized)
Same "Master List" pattern as Clients: real KPI cards, search/filters, a
Card View (primary) and Table View (kept -- architects like information-
dense tables), reusing ui_components.py.

Honest translations from the reference mockup:
  - No project photo thumbnails -- no image storage exists for projects
    anywhere in the schema; a fabricated stock photo would be dishonest.
    Cards use a simple icon banner instead.
  - No "Tasks" count -- no task-management system exists (see
    KNOWN_ISSUES.md). Substituted with Milestones, which is the real
    equivalent concept already tracked.
  - "Progress %" is genuinely computed from real Milestone completion
    (completed / total milestones), not a fabricated or manually-set value.
  - "View Floors/Spaces/Proposals/Invoices" quick-links open the Project
    Workspace directly on the relevant tab (via the new initial_tab
    parameter) instead of always landing on Overview -- a real, incremental
    improvement on the multi-click navigation problem, without the larger
    architecture refactor that's deliberately deferred.
"""
import customtkinter as ctk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
import csv
import os
import datetime
import db
import theme
import ui_components as ui
from constants import apply_decimal_only

STATUS_OPTIONS = ["Lead", "Discussion", "Quotation Sent", "Negotiation", "Confirmed",
                  "Planning", "Approval", "Design", "Working Drawings", "Construction",
                  "Completed", "Cancelled"]
UNIT_OPTIONS = ["Sq.ft.", "Sq.m."]
NO_DEFAULT_PACKAGE = "-- None --"

STATUS_BUCKETS = {
    "Lead": ["Lead", "Discussion", "Quotation Sent", "Negotiation"],
    "Planning": ["Confirmed", "Planning", "Approval"],
    "In Progress": ["Design", "Working Drawings", "Construction"],
    "Completed": ["Completed"],
}
STATUS_COLORS = {"Lead": "#B68100", "Discussion": "#B68100", "Quotation Sent": "#B68100", "Negotiation": "#B68100",
                  "Confirmed": "#1E5FA8", "Planning": "#1E5FA8", "Approval": "#1E5FA8",
                  "Design": "#9B59B6", "Working Drawings": "#9B59B6", "Construction": "#9B59B6",
                  "Completed": "#2E8B57", "Cancelled": "#8B2E2E"}

EXPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Exports")


def get_project_progress(project_id):
    """Real, computed from actual Milestone completion -- never fabricated or manually set."""
    total = db.fetch_one("SELECT COUNT(*) AS n FROM tblMilestone WHERE ProjectID=?", (project_id,))["n"]
    if total == 0:
        return None
    completed = db.fetch_one(
        "SELECT COUNT(*) AS n FROM tblMilestone WHERE ProjectID=? AND Status='Completed'", (project_id,))["n"]
    return int(round(completed / total * 100))


class ProjectScreen(ctk.CTkFrame):
    def __init__(self, master, app=None):
        super().__init__(master, fg_color=theme.PARCHMENT)
        self.app = app  # reference to the App instance, used to keep sidebar's Current Project in sync
        self.view_mode = "card"
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 5))
        title_block = ctk.CTkFrame(header, fg_color="transparent")
        title_block.pack(side="left")
        ctk.CTkLabel(title_block, text="Projects", font=theme.FONT_HEADING, text_color=theme.INK).pack(anchor="w")
        ctk.CTkLabel(title_block, text="Manage all your projects and their progress.",
                    font=theme.FONT_SMALL, text_color=theme.MUTED).pack(anchor="w")

        ctk.CTkButton(header, text="+ New Project", command=self.open_add_form,
                      fg_color=theme.BRASS, hover_color=theme.INK,
                      font=theme.FONT_BODY_BOLD, width=140).pack(side="right")

        # Search moved into the header, matching Clients -- no Bell or Help
        # icons here either: same reasoning as Clients, they had no real
        # function behind them and were just clutter, not reserved space
        # for something concretely planned.
        search_frame = ctk.CTkFrame(header, fg_color=theme.WHITE, corner_radius=8, border_width=1,
                                    border_color=theme.MUTED)
        search_frame.pack(side="right", padx=(0, 20))
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="Search projects by name, code, client...",
                                         width=260, fg_color="transparent", border_width=0)
        self.search_entry.pack(side="left", padx=(10, 4), pady=4)
        self.search_entry.bind("<KeyRelease>", lambda e: self.refresh())
        ctk.CTkLabel(search_frame, text="Ctrl+K", font=("Segoe UI", 9), text_color=theme.MUTED).pack(
            side="left", padx=(0, 10))

        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=20, pady=(8, 6))

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=20, pady=(0, 18))

        self.status_filter_var = ctk.StringVar(value="All Status")
        ctk.CTkOptionMenu(toolbar, values=["All Status"] + STATUS_OPTIONS, variable=self.status_filter_var,
                          width=130, command=lambda c: self.refresh()).pack(side="left", padx=(0, 8))

        sectors = ["All Sectors"] + [s["SectorName"] for s in db.fetch_all("SELECT SectorName FROM mstSector ORDER BY SectorName")]
        self.sector_filter_var = ctk.StringVar(value="All Sectors")
        ctk.CTkOptionMenu(toolbar, values=sectors, variable=self.sector_filter_var,
                          width=130, command=lambda c: self.refresh()).pack(side="left", padx=(0, 8))

        clients = ["All Clients"] + [c["ClientName"] for c in db.fetch_all("SELECT ClientName FROM tblClient ORDER BY ClientName")]
        self.client_filter_var = ctk.StringVar(value="All Clients")
        ctk.CTkOptionMenu(toolbar, values=clients, variable=self.client_filter_var,
                          width=140, command=lambda c: self.refresh()).pack(side="left", padx=(0, 8))

        ctk.CTkButton(toolbar, text="Export", command=self.export_csv, fg_color=theme.MUTED,
                      hover_color=theme.INK, font=theme.FONT_SMALL, width=70, height=28).pack(side="right")
        self.view_toggle = ctk.CTkSegmentedButton(toolbar, values=["Card View", "Table View"],
                                                   command=self._on_view_toggle, fg_color=theme.WHITE,
                                                   selected_color=theme.BRASS, unselected_color=theme.WHITE,
                                                   text_color=theme.INK, selected_hover_color=theme.INK)
        self.view_toggle.set("Card View")
        self.view_toggle.pack(side="right", padx=(0, 10))

        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    def _on_view_toggle(self, choice):
        self.view_mode = "card" if choice == "Card View" else "table"
        self.refresh()

    def _get_filtered_projects(self):
        search = self.search_entry.get().strip().lower()
        status_filter = self.status_filter_var.get()
        sector_filter = self.sector_filter_var.get()
        client_filter = self.client_filter_var.get()

        projects = db.fetch_all("""
            SELECT p.*, c.ClientName, c.Priority AS ClientPriority, sec.SectorName, svc.ServiceName
            FROM tblProject p
            JOIN tblClient c ON p.ClientID = c.ClientID
            LEFT JOIN mstSector sec ON p.SectorID = sec.SectorID
            LEFT JOIN mstService svc ON p.ServiceID = svc.ServiceID
            ORDER BY p.ProjectID DESC
        """)
        if search:
            projects = [p for p in projects if search in p["ProjectName"].lower()
                       or search in p["ProjectCode"].lower() or search in p["ClientName"].lower()]
        if status_filter != "All Status":
            projects = [p for p in projects if p["ProjectStatus"] == status_filter]
        if sector_filter != "All Sectors":
            projects = [p for p in projects if p["SectorName"] == sector_filter]
        if client_filter != "All Clients":
            projects = [p for p in projects if p["ClientName"] == client_filter]
        return projects

    def refresh(self):
        self._render_stats()
        for w in self.content_frame.winfo_children():
            w.destroy()
        projects = self._get_filtered_projects()

        if not projects:
            ctk.CTkLabel(self.content_frame, text="No projects match this search/filter.",
                        font=theme.FONT_BODY, text_color=theme.MUTED).pack(pady=20)
            return

        if self.view_mode == "card":
            self._render_card_view(projects)
        else:
            self._render_table_view(projects)

    def _render_stats(self):
        for w in self.stats_frame.winfo_children():
            w.destroy()
        all_projects = db.fetch_all("SELECT ProjectStatus FROM tblProject")
        total = len(all_projects)
        active = sum(1 for p in all_projects if p["ProjectStatus"] not in ("Completed", "Cancelled"))

        bucket_counts = {bucket: 0 for bucket in STATUS_BUCKETS}
        for p in all_projects:
            for bucket, statuses in STATUS_BUCKETS.items():
                if p["ProjectStatus"] in statuses:
                    bucket_counts[bucket] += 1
                    break

        def pct(n):
            return f"{int(round(n / total * 100))}% of total" if total else "0% of total"

        stats = [
            (str(total), "Total Projects", "All Time", "📁", "#F5E6D3"),
            (str(active), "Active Projects", pct(active), "✅", "#D4F0E0"),
            (str(bucket_counts["Lead"]), "Lead", pct(bucket_counts["Lead"]), "✏️", "#D6E8FA"),
            (str(bucket_counts["In Progress"]), "In Progress", pct(bucket_counts["In Progress"]), "⚙️", "#FBE0E0"),
            (str(bucket_counts["Completed"]), "Completed", pct(bucket_counts["Completed"]), "✔️", "#E8DFF5"),
        ]
        # Weighted grid matching Clients -- cards stay the same size, but
        # sit in equally-expanding columns so gutters grow to fill the
        # available width instead of sitting bunched together on the left.
        for col in range(5):
            self.stats_frame.grid_columnconfigure(col, weight=1)
        for col_idx, (value, label, sublabel, icon, bg_color) in enumerate(stats):
            ui.kpi_card(self.stats_frame, value, label, sublabel, icon, bg_color, col_idx)

    def _render_card_view(self, projects):
        scroll = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        for p in projects:
            self._render_project_card(scroll, p)

    def _render_project_card(self, parent, p):
        card = ctk.CTkFrame(parent, fg_color=theme.WHITE, corner_radius=10, border_width=1, border_color="#E8E0D0")
        card.pack(fill="x", pady=(0, 12))

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=15, pady=10)

        # Icon in a colored box (matching the client card's monogram
        # treatment) instead of a bare emoji in a separate banner strip --
        # no real project image exists anywhere in this schema, so this is
        # a styled real icon, not a fabricated photo standing in for one.
        header_row = ctk.CTkFrame(body, fg_color="transparent")
        header_row.pack(fill="x")
        icon_box = ctk.CTkLabel(header_row, text="🏗", font=("Segoe UI", 18), fg_color="#F5E6D3",
                                corner_radius=10, width=44, height=44)
        icon_box.pack(side="left", padx=(0, 12))

        title_block = ctk.CTkFrame(header_row, fg_color="transparent")
        title_block.pack(side="left", fill="x", expand=True)
        code_row = ctk.CTkFrame(title_block, fg_color="transparent")
        code_row.pack(anchor="w")
        ui.pill_badge(code_row, p["ProjectCode"], "#8B5A2B").pack(side="left")
        ctk.CTkLabel(title_block, text=p["ProjectName"], font=("Segoe UI", 17, "bold"), text_color=theme.INK,
                    anchor="w").pack(fill="x", pady=(2, 0))
        ctk.CTkLabel(title_block, text=f"👤 {p['ClientName']}", font=theme.FONT_SMALL, text_color=theme.INK,
                    anchor="w").pack(fill="x", pady=(2, 0))

        info_line = f"🏢 {p['SectorName'] or '—'}  ·  🎯 {p['ServiceName'] or '—'}  ·  📐 {p['TotalBuiltUpArea']} {p['Unit']}"
        ctk.CTkLabel(body, text=info_line, font=theme.FONT_SMALL, text_color=theme.MUTED, anchor="w").pack(
            fill="x", pady=(6, 0))

        badges = ctk.CTkFrame(body, fg_color="transparent")
        badges.pack(fill="x", pady=(6, 0))
        status_color = STATUS_COLORS.get(p["ProjectStatus"], "#6B6B6B")
        ui.pill_badge(badges, p["ProjectStatus"], status_color).pack(side="left", padx=(0, 8))
        if p["ClientPriority"] and p["ClientPriority"] != "Normal":
            priority_color = "#B68100" if p["ClientPriority"] == "VIP" else "#1E5FA8"
            ui.pill_badge(badges, f"Client: {p['ClientPriority']}", priority_color).pack(side="left", padx=(0, 8))

        # Real schedule chip -- ExpectedCompletion is a genuine field on
        # every project, so "On Schedule"/"Delayed" is an honest comparison
        # against today's date, not a fabricated status. Shown only when
        # ExpectedCompletion is actually set and the project isn't already
        # finished -- no chip at all when there's no real date to compare
        # against, rather than guessing.
        if p["ExpectedCompletion"] and p["ProjectStatus"] not in ("Completed", "Cancelled"):
            try:
                expected = datetime.date.fromisoformat(p["ExpectedCompletion"][:10])
                if datetime.date.today() > expected:
                    ui.pill_badge(badges, "🔴 Delayed", "#8B2E2E").pack(side="left")
                else:
                    ui.pill_badge(badges, "🟢 On Schedule", "#2E8B57").pack(side="left")
            except (ValueError, TypeError):
                pass  # malformed date data -- skip the chip rather than guess

        progress = get_project_progress(p["ProjectID"])
        progress_row = ctk.CTkFrame(body, fg_color="transparent")
        progress_row.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(progress_row, text="Progress", font=theme.FONT_SMALL, text_color=theme.MUTED, width=55,
                    anchor="w").pack(side="left")
        if progress is not None:
            bar = ctk.CTkProgressBar(progress_row, height=8, progress_color=theme.BRASS, fg_color=theme.PARCHMENT)
            bar.set(progress / 100)
            bar.pack(side="left", fill="x", expand=True, padx=(8, 8))
            ctk.CTkLabel(progress_row, text=f"{progress}%", font=("Segoe UI", 12, "bold"), text_color=theme.INK,
                        width=35).pack(side="left")
        else:
            ctk.CTkLabel(progress_row, text="No milestones yet", font=theme.FONT_SMALL, text_color=theme.MUTED).pack(
                side="left", padx=(8, 0))

        dates_row = ctk.CTkFrame(body, fg_color="transparent")
        dates_row.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(dates_row, text=f"Created: {p['CreatedOn'][:10] if p['CreatedOn'] else '—'}",
                    font=("Segoe UI", 9), text_color=theme.MUTED).pack(side="left")
        ctk.CTkLabel(dates_row, text=f"Updated: {p['ModifiedOn'][:10] if p['ModifiedOn'] else '—'}",
                    font=("Segoe UI", 9), text_color=theme.MUTED).pack(side="right")

        floors_n = db.fetch_one("SELECT COUNT(*) AS n FROM tblFloor WHERE ProjectID=?", (p["ProjectID"],))["n"]
        spaces_n = db.fetch_one(
            "SELECT COUNT(*) AS n FROM tblRoom r JOIN tblFloor f ON r.FloorID=f.FloorID WHERE f.ProjectID=?",
            (p["ProjectID"],))["n"]
        proposals_n = db.fetch_one("SELECT COUNT(*) AS n FROM trxProposal WHERE ProjectID=?", (p["ProjectID"],))["n"]
        invoices_n = db.fetch_one("SELECT COUNT(*) AS n FROM trxInvoice WHERE ProjectID=?", (p["ProjectID"],))["n"]
        milestones_n = db.fetch_one("SELECT COUNT(*) AS n FROM tblMilestone WHERE ProjectID=?", (p["ProjectID"],))["n"]

        counts_row = ctk.CTkFrame(card, fg_color=theme.PARCHMENT, corner_radius=8)
        counts_row.pack(fill="x", padx=15, pady=(8, 10))
        quick_links = [
            ("📋", floors_n, "Floors", "Planning"), ("🧩", spaces_n, "Spaces", "Planning"),
            ("📝", proposals_n, "Proposals", "Commercial"), ("🧾", invoices_n, "Invoices", "Commercial"),
            ("✅", milestones_n, "Milestones", "Overview"),
        ]
        # Packed as a centered cluster with generous internal gutters,
        # rather than stretched with grid weights across the full card
        # width -- weighted stretching is exactly what made this feel like
        # 5 separate islands on a wide card. expand=True on a pack() call
        # centers the cluster's own natural width within the available
        # space, the same technique already used for Dashboard's donut+
        # legend grouping.
        cluster = ctk.CTkFrame(counts_row, fg_color="transparent")
        cluster.pack(expand=True, pady=10)
        for icon, count, label, tab in quick_links:
            box = ctk.CTkFrame(cluster, fg_color="transparent")
            box.pack(side="left", padx=22)
            ctk.CTkLabel(box, text=f"{icon} {count}", font=("Georgia", 15, "bold"), text_color=theme.INK).pack()
            link = ctk.CTkLabel(box, text=label, font=("Segoe UI", 9, "underline"), text_color="#1E5FA8",
                                cursor="hand2")
            link.pack()
            link.bind("<Button-1>", lambda e, pid=p["ProjectID"], t=tab: self.open_workspace_for(pid, t))

        # Actions rebalanced with genuine weight, not just color -- matching
        # the same Open/Edit/Delete hierarchy established for Clients: Open
        # Workspace is the dominant, primary action; Details is secondary;
        # Delete is a small, fixed-width outline that doesn't compete with
        # either for attention.
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=15, pady=(0, 15))
        actions.grid_columnconfigure(0, weight=3)
        actions.grid_columnconfigure(1, weight=2)
        ctk.CTkButton(actions, text="Open Workspace  →", command=lambda pid=p["ProjectID"]: self.open_workspace_for(pid),
                      fg_color=theme.BRASS, hover_color=theme.INK, font=("Segoe UI", 12, "bold"), height=34).grid(
            row=0, column=0, sticky="ew", padx=(0, 5))
        ctk.CTkButton(actions, text="Details", command=lambda pid=p["ProjectID"]: self.open_edit_form_for(pid),
                      fg_color=theme.INK, hover_color=theme.BRASS, font=theme.FONT_SMALL, height=34).grid(
            row=0, column=1, sticky="ew", padx=(0, 5))
        ctk.CTkButton(actions, text="🗑", command=lambda pid=p["ProjectID"]: self.delete_project(pid),
                      fg_color="transparent", hover_color="#8B2E2E", text_color="#8B2E2E",
                      border_width=1, border_color="#8B2E2E", font=theme.FONT_SMALL, height=34, width=40).grid(
            row=0, column=2)

    def _render_table_view(self, projects):
        table_frame = ctk.CTkFrame(self.content_frame, fg_color=theme.WHITE)
        table_frame.pack(fill="both", expand=True)
        cols = ("code", "name", "client", "sector", "service", "status", "area", "progress")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=18)
        headings = {"code": "Project Code", "name": "Project Name", "client": "Client",
                    "sector": "Sector", "service": "Service", "status": "Status", "area": "Built-up Area",
                    "progress": "Progress"}
        widths = {"code": 100, "name": 160, "client": 130, "sector": 100, "service": 120, "status": 110,
                  "area": 100, "progress": 80}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c])
        for status, color in STATUS_COLORS.items():
            self.tree.tag_configure(f"status_{status}", foreground=color)
        self.tree.bind("<Double-1>", lambda e: self.open_workspace())

        hscrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscroll=hscrollbar.set)
        hscrollbar.pack(side="bottom", fill="x")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self.tree.pack(fill="both", expand=True, side="left")

        for p in projects:
            progress = get_project_progress(p["ProjectID"])
            self.tree.insert("", "end", iid=p["ProjectID"],
                             values=(p["ProjectCode"], p["ProjectName"], p["ClientName"], p["SectorName"] or "-",
                                    p["ServiceName"] or "-", p["ProjectStatus"], f"{p['TotalBuiltUpArea']} {p['Unit']}",
                                    f"{progress}%" if progress is not None else "-"),
                             tags=(f"status_{p['ProjectStatus']}",))

        footer = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        footer.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(footer, text="Open Workspace", command=self.open_workspace,
                      fg_color=theme.BRASS, hover_color=theme.INK, font=theme.FONT_SMALL, height=28).pack(
            side="left", padx=(0, 8))
        ctk.CTkButton(footer, text="Edit Selected", command=self.open_edit_form,
                      fg_color=theme.INK, font=theme.FONT_SMALL, height=28).pack(side="left", padx=(0, 8))
        ctk.CTkButton(footer, text="Delete Selected", command=self.delete_selected,
                      fg_color="#8B2E2E", hover_color="#5E1F1F", font=theme.FONT_SMALL, height=28).pack(side="left")

    def export_csv(self):
        projects = self._get_filtered_projects()
        if not projects:
            messagebox.showinfo("Nothing to export", "No projects match the current search/filter.", parent=self)
            return
        os.makedirs(EXPORTS_DIR, exist_ok=True)
        filename = f"Projects_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path = os.path.join(EXPORTS_DIR, filename)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Project Code", "Project Name", "Client", "Sector", "Service", "Status",
                             "Built-up Area", "Unit", "Progress %", "Created On"])
            for p in projects:
                progress = get_project_progress(p["ProjectID"])
                writer.writerow([p["ProjectCode"], p["ProjectName"], p["ClientName"], p["SectorName"] or "-",
                                 p["ServiceName"] or "-", p["ProjectStatus"], p["TotalBuiltUpArea"], p["Unit"],
                                 progress if progress is not None else "-", p["CreatedOn"]])
        messagebox.showinfo("Exported", f"Saved to:\n{path}", parent=self)

    def _selected_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select a project", "Please select a project from the list first.", parent=self)
            return None
        return int(sel[0])

    def open_add_form(self):
        clients = db.fetch_all("SELECT ClientID, ClientName FROM tblClient ORDER BY ClientName")
        if not clients:
            messagebox.showwarning("No clients yet", "Add at least one client before creating a project.", parent=self)
            return
        ProjectForm(self, on_save=self.refresh)

    def open_edit_form(self):
        project_id = self._selected_id()
        if project_id is None:
            return
        self.open_edit_form_for(project_id)

    def open_edit_form_for(self, project_id):
        project = db.fetch_one("SELECT * FROM tblProject WHERE ProjectID = ?", (project_id,))
        ProjectForm(self, on_save=self.refresh, existing=project)

    def open_workspace(self):
        project_id = self._selected_id()
        if project_id is None:
            return
        self.open_workspace_for(project_id)

    def open_workspace_for(self, project_id, initial_tab=None):
        from project_workspace import ProjectWorkspace
        if self.app:
            self.app.set_current_project(project_id)
        ProjectWorkspace(self, project_id, on_close=self.refresh, initial_tab=initial_tab)

    def delete_selected(self):
        project_id = self._selected_id()
        if project_id is None:
            return
        self.delete_project(project_id)

    def delete_project(self, project_id):
        in_use = db.fetch_one("SELECT COUNT(*) AS n FROM tblFloor WHERE ProjectID = ?", (project_id,))
        if in_use["n"] > 0:
            messagebox.showerror("Cannot delete",
                                  "This project has floors/rooms defined. Remove those first.", parent=self)
            return
        if messagebox.askyesno("Confirm delete",
                                "Delete this project permanently? This also removes its milestones and "
                                "site visit history.", parent=self):
            db.execute("DELETE FROM tblMilestone WHERE ProjectID = ?", (project_id,))
            db.execute("DELETE FROM trxSiteVisit WHERE ProjectID = ?", (project_id,))
            db.execute("DELETE FROM tblProject WHERE ProjectID = ?", (project_id,))
            db.log_activity("Project", project_id, "Deleted")
            self.refresh()

class ProjectForm(ctk.CTkToplevel):
    def __init__(self, master, on_save, existing=None):
        super().__init__(master)
        self.on_save = on_save
        self.existing = existing
        self.title("Edit Project" if existing else "New Project")
        self.geometry("560x700")
        self.configure(fg_color=theme.PARCHMENT)
        self.grab_set()

        # Scrollable content -- this form has 12+ fields and will not fit most
        # screen heights without it.
        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=5, pady=5)

        self.clients = db.fetch_all(
            "SELECT ClientID, ClientName, Address, City, State, Country FROM tblClient ORDER BY ClientName")
        self.sectors = db.fetch_all("SELECT SectorID, SectorName FROM mstSector WHERE Active=1 ORDER BY SectorName")
        self.services = db.fetch_all("SELECT ServiceID, ServiceName FROM mstService WHERE Active=1 ORDER BY ServiceName")
        self.packages = db.fetch_all(
            "SELECT PackageID, PackageName, Rate, MinimumFee FROM mstPackage WHERE Active=1 ORDER BY Rate")

        client_names = [c["ClientName"] for c in self.clients]
        package_names = [NO_DEFAULT_PACKAGE] + [p["PackageName"] for p in self.packages]
        SECTOR_PLACEHOLDER = "-- Select Sector --"
        SERVICE_PLACEHOLDER = "-- Select Service --"

        row = 0
        ctk.CTkLabel(content, text=self.title(), font=theme.FONT_SUBHEADING,
                     text_color=theme.INK).grid(row=row, column=0, columnspan=2, pady=(15, 10), padx=15, sticky="w")
        row += 1

        # Client dropdown -- triggers address carry-forward on change
        ctk.CTkLabel(content, text="Client *", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        default_client = next((c["ClientName"] for c in self.clients if existing and c["ClientID"] == existing["ClientID"]),
                               client_names[0] if client_names else "")
        self.client_var = ctk.StringVar(value=default_client)
        ctk.CTkOptionMenu(content, values=client_names, variable=self.client_var, width=280,
                          command=self._on_client_change).grid(row=row, column=1, padx=15, pady=6)
        row += 1

        ctk.CTkLabel(content, text="Project Name *", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        self.name_entry = ctk.CTkEntry(content, width=280)
        self.name_entry.grid(row=row, column=1, padx=15, pady=6)
        if existing:
            self.name_entry.insert(0, existing["ProjectName"])
        row += 1

        # Same-as-client-address checkbox
        client = self._selected_client()
        same_as_client_default = True
        if existing and client:
            same_as_client_default = (
                (existing["SiteAddress"] or "") == (client["Address"] or "") and
                (existing["City"] or "") == (client["City"] or "") and
                (existing["State"] or "") == (client["State"] or "") and
                (existing["Country"] or "") == (client["Country"] or "")
            )
        self.same_address_var = ctk.BooleanVar(value=same_as_client_default)
        ctk.CTkCheckBox(content, text="Same as Client's Residence", variable=self.same_address_var,
                        command=self._toggle_address_fields, font=theme.FONT_BODY,
                        text_color=theme.INK).grid(row=row, column=0, columnspan=2, sticky="w", padx=15, pady=(10, 4))
        row += 1

        self.address_entries = {}
        addr_fields = [("SiteAddress", "Site Address"), ("City", "City"),
                       ("State", "State"), ("Country", "Country")]
        for field, label in addr_fields:
            ctk.CTkLabel(content, text=label, font=theme.FONT_BODY, text_color=theme.INK).grid(
                row=row, column=0, sticky="w", padx=15, pady=6)
            entry = ctk.CTkEntry(content, width=280)
            entry.grid(row=row, column=1, padx=15, pady=6)
            if existing and existing[field]:
                entry.insert(0, str(existing[field]))
            self.address_entries[field] = entry
            row += 1

        ctk.CTkLabel(content, text="Total Built-up Area", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        self.area_entry = ctk.CTkEntry(content, width=280)
        apply_decimal_only(self, self.area_entry)
        self.area_entry.grid(row=row, column=1, padx=15, pady=6)
        if existing:
            self.area_entry.insert(0, str(existing["TotalBuiltUpArea"]))
        row += 1

        # Start Date -- dropdown calendar (tkcalendar DateEntry)
        ctk.CTkLabel(content, text="Start Date", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        self.start_date_entry = DateEntry(content, width=25, date_pattern="yyyy-mm-dd",
                                          background=theme.BRASS, foreground="white",
                                          borderwidth=1, headersbackground=theme.INK,
                                          headersforeground="white", selectbackground=theme.BRASS)
        if existing and existing["StartDate"]:
            try:
                self.start_date_entry.set_date(existing["StartDate"])
            except Exception:
                pass
        self.start_date_entry.grid(row=row, column=1, padx=15, pady=6, sticky="w")
        row += 1

        # Expected Completion -- previously removed from this form (see
        # prior comment history), but the "On Schedule"/"Delayed" status
        # chip added since then genuinely depends on this field being
        # real, user-settable data, not something only editable by hand in
        # the database. Re-added specifically because a real feature now
        # needs it; optional (blank means the chip simply doesn't show,
        # never a guessed date).
        ctk.CTkLabel(content, text="Expected Completion", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        completion_row = ctk.CTkFrame(content, fg_color="transparent")
        completion_row.grid(row=row, column=1, padx=15, pady=6, sticky="w")
        has_completion_date = bool(existing and existing["ExpectedCompletion"])
        self.completion_enabled_var = ctk.BooleanVar(value=has_completion_date)
        self.completion_date_entry = DateEntry(completion_row, width=22, date_pattern="yyyy-mm-dd",
                                               background=theme.BRASS, foreground="white", borderwidth=1,
                                               headersbackground=theme.INK, headersforeground="white",
                                               selectbackground=theme.BRASS,
                                               state="normal" if has_completion_date else "disabled")
        if has_completion_date:
            try:
                self.completion_date_entry.set_date(existing["ExpectedCompletion"])
            except Exception:
                pass
        def _toggle_completion():
            self.completion_date_entry.configure(state="normal" if self.completion_enabled_var.get() else "disabled")
        ctk.CTkCheckBox(completion_row, text="Set a date", variable=self.completion_enabled_var,
                       command=_toggle_completion, font=theme.FONT_SMALL, width=20).pack(side="left", padx=(0, 8))
        self.completion_date_entry.pack(side="left")
        row += 1

        ctk.CTkLabel(content, text="Remarks", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        self.remarks_entry = ctk.CTkEntry(content, width=280)
        self.remarks_entry.grid(row=row, column=1, padx=15, pady=6)
        if existing and existing["Remarks"]:
            self.remarks_entry.insert(0, existing["Remarks"])
        row += 1

        # Sector -- "what kind of project is this" (Residential, Healthcare, Airport...)
        ctk.CTkLabel(content, text="Sector *", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        default_sector = next((s["SectorName"] for s in self.sectors if existing and s["SectorID"] == existing["SectorID"]),
                              None)
        if default_sector is None:
            default_sector = SECTOR_PLACEHOLDER if not existing else (self.sectors[0]["SectorName"] if self.sectors else "")
        sector_values = ([SECTOR_PLACEHOLDER] if not existing else []) + [s["SectorName"] for s in self.sectors]
        self.sector_var = ctk.StringVar(value=default_sector)
        ctk.CTkOptionMenu(content, values=sector_values, variable=self.sector_var, width=280).grid(row=row, column=1, padx=15, pady=6)
        row += 1

        # Service -- "what we're doing" (Architectural Design, Interior Design, Renovation...)
        ctk.CTkLabel(content, text="Service *", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        default_service = next((s["ServiceName"] for s in self.services if existing and s["ServiceID"] == existing["ServiceID"]),
                               None)
        if default_service is None:
            default_service = SERVICE_PLACEHOLDER if not existing else (self.services[0]["ServiceName"] if self.services else "")
        service_values = ([SERVICE_PLACEHOLDER] if not existing else []) + [s["ServiceName"] for s in self.services]
        self.service_var = ctk.StringVar(value=default_service)
        ctk.CTkOptionMenu(content, values=service_values, variable=self.service_var, width=280).grid(row=row, column=1, padx=15, pady=6)
        row += 1

        # Unit dropdown
        ctk.CTkLabel(content, text="Unit", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        self.unit_var = ctk.StringVar(value=(existing["Unit"] if existing else "Sq.ft."))
        ctk.CTkOptionMenu(content, values=UNIT_OPTIONS, variable=self.unit_var, width=280).grid(row=row, column=1, padx=15, pady=6)
        row += 1

        # Package section: dropdown + live Rate/Min Fee display
        ctk.CTkLabel(content, text="Package", font=theme.FONT_BODY_BOLD, text_color=theme.INK).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=15, pady=(14, 2))
        row += 1

        ctk.CTkLabel(content, text="Default Package", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        default_pkg_name = NO_DEFAULT_PACKAGE
        if existing and existing["DefaultPackageID"]:
            default_pkg_name = next((p["PackageName"] for p in self.packages
                                      if p["PackageID"] == existing["DefaultPackageID"]), NO_DEFAULT_PACKAGE)
        self.package_var = ctk.StringVar(value=default_pkg_name)
        ctk.CTkOptionMenu(content, values=package_names, variable=self.package_var, width=280,
                          command=self._on_package_change).grid(row=row, column=1, padx=15, pady=6)
        row += 1

        self.package_info_label = ctk.CTkLabel(content, text="", font=theme.FONT_SMALL, text_color=theme.MUTED,
                                               justify="left")
        self.package_info_label.grid(row=row, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 6))
        row += 1

        # Status dropdown
        ctk.CTkLabel(content, text="Status", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        self.status_var = ctk.StringVar(value=(existing["ProjectStatus"] if existing else "Lead"))
        ctk.CTkOptionMenu(content, values=STATUS_OPTIONS, variable=self.status_var, width=280).grid(row=row, column=1, padx=15, pady=6)
        row += 1

        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.grid(row=row, column=0, columnspan=2, pady=20)
        ctk.CTkButton(btn_frame, text="Save", command=self.save,
                      fg_color=theme.BRASS, hover_color=theme.INK,
                      font=theme.FONT_BODY_BOLD, width=120).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Cancel", command=self.destroy,
                      fg_color=theme.MUTED, font=theme.FONT_BODY, width=120).pack(side="left", padx=10)

        self._toggle_address_fields()
        self._on_package_change(default_pkg_name)

    def _selected_client(self):
        name = self.client_var.get()
        return next((c for c in self.clients if c["ClientName"] == name), None)

    def _on_client_change(self, _choice=None):
        # Bug fix: previously called _fill_address_from_client() directly, which
        # temporarily sets fields to "normal" to insert text and never restored
        # "disabled" afterward -- so switching clients silently unlocked the
        # address fields even while the checkbox stayed checked. Routing through
        # _toggle_address_fields() ensures the disabled state is reapplied.
        self._toggle_address_fields()

    def _fill_address_from_client(self):
        client = self._selected_client()
        if not client:
            return
        mapping = {"SiteAddress": client["Address"], "City": client["City"],
                   "State": client["State"], "Country": client["Country"]}
        for field, value in mapping.items():
            entry = self.address_entries[field]
            entry.configure(state="normal")
            entry.delete(0, "end")
            if value:
                entry.insert(0, value)

    def _toggle_address_fields(self):
        if self.same_address_var.get():
            self._fill_address_from_client()
            for entry in self.address_entries.values():
                entry.configure(state="disabled")
        else:
            for entry in self.address_entries.values():
                entry.configure(state="normal")

    def _on_package_change(self, choice):
        if choice == NO_DEFAULT_PACKAGE:
            self.package_info_label.configure(text="")
            return
        pkg = next((p for p in self.packages if p["PackageName"] == choice), None)
        if pkg:
            self.package_info_label.configure(
                text=f"Rate: ₹{pkg['Rate']}/sq.ft.   ·   Minimum Fee: ₹{pkg['MinimumFee']}")

    def save(self):
        name = self.name_entry.get().strip()
        missing = []
        if not name:
            missing.append("Project Name")
        if self.sector_var.get() == "-- Select Sector --":
            missing.append("Sector")
        if self.service_var.get() == "-- Select Service --":
            missing.append("Service")
        if missing:
            messagebox.showerror("Missing required fields", "Please fill in: " + ", ".join(missing), parent=self)
            return
        try:
            area = float(self.area_entry.get().strip() or 0)
        except ValueError:
            messagebox.showerror("Invalid area", "Total Built-up Area must be a number.", parent=self)
            return

        client_id = next(c["ClientID"] for c in self.clients if c["ClientName"] == self.client_var.get())
        sector_id = next(s["SectorID"] for s in self.sectors if s["SectorName"] == self.sector_var.get())
        service_id = next(s["ServiceID"] for s in self.services if s["ServiceName"] == self.service_var.get())
        # Legacy ProjectTypeID column still has a NOT NULL constraint from before
        # the Sector/Service split -- resolve it from the chosen Sector (names
        # match 1:1) purely to satisfy that constraint. No app logic reads this
        # column anymore; SectorID/ServiceID are the real source of truth.
        legacy_type = db.fetch_one("SELECT ProjectTypeID FROM mstProjectType WHERE ProjectType=?", (self.sector_var.get(),))
        legacy_type_id = legacy_type["ProjectTypeID"] if legacy_type else 1

        pkg_name = self.package_var.get()
        default_package_id = None
        if pkg_name != NO_DEFAULT_PACKAGE:
            default_package_id = next(p["PackageID"] for p in self.packages if p["PackageName"] == pkg_name)

        addr = {f: self.address_entries[f].get().strip() for f in
                ["SiteAddress", "City", "State", "Country"]}
        start_date = self.start_date_entry.get_date().isoformat()
        # NULL unless the checkbox is actually checked -- never persist a
        # date the user didn't genuinely set, same pattern as Client's
        # NextFollowUpDate field.
        expected_completion = self.completion_date_entry.get_date().isoformat() if self.completion_enabled_var.get() else None
        remarks = self.remarks_entry.get().strip()

        if self.existing:
            db.execute(
                """UPDATE tblProject SET ClientID=?, ProjectName=?, ProjectTypeID=?, SectorID=?, ServiceID=?,
                   Unit=?, ProjectStatus=?, SiteAddress=?, City=?, State=?, Country=?, TotalBuiltUpArea=?,
                   StartDate=?, ExpectedCompletion=?, DefaultPackageID=?, Remarks=?, ModifiedOn=datetime('now')
                   WHERE ProjectID=?""",
                (client_id, name, legacy_type_id, sector_id, service_id, self.unit_var.get(), self.status_var.get(),
                 addr["SiteAddress"], addr["City"], addr["State"], addr["Country"], area,
                 start_date, expected_completion, default_package_id, remarks, self.existing["ProjectID"])
            )
            db.log_activity("Project", self.existing["ProjectID"], "Updated")
        else:
            code = db.next_code("ADS-PRJ", "tblProject", "ProjectCode")
            new_id = db.execute(
                """INSERT INTO tblProject (ProjectCode, ClientID, ProjectName, ProjectTypeID, SectorID, ServiceID, Unit,
                   ProjectStatus, SiteAddress, City, State, Country, TotalBuiltUpArea, StartDate, ExpectedCompletion,
                   DefaultPackageID, Remarks)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (code, client_id, name, legacy_type_id, sector_id, service_id, self.unit_var.get(), self.status_var.get(),
                 addr["SiteAddress"], addr["City"], addr["State"], addr["Country"], area,
                 start_date, expected_completion, default_package_id, remarks)
            )
            db.log_activity("Project", new_id, "Created")
            db.seed_milestones_for_project(new_id)

        self.on_save()
        self.destroy()

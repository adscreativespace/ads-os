"""
ADS OS Desktop -- Contractor Master (Phase 1 of the Contractor Module)
A genuine first-class master entity, deliberately separate from Vendors --
an explicit business decision, not a database-normalization exercise.
Contractors represent execution partners (masons, electricians, plumbers,
fabricators) whose business revolves around labour, scope of work, and
running bills -- a fundamentally different workflow from Vendors, who
supply materials.

Built independently, not as a thin wrapper reusing VendorsPanel's code, per
explicit instruction: if separating, separate them properly.

Phase 1 scope: Master + CRUD (add/edit/archive), Scope of Work (reusing the
existing mstScopeOfWork master, since "Civil Works" or "Flooring" as a
concept doesn't change depending on which master owns it), search/filter,
soft delete. Deliberately NOT built in this phase: Running Bills,
Measurements, Performance scorecards, Contractor Reports, a dedicated
Contractor Dashboard -- each is real, planned future work, scoped as its
own phase the same way Commercial itself was built module by module rather
than all at once.
"""
import customtkinter as ctk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
import re
import db
import theme
import ui_components as ui
from constants import apply_numeric_only, apply_decimal_only
from contract_panel import get_contract_status

TRADE_OPTIONS = ["Mason", "Carpenter", "Bar Bender", "Electrician", "Plumber", "Painter",
                 "POP Contractor", "Fabricator", "Aluminium Fabricator", "Tile Fixer",
                 "Marble Contractor", "False Ceiling Contractor", "Interior Contractor",
                 "HVAC Contractor", "Waterproofing Contractor", "Landscape Contractor",
                 "Civil Contractor", "Labour Supplier", "Others"]
CONTRACTOR_STATUS_OPTIONS = ["Active", "Inactive", "Archived"]
STATUS_COLORS = {"Active": "#2E8B57", "Inactive": "#6B6B6B", "Archived": "#8B2E2E"}

SCOPE_GROUPS = {
    "Furniture": ["Furniture", "Furniture Polishing", "Modular Kitchen"],
    "Ceiling": ["False Ceiling", "POP Ceiling", "PVC Ceiling"],
    "Flooring": ["Flooring", "Marble", "Granite"],
    "Civil": ["Civil Works", "Brick Work", "Demolition", "Waterproofing"],
    "Finishing": ["Painting", "Plaster", "Cleaning"],
    "MEP": ["Electrical", "Plumbing", "HVAC"],
    "Fabrication": ["Aluminium", "Glass", "Steel Fabrication", "MS Fabrication", "SS Fabrication"],
    "Other": ["Signage", "Landscaping"],
}


def contractor_financials(contractor_id):
    """
    Real, computed (total_value, total_paid, outstanding, project_count)
    for a contractor -- single source of truth, used by both the list
    screen's Quick Profile and the full Workspace, so a fix here applies
    everywhere instead of two screens quietly drifting apart.
    """
    contracts = db.fetch_all("SELECT ContractID, ContractAmount, ProjectID FROM trxContract WHERE ContractorID=?",
                             (contractor_id,))
    total_value = sum(ct["ContractAmount"] for ct in contracts if ct["ContractAmount"] is not None)
    total_paid = sum(db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxContractPayment WHERE ContractID=?",
                                  (ct["ContractID"],))["t"] for ct in contracts)
    project_count = len({ct["ProjectID"] for ct in contracts if ct["ProjectID"] is not None})
    return total_value, total_paid, total_value - total_paid, project_count


def contractor_last_payment(contractor_id):
    """Real last payment (amount, date) across all this contractor's contracts, or (None, None) if none yet."""
    row = db.fetch_one("""
        SELECT cp.Amount, cp.PaymentDate FROM trxContractPayment cp
        JOIN trxContract c ON cp.ContractID = c.ContractID
        WHERE c.ContractorID = ? ORDER BY cp.PaymentDate DESC LIMIT 1
    """, (contractor_id,))
    return (row["Amount"], row["PaymentDate"]) if row else (None, None)


class ContractorsPanel(ctk.CTkFrame):
    def __init__(self, master, project_id):
        super().__init__(master, fg_color="transparent")
        # Accepted for consistency with how CommercialPanel._on_switch()
        # constructs every module uniformly -- not actually used for
        # filtering, since Contractors (like Vendors) are a genuine global
        # master, not scoped to one project. Matches VendorsPanel's own
        # identical pattern.
        self.project_id = project_id
        self.selected_contractor_id = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 5))
        title_block = ctk.CTkFrame(header, fg_color="transparent")
        title_block.pack(side="left")
        ctk.CTkLabel(title_block, text="Contractors", font=theme.FONT_HEADING, text_color=theme.INK).pack(anchor="w")
        ctk.CTkLabel(title_block, text="Execution partners -- labour, scope of work, running bills. "
                                       "Separate from Vendors, who supply materials.",
                     font=theme.FONT_SMALL, text_color=theme.MUTED).pack(anchor="w")

        ctk.CTkButton(header, text="+ New Contractor", command=self.open_add_contractor,
                      fg_color=theme.BRASS, hover_color=theme.INK, font=theme.FONT_BODY_BOLD, width=150).pack(
            side="right")

        # Search in the header with Ctrl+K, matching Clients/Projects/
        # Vendors -- no Bell/Help icons, same reasoning as those three.
        search_frame = ctk.CTkFrame(header, fg_color=theme.WHITE, corner_radius=8, border_width=1,
                                    border_color=theme.MUTED)
        search_frame.pack(side="right", padx=(0, 20))
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="Search name, trade, phone...",
                                         width=240, fg_color="transparent", border_width=0)
        self.search_entry.pack(side="left", padx=(10, 4), pady=4)
        self.search_entry.bind("<KeyRelease>", lambda e: self.refresh())
        ctk.CTkLabel(search_frame, text="Ctrl+K", font=("Segoe UI", 9), text_color=theme.MUTED).pack(
            side="left", padx=(0, 10))

        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=20, pady=(10, 8))

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=20, pady=(0, 18))
        self.status_filter_var = ctk.StringVar(value="Active")
        ctk.CTkOptionMenu(toolbar, values=["All Status"] + CONTRACTOR_STATUS_OPTIONS,
                          variable=self.status_filter_var, width=130,
                          command=lambda c: self.refresh()).pack(side="left", padx=(0, 8))
        self.trade_filter_var = ctk.StringVar(value="All Trades")
        ctk.CTkOptionMenu(toolbar, values=["All Trades"] + TRADE_OPTIONS, variable=self.trade_filter_var,
                          width=170, command=lambda c: self.refresh()).pack(side="left", padx=(0, 8))

        columns = ctk.CTkFrame(self, fg_color="transparent")
        columns.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        self.table_frame = ctk.CTkFrame(columns, fg_color=theme.WHITE)
        self.table_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        # Phone and Default Commission moved to the Quick Profile panel --
        # replaced with real, operational metrics (Projects/Contract Value/
        # Outstanding) that actually help prioritize contractors, matching
        # the same table redesign already done for Vendors.
        cols = ("code", "name", "trade", "projects", "value", "outstanding", "status")
        # Scoped custom style (not the global "Treeview" style shared by
        # every other table in the app) -- a slightly shorter row height
        # here, ~14% less than the app-wide default, without affecting
        # Clients/Projects/Vendors' tables.
        ttk.Style().configure("Contractors.Treeview", rowheight=24)
        self.tree = ttk.Treeview(self.table_frame, columns=cols, show="headings", height=16,
                                 style="Contractors.Treeview")
        headings = {"code": "Code", "name": "Contractor", "trade": "Trade", "projects": "Projects",
                    "value": "Contract Value", "outstanding": "Outstanding", "status": "Status"}
        widths = {"code": 85, "name": 150, "trade": 120, "projects": 70, "value": 115, "outstanding": 110,
                  "status": 90}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c])
        for status, color in STATUS_COLORS.items():
            self.tree.tag_configure(f"status_{status}", foreground=color)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda e: self.open_workspace())

        hscrollbar = ttk.Scrollbar(self.table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscroll=hscrollbar.set)
        hscrollbar.pack(side="bottom", fill="x")
        scrollbar = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True, side="left")

        details_panel = ctk.CTkFrame(columns, fg_color=theme.WHITE, corner_radius=8, width=360)
        details_panel.pack(side="left", fill="y")
        details_panel.pack_propagate(False)
        # Wrapped in AdaptiveScrollFrame from the start -- the same fix
        # just applied for Vendors' overflow bug, applied proactively here
        # so this panel never needs the same emergency fix later.
        details_scroll = ui.AdaptiveScrollFrame(details_panel, fg_color=theme.WHITE)
        details_scroll.pack(fill="both", expand=True)
        self.details_container = details_scroll.content
        self._render_empty_details()

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 15))
        ctk.CTkButton(footer, text="Edit Contractor", command=self.open_edit_contractor,
                      fg_color=theme.INK, font=theme.FONT_SMALL, height=26).pack(side="left", padx=(0, 8))
        ctk.CTkButton(footer, text="Archive Contractor", command=self.archive_contractor,
                      fg_color="#8B2E2E", hover_color="#5E1F1F", font=theme.FONT_SMALL, height=26).pack(side="left")

    def _render_empty_details(self):
        for w in self.details_container.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.details_container, text="Contractor Details", font=theme.FONT_BODY_BOLD,
                    text_color=theme.INK).pack(anchor="w", padx=15, pady=(15, 8))
        ctk.CTkLabel(self.details_container, text="Select a contractor to view:",
                    font=theme.FONT_SMALL, text_color=theme.MUTED, justify="left").pack(
            anchor="w", padx=15, pady=(0, 8))
        for line in ["Financial Summary", "Business Summary", "Current Projects", "Contact Information"]:
            row = ctk.CTkFrame(self.details_container, fg_color="transparent")
            row.pack(anchor="w", padx=15, pady=2)
            ctk.CTkLabel(row, text="•", font=theme.FONT_SMALL, text_color=theme.BRASS).pack(side="left", padx=(0, 6))
            ctk.CTkLabel(row, text=line, font=theme.FONT_SMALL, text_color=theme.MUTED).pack(side="left")

    def refresh(self):
        self._render_stats()
        for row in self.tree.get_children():
            self.tree.delete(row)
        if hasattr(self, "_empty_state_frame"):
            self._empty_state_frame.destroy()
            del self._empty_state_frame

        search = self.search_entry.get().strip().lower()
        status_filter = self.status_filter_var.get()
        trade_filter = self.trade_filter_var.get()

        contractors = db.fetch_all("SELECT * FROM mstContractor ORDER BY IsPreferred DESC, Name")
        if search:
            contractors = [c for c in contractors if search in c["Name"].lower()
                          or search in (c["Trade"] or "").lower()
                          or search in (c["Mobile"] or "").lower()]
        if status_filter != "All Status":
            contractors = [c for c in contractors if (c["Status"] or "Active") == status_filter]
        if trade_filter != "All Trades":
            contractors = [c for c in contractors if c["Trade"] == trade_filter]

        if not contractors:
            self.tree.pack_forget()
            self._empty_state_frame = ui.empty_state(
                self.table_frame, "No contractors yet.", "+ New Contractor", self.open_add_contractor)
            return
        self.tree.pack(fill="both", expand=True, side="left")

        for c in contractors:
            status = c["Status"] or "Active"
            name_display = f"⭐ {c['Name']}" if c["IsPreferred"] else c["Name"]
            total_value, total_paid, outstanding, project_count = contractor_financials(c["ContractorID"])
            self.tree.insert("", "end", iid=c["ContractorID"],
                             values=(c["ContractorCode"] or "—", name_display, c["Trade"] or "—",
                                    project_count, f"₹{total_value:,.0f}", f"₹{outstanding:,.0f}", status),
                             tags=(f"status_{status}",))

    def _render_stats(self):
        for w in self.stats_frame.winfo_children():
            w.destroy()
        all_contractors = db.fetch_all("SELECT ContractorID, Status, IsPreferred FROM mstContractor WHERE Active=1")
        total = len(all_contractors)
        active = sum(1 for c in all_contractors if (c["Status"] or "Active") == "Active")
        preferred = sum(1 for c in all_contractors if c["IsPreferred"])
        totals = [contractor_financials(c["ContractorID"]) for c in all_contractors]
        total_contract_value = sum(t[0] for t in totals)
        total_paid_all = sum(t[1] for t in totals)
        total_outstanding_all = sum(t[2] for t in totals)

        def pct(n):
            return f"{int(round(n / total * 100))}% of total" if total else "0% of total"

        # Six real, business-oriented cards, matching Vendors' pattern --
        # replacing the previous weak trio (Total/Active/With Default
        # Commission) with the same financial-hierarchy questions
        # (scale -> activity -> money -> exceptions) already proven there.
        stats = [
            (str(total), "Total Contractors", "All Time", "👷", "#F5E6D3"),
            (str(active), "Active Contractors", pct(active), "✅", "#D4F0E0"),
            (str(preferred), "Preferred", pct(preferred), "⭐", "#FBF0D6"),
            (f"₹{total_contract_value:,.0f}", "Total Contract Value", "All Projects", "📋", "#D6E8FA"),
            (f"₹{total_paid_all:,.0f}", "Total Paid", "All Time", "💰", "#DCF0DC"),
            (f"₹{total_outstanding_all:,.0f}", "Outstanding", "All Contracts", "⚠️", "#FBE0E0"),
        ]
        for col in range(6):
            self.stats_frame.grid_columnconfigure(col, weight=1)
        for col_idx, (value, label, sublabel, icon, bg_color) in enumerate(stats):
            ui.kpi_card(self.stats_frame, value, label, sublabel, icon, bg_color, col_idx)

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        contractor_id = int(sel[0])
        self.selected_contractor_id = contractor_id
        c = db.fetch_one("SELECT * FROM mstContractor WHERE ContractorID=?", (contractor_id,))
        total_value, total_paid, outstanding, project_count = contractor_financials(contractor_id)
        last_amount, last_date = contractor_last_payment(contractor_id)
        scope = db.fetch_all("SELECT s.ScopeName FROM mstContractorScope cs JOIN mstScopeOfWork s ON cs.ScopeID=s.ScopeID "
                             "WHERE cs.ContractorID=? ORDER BY s.ScopeName", (contractor_id,))
        current_projects = db.fetch_all("""
            SELECT DISTINCT p.ProjectID, p.ProjectName, p.ProjectStatus FROM tblProject p
            JOIN trxContract ct ON ct.ProjectID = p.ProjectID
            WHERE ct.ContractorID=? AND p.ProjectStatus NOT IN ('Completed', 'Cancelled')
        """, (contractor_id,))

        for w in self.details_container.winfo_children():
            w.destroy()
        d = self.details_container

        def section_label(text):
            ctk.CTkLabel(d, text=text.upper(), font=("Segoe UI", 9, "bold"), text_color=theme.MUTED).pack(
                anchor="w", padx=15, pady=(14, 4))

        def divider():
            ctk.CTkFrame(d, fg_color=theme.PARCHMENT, height=1).pack(fill="x", padx=15, pady=(4, 0))

        def value_row(label, value, value_color=None, size=13):
            row = ctk.CTkFrame(d, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=(6, 0))
            ctk.CTkLabel(row, text=label, font=("Segoe UI", 9), text_color=theme.MUTED, anchor="w").pack(anchor="w")
            ctk.CTkLabel(row, text=value, font=("Segoe UI", size, "bold"), text_color=value_color or theme.INK,
                        anchor="w", wraplength=310, justify="left").pack(anchor="w")

        # ---------------- Identity ----------------
        header_row = ctk.CTkFrame(d, fg_color="transparent")
        header_row.pack(fill="x", padx=15, pady=(15, 4))
        initials = "".join(w[0].upper() for w in c["Name"].split()[:2]) or "?"
        ctk.CTkLabel(header_row, text=initials, font=("Segoe UI", 13, "bold"), text_color=theme.WHITE,
                    fg_color=theme.BRASS, corner_radius=18, width=36, height=36).pack(side="left", padx=(0, 10))
        name_block = ctk.CTkFrame(header_row, fg_color="transparent")
        name_block.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(name_block, text=c["Name"], font=("Segoe UI", 16, "bold"), text_color=theme.INK,
                    anchor="w").pack(fill="x")
        ctk.CTkLabel(name_block, text=c["ContractorCode"] or "—", font=("Segoe UI", 10), text_color=theme.MUTED,
                    anchor="w").pack(fill="x")
        badges = ctk.CTkFrame(d, fg_color="transparent")
        badges.pack(fill="x", padx=15, pady=(4, 0))
        if c["IsPreferred"]:
            ui.pill_badge(badges, "⭐ Preferred", "#B68100").pack(side="left", padx=(0, 6))
        ui.pill_badge(badges, c["Trade"] or "Contractor", "#1E5FA8").pack(side="left")
        if c["Rating"]:
            ctk.CTkLabel(d, text="★" * int(round(c["Rating"])) + f"  ({c['Rating']:.1f}/5)",
                        font=("Segoe UI", 12), text_color=theme.BRASS).pack(anchor="w", padx=15, pady=(6, 0))
        divider()

        # ---------------- Financial Summary (real, already existed via trxContractPayment) ----------------
        section_label("Financial Summary")
        value_row("Total Contract Value", f"₹{total_value:,.0f}")
        value_row("Payments Made", f"₹{total_paid:,.0f}", "#2E8B57")
        value_row("Outstanding", f"₹{outstanding:,.0f}", "#8B2E2E" if outstanding > 0 else theme.INK, size=16)
        if last_amount is not None:
            value_row("Last Payment", f"₹{last_amount:,.0f}  ({last_date})")
        if total_value == 0:
            status_text, status_color = "No Contracts Yet", "#6B6B6B"
        elif outstanding <= 0:
            status_text, status_color = "● Fully Paid", "#2E8B57"
        elif total_paid > 0:
            status_text, status_color = "● Partial Payment", "#B68100"
        else:
            status_text, status_color = "● Payment Due", "#8B2E2E"
        ui.pill_badge(d, status_text, status_color).pack(anchor="w", padx=15, pady=(6, 0))
        ctk.CTkButton(d, text="+ Record Payment", command=self._open_record_payment,
                     fg_color=theme.INK, hover_color=theme.BRASS, font=theme.FONT_SMALL, height=26).pack(
            fill="x", padx=15, pady=(8, 0))
        divider()

        # ---------------- Business Summary ----------------
        section_label("Business Summary")
        value_row("Projects Worked", str(project_count))
        value_row("Active Projects", str(len(current_projects)))
        if c["DefaultCommissionPercent"]:
            value_row("Default Commission", f"{c['DefaultCommissionPercent']:.1f}%")
        value_row("Relationship Since", c["CreatedOn"][:10] if c["CreatedOn"] else "—")
        if scope:
            ctk.CTkLabel(d, text="Scope of Work", font=("Segoe UI", 9), text_color=theme.MUTED, anchor="w").pack(
                anchor="w", padx=15, pady=(8, 2))
            scope_row = ctk.CTkFrame(d, fg_color="transparent")
            scope_row.pack(fill="x", padx=15)
            for s in scope:
                ui.pill_badge(scope_row, s["ScopeName"], "#6B6B6B").pack(side="left", padx=(0, 4), pady=2)
        divider()

        # ---------------- Current Projects (real, active only) ----------------
        section_label("Current Projects")
        if not current_projects:
            ctk.CTkLabel(d, text="No active projects for this contractor right now.", font=theme.FONT_SMALL,
                        text_color=theme.MUTED, wraplength=310, justify="left").pack(anchor="w", padx=15, pady=(0, 0))
        else:
            for p in current_projects:
                row = ctk.CTkFrame(d, fg_color="transparent")
                row.pack(fill="x", padx=15, pady=2)
                ctk.CTkLabel(row, text=p["ProjectName"], font=theme.FONT_SMALL, text_color=theme.INK).pack(side="left")
                ctk.CTkLabel(row, text=p["ProjectStatus"], font=("Segoe UI", 9), text_color=theme.MUTED).pack(side="right")
        divider()

        # ---------------- Contact ----------------
        section_label("Contact")
        value_row("Mobile", c["Mobile"] or "—")
        value_row("Alt. Mobile", c["AltMobile"] or "—")
        value_row("Email", c["Email"] or "—")
        value_row("GST No.", c["GSTNo"] or "—")

        ctk.CTkButton(d, text="Open Contractor Workspace  →", command=self.open_workspace,
                     fg_color=theme.BRASS, hover_color=theme.INK, font=("Segoe UI", 12, "bold"), height=32).pack(
            fill="x", padx=15, pady=(14, 15))

    def _open_record_payment(self):
        if self.selected_contractor_id is None:
            return
        c = db.fetch_one("SELECT * FROM mstContractor WHERE ContractorID=?", (self.selected_contractor_id,))
        RecordContractorPaymentDialog(self, c, on_save=lambda: self._on_select())

    def _selected_or_warn(self):
        if self.selected_contractor_id is None:
            messagebox.showinfo("Select a contractor", "Please select a contractor from the list first.", parent=self)
            return None
        return self.selected_contractor_id


    def open_add_contractor(self):
        ContractorForm(self, on_save=self.refresh)

    def open_edit_contractor(self):
        contractor_id = self._selected_or_warn()
        if contractor_id is None:
            return
        contractor = db.fetch_one("SELECT * FROM mstContractor WHERE ContractorID=?", (contractor_id,))
        ContractorForm(self, on_save=self.refresh, existing=contractor)

    def open_workspace(self):
        contractor_id = self._selected_or_warn()
        if contractor_id is None:
            return
        ContractorWorkspace(self, contractor_id, on_close=self.refresh)

    def archive_contractor(self):
        contractor_id = self._selected_or_warn()
        if contractor_id is None:
            return
        in_use = db.fetch_one("SELECT COUNT(*) AS n FROM trxContract WHERE ContractorID=?", (contractor_id,))["n"]
        message = (f"This contractor has {in_use} real contract(s) attached. Archiving removes them from active "
                  f"pickers but keeps all history intact. Archive this contractor?") if in_use > 0 else \
                  "Archive this contractor? This can be reversed later by editing their Status."
        if messagebox.askyesno("Archive contractor", message, parent=self):
            db.execute("UPDATE mstContractor SET Status='Archived', Active=0, ModifiedOn=datetime('now') WHERE ContractorID=?",
                      (contractor_id,))
            db.log_activity("System", contractor_id, "Contractor Archived", "")
            self.selected_contractor_id = None
            self.refresh()


class ContractorForm(ui.ScrollableDialog):
    def __init__(self, master, on_save, existing=None):
        super().__init__(master, title="Edit Contractor" if existing else "New Contractor",
                         natural_width=460, natural_height=880)
        self.on_save = on_save
        self.existing = existing

        row = 0
        ctk.CTkLabel(self.body, text=self.title(), font=theme.FONT_SUBHEADING, text_color=theme.INK).grid(
            row=row, column=0, columnspan=2, padx=15, pady=(15, 10), sticky="w")
        row += 1

        self.entries = {}
        fields = [
            ("Name *", "name_entry", existing["Name"] if existing else ""),
            ("Business Name", "business_entry", existing["BusinessName"] if existing and existing["BusinessName"] else ""),
            ("Alternate Mobile", "alt_mobile_entry", existing["AltMobile"] if existing and existing["AltMobile"] else ""),
            ("Address", "address_entry", existing["Address"] if existing and existing["Address"] else ""),
        ]
        for label, key, default in fields:
            ctk.CTkLabel(self.body, text=label, font=theme.FONT_BODY, text_color=theme.INK).grid(
                row=row, column=0, sticky="w", padx=15, pady=8)
            entry = ctk.CTkEntry(self.body, width=250)
            entry.insert(0, default)
            entry.grid(row=row, column=1, padx=15, pady=8)
            self.entries[key] = entry
            row += 1

        ctk.CTkLabel(self.body, text="Trade *", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.trade_var = ctk.StringVar(value=(existing["Trade"] if existing and existing["Trade"] else TRADE_OPTIONS[0]))
        ctk.CTkOptionMenu(self.body, values=TRADE_OPTIONS, variable=self.trade_var, width=250).grid(
            row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self.body, text="Mobile *", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.entries["mobile_entry"] = ctk.CTkEntry(self.body, width=250, placeholder_text="10-digit mobile number")
        apply_numeric_only(self, self.entries["mobile_entry"], max_length=15)
        if existing and existing["Mobile"]:
            self.entries["mobile_entry"].insert(0, existing["Mobile"])
        self.entries["mobile_entry"].grid(row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self.body, text="Email", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.entries["email_entry"] = ctk.CTkEntry(self.body, width=250, placeholder_text="name@example.com")
        if existing and existing["Email"]:
            self.entries["email_entry"].insert(0, existing["Email"])
        self.entries["email_entry"].grid(row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self.body, text="GST No. (optional)", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.entries["gst_entry"] = ctk.CTkEntry(self.body, width=250, placeholder_text="15-character GSTIN")
        if existing and existing["GSTNo"]:
            self.entries["gst_entry"].insert(0, existing["GSTNo"])
        self.entries["gst_entry"].grid(row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self.body, text="PAN No.", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.entries["pan_entry"] = ctk.CTkEntry(self.body, width=250, placeholder_text="10-character PAN")
        if existing and existing["PANNo"]:
            self.entries["pan_entry"].insert(0, existing["PANNo"])
        self.entries["pan_entry"].grid(row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self.body, text="Aadhaar No.", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.entries["aadhaar_entry"] = ctk.CTkEntry(self.body, width=250, placeholder_text="12-digit Aadhaar")
        apply_numeric_only(self, self.entries["aadhaar_entry"], max_length=12)
        if existing and existing["AadhaarNo"]:
            self.entries["aadhaar_entry"].insert(0, existing["AadhaarNo"])
        self.entries["aadhaar_entry"].grid(row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self.body, text="Banking", font=theme.FONT_BODY_BOLD, text_color=theme.INK).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=15, pady=(10, 6))
        row += 1
        for label, key, default in [
            ("Bank Name", "bank_name_entry", existing["BankName"] if existing and existing["BankName"] else ""),
            ("Account Number", "bank_account_entry", existing["BankAccountNumber"] if existing and existing["BankAccountNumber"] else ""),
            ("IFSC", "bank_ifsc_entry", existing["BankIFSC"] if existing and existing["BankIFSC"] else ""),
            ("UPI ID", "upi_entry", existing["UPIID"] if existing and existing["UPIID"] else ""),
        ]:
            ctk.CTkLabel(self.body, text=label, font=theme.FONT_BODY, text_color=theme.INK).grid(
                row=row, column=0, sticky="w", padx=15, pady=8)
            entry = ctk.CTkEntry(self.body, width=250)
            entry.insert(0, default)
            entry.grid(row=row, column=1, padx=15, pady=8)
            self.entries[key] = entry
            row += 1

        ctk.CTkLabel(self.body, text="Default Commission (%)", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.entries["commission_entry"] = ctk.CTkEntry(self.body, width=250, placeholder_text="e.g. 5")
        apply_decimal_only(self, self.entries["commission_entry"])
        if existing and existing["DefaultCommissionPercent"]:
            self.entries["commission_entry"].insert(0, str(existing["DefaultCommissionPercent"]))
        self.entries["commission_entry"].grid(row=row, column=1, padx=15, pady=8)
        row += 1
        ctk.CTkLabel(self.body, text="A default only -- the actual commission on any project contract can be "
                                     "set independently and never changes this master record.",
                    font=theme.FONT_SMALL, text_color=theme.MUTED, wraplength=380, justify="left").grid(
            row=row, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 6))
        row += 1

        self.preferred_var = ctk.BooleanVar(value=bool(existing["IsPreferred"]) if existing else False)
        ctk.CTkCheckBox(self.body, text="⭐ Preferred Contractor", variable=self.preferred_var,
                       font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self.body, text="Scope of Work", font=theme.FONT_BODY_BOLD, text_color=theme.INK).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=15, pady=(10, 6))
        row += 1
        scope_by_name = {r["ScopeName"]: r["ScopeID"] for r in db.fetch_all("SELECT ScopeID, ScopeName FROM mstScopeOfWork")}
        existing_scope_ids = set()
        if existing:
            existing_scope_ids = {r["ScopeID"] for r in db.fetch_all(
                "SELECT ScopeID FROM mstContractorScope WHERE ContractorID=?", (existing["ContractorID"],))}
        scope_outer = ctk.CTkFrame(self.body, fg_color="transparent")
        scope_outer.grid(row=row, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 10))
        self.scope_vars = {}
        for group_name, item_names in SCOPE_GROUPS.items():
            self._build_scope_group(scope_outer, group_name, item_names, scope_by_name, existing_scope_ids)
        row += 1

        ctk.CTkLabel(self.body, text="Status", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.status_var = ctk.StringVar(value=(existing["Status"] if existing and existing["Status"] else "Active"))
        ctk.CTkOptionMenu(self.body, values=CONTRACTOR_STATUS_OPTIONS, variable=self.status_var, width=250).grid(
            row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self.body, text="Notes", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.entries["notes_entry"] = ctk.CTkEntry(self.body, width=250)
        if existing and existing["Notes"] and not existing["Notes"].startswith("Migrated from Vendor"):
            self.entries["notes_entry"].insert(0, existing["Notes"])
        self.entries["notes_entry"].grid(row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkButton(self.body, text="Save", command=self.save, fg_color=theme.BRASS,
                     hover_color=theme.INK, font=theme.FONT_BODY_BOLD).grid(
            row=row, column=0, columnspan=2, pady=20)

    def _build_scope_group(self, parent, group_name, item_names, scope_by_name, existing_scope_ids):
        group_scope_ids = [scope_by_name[n] for n in item_names if n in scope_by_name]
        any_checked = any(sid in existing_scope_ids for sid in group_scope_ids)

        group_frame = ctk.CTkFrame(parent, fg_color=theme.PARCHMENT, corner_radius=4)
        group_frame.pack(fill="x", pady=2)
        expanded_var = ctk.BooleanVar(value=any_checked)
        items_frame = ctk.CTkFrame(group_frame, fg_color="transparent")

        def toggle():
            if expanded_var.get():
                items_frame.pack_forget()
                expanded_var.set(False)
                header_btn.configure(text=f"▶ {group_name}")
            else:
                items_frame.pack(fill="x", padx=15, pady=(0, 6))
                expanded_var.set(True)
                header_btn.configure(text=f"▼ {group_name}")

        header_btn = ctk.CTkButton(group_frame, text=f"{'▼' if any_checked else '▶'} {group_name}",
                                   command=toggle, fg_color="transparent", hover_color=theme.WHITE,
                                   text_color=theme.INK, font=theme.FONT_SMALL, anchor="w", height=24)
        header_btn.pack(fill="x", padx=5, pady=2)

        for name in item_names:
            if name not in scope_by_name:
                continue
            scope_id = scope_by_name[name]
            var = ctk.BooleanVar(value=(scope_id in existing_scope_ids))
            ctk.CTkCheckBox(items_frame, text=name, variable=var, font=theme.FONT_SMALL).pack(
                anchor="w", padx=10, pady=2)
            self.scope_vars[scope_id] = var

        if any_checked:
            items_frame.pack(fill="x", padx=15, pady=(0, 6))

    def save(self):
        name = self.entries["name_entry"].get().strip()
        mobile = self.entries["mobile_entry"].get().strip()
        if not name:
            messagebox.showerror("Missing name", "Contractor Name is required.", parent=self)
            return
        if not mobile:
            messagebox.showerror("Missing mobile", "Mobile number is required.", parent=self)
            return

        email = self.entries["email_entry"].get().strip()
        if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            messagebox.showerror("Invalid email", "Please enter a valid email address.", parent=self)
            return
        gst = self.entries["gst_entry"].get().strip()
        if gst and len(gst) != 15:
            messagebox.showerror("Invalid GST No.", "GSTIN must be exactly 15 characters.", parent=self)
            return

        commission_raw = self.entries["commission_entry"].get().strip()
        try:
            commission = float(commission_raw) if commission_raw else None
        except ValueError:
            messagebox.showerror("Invalid number", "Default Commission must be a number.", parent=self)
            return

        active_flag = 1 if self.status_var.get() == "Active" else 0
        business_name = self.entries["business_entry"].get().strip()
        alt_mobile = self.entries["alt_mobile_entry"].get().strip()
        address = self.entries["address_entry"].get().strip()
        pan = self.entries["pan_entry"].get().strip()
        aadhaar = self.entries["aadhaar_entry"].get().strip()
        bank_name = self.entries["bank_name_entry"].get().strip()
        bank_account = self.entries["bank_account_entry"].get().strip()
        bank_ifsc = self.entries["bank_ifsc_entry"].get().strip()
        upi = self.entries["upi_entry"].get().strip()
        notes = self.entries["notes_entry"].get().strip()
        is_preferred = 1 if self.preferred_var.get() else 0
        trade = self.trade_var.get()

        if self.existing:
            contractor_id = self.existing["ContractorID"]
            db.execute(
                """UPDATE mstContractor SET Name=?, BusinessName=?, Trade=?, Mobile=?, AltMobile=?, Email=?,
                   GSTNo=?, PANNo=?, AadhaarNo=?, Address=?, BankName=?, BankAccountNumber=?, BankIFSC=?, UPIID=?,
                   DefaultCommissionPercent=?, IsPreferred=?, Status=?, Active=?, Notes=?, ModifiedOn=datetime('now')
                   WHERE ContractorID=?""",
                (name, business_name, trade, mobile, alt_mobile, email, gst, pan, aadhaar, address, bank_name,
                 bank_account, bank_ifsc, upi, commission, is_preferred, self.status_var.get(), active_flag,
                 notes, contractor_id)
            )
            db.log_activity("System", contractor_id, "Contractor Updated", name)
        else:
            contractor_id = db.execute(
                """INSERT INTO mstContractor (Name, BusinessName, Trade, Mobile, AltMobile, Email, GSTNo, PANNo,
                   AadhaarNo, Address, BankName, BankAccountNumber, BankIFSC, UPIID, DefaultCommissionPercent,
                   IsPreferred, Status, Active, Notes, CreatedOn, ModifiedOn)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))""",
                (name, business_name, trade, mobile, alt_mobile, email, gst, pan, aadhaar, address, bank_name,
                 bank_account, bank_ifsc, upi, commission, is_preferred, self.status_var.get(), active_flag, notes)
            )
            code = f"CON-{contractor_id:04d}"
            db.execute("UPDATE mstContractor SET ContractorCode=? WHERE ContractorID=?", (code, contractor_id))
            db.log_activity("System", contractor_id, "Contractor Added", name)

        # Scope of Work: replace the full selection each save.
        db.execute("DELETE FROM mstContractorScope WHERE ContractorID=?", (contractor_id,))
        for scope_id, var in self.scope_vars.items():
            if var.get():
                db.execute("INSERT INTO mstContractorScope (ContractorID, ScopeID) VALUES (?,?)", (contractor_id, scope_id))

        self.on_save()
        self.destroy()


class RecordContractorPaymentDialog(ctk.CTkToplevel):
    """
    Real, functional dialog to record an actual payment against one of a
    contractor's real contracts. Unlike Vendor payments (where PurchaseID
    is optional), trxContractPayment.ContractID is NOT NULL -- a payment
    must be tied to a specific real contract, so this requires picking
    one from the contractor's actual contracts, not just the contractor
    generally.
    """
    def __init__(self, master, contractor, on_save):
        super().__init__(master)
        self.contractor = contractor
        self.on_save = on_save
        self.title(f"Record Payment -- {contractor['Name']}")
        self.geometry("400x380")
        self.configure(fg_color=theme.PARCHMENT)
        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(self, text=f"Record Payment to {contractor['Name']}", font=theme.FONT_BODY_BOLD,
                    text_color=theme.INK).pack(anchor="w", padx=20, pady=(20, 15))

        contracts = db.fetch_all("""
            SELECT ct.ContractID, ct.ContractAmount, p.ProjectName FROM trxContract ct
            JOIN tblProject p ON ct.ProjectID = p.ProjectID WHERE ct.ContractorID=?
        """, (contractor["ContractorID"],))
        if not contracts:
            ctk.CTkLabel(self, text="This contractor has no contracts yet -- create a contract for a "
                                    "project before recording a payment.", font=theme.FONT_SMALL,
                        text_color=theme.MUTED, wraplength=340, justify="left").pack(padx=20, pady=(0, 20))
            ctk.CTkButton(self, text="Close", command=self.destroy, fg_color=theme.INK).pack(padx=20, pady=(0, 20))
            return

        self._contracts = {f"{c['ProjectName']} (₹{c['ContractAmount']:,.0f})": c["ContractID"] for c in contracts}
        ctk.CTkLabel(self, text="Contract", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.contract_var = ctk.StringVar(value=list(self._contracts.keys())[0])
        ctk.CTkOptionMenu(self, values=list(self._contracts.keys()), variable=self.contract_var,
                         width=340).pack(padx=20, pady=(2, 12))

        ctk.CTkLabel(self, text="Amount", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.amount_entry = ctk.CTkEntry(self, width=340)
        self.amount_entry.pack(padx=20, pady=(2, 12))

        ctk.CTkLabel(self, text="Payment Date", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.date_entry = DateEntry(self, width=25, date_pattern="yyyy-mm-dd", background=theme.BRASS,
                                    foreground="white", borderwidth=1)
        self.date_entry.pack(anchor="w", padx=20, pady=(2, 12))

        ctk.CTkLabel(self, text="Payment Mode", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.mode_var = ctk.StringVar(value="Bank Transfer")
        ctk.CTkOptionMenu(self, values=["Bank Transfer", "Cheque", "Cash", "UPI", "Other"],
                         variable=self.mode_var, width=340).pack(padx=20, pady=(2, 12))

        ctk.CTkButton(self, text="Save Payment", command=self.save, fg_color=theme.BRASS, hover_color=theme.INK,
                     font=theme.FONT_BODY_BOLD).pack(padx=20, pady=(10, 20), fill="x")

    def save(self):
        try:
            amount = float(self.amount_entry.get().strip())
            if amount <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid amount", "Enter a valid payment amount greater than 0.", parent=self)
            return
        contract_id = self._contracts[self.contract_var.get()]
        db.execute("INSERT INTO trxContractPayment (ContractID, Amount, PaymentDate, PaymentType, PaymentMode) "
                  "VALUES (?,?,?,?,?)",
                  (contract_id, amount, self.date_entry.get_date().isoformat(), "Partial", self.mode_var.get()))
        db.log_activity("Contractor", self.contractor["ContractorID"], "Payment Recorded")
        self.on_save()
        self.destroy()


class ContractorWorkspace(ui.EntityWorkspace):
    """
    The full Contractor profile -- opened by double-clicking a row in
    ContractorsPanel, or via "View Full Profile" from the quick-profile
    panel. Built on the shared EntityWorkspace framework so it stays
    visually and structurally identical to the Vendor Workspace that
    will follow it, and any future entity workspace built the same way.

    Tabs built now, with real queryable data: Overview, Projects, Payments,
    Notes. Deliberately NOT built in this pass: Documents (no file-upload
    infrastructure exists anywhere in this app), Analytics (would need a
    real charting decision, not a placeholder), Reports (needs its own
    design), Running Bills (not a real, built concept yet -- that's
    Contractor Module Phase 2, alongside the trxContract integration
    already shipped in v4.6.0).
    """
    def __init__(self, master, contractor_id, on_close=None):
        self.contractor_id = contractor_id
        c = db.fetch_one("SELECT * FROM mstContractor WHERE ContractorID=?", (contractor_id,))
        tags = []
        if c["IsPreferred"]:
            tags.append("⭐ Preferred")
        tags.append(c["Status"] or "Active")

        super().__init__(master, breadcrumb_root="Contractors", entity_name=c["Name"],
                         subtitle=f"{c['Trade'] or 'Contractor'}" + (f"  ·  {c['Mobile']}" if c["Mobile"] else ""),
                         tags=tags, quick_actions=[("Edit Contractor", self._edit),
                                                  ("Record Payment", self._record_payment)], on_close=on_close)

        self.add_tab("Overview", self._build_overview)
        self.add_tab("Projects", self._build_projects)
        self.add_tab("Payments", self._build_payments)
        self.add_tab("Notes", self._build_notes)
        self.build()

    def _record_payment(self):
        c = db.fetch_one("SELECT * FROM mstContractor WHERE ContractorID=?", (self.contractor_id,))
        RecordContractorPaymentDialog(self, c, on_save=lambda: None)

    def _edit(self):
        c = db.fetch_one("SELECT * FROM mstContractor WHERE ContractorID=?", (self.contractor_id,))
        ContractorForm(self, on_save=lambda: self._refresh_after_edit(), existing=c)

    def _refresh_after_edit(self):
        # The workspace window itself doesn't need to rebuild -- most
        # fields are only shown in Overview/the header, which the user
        # will see fresh next time they open this contractor. Simple and
        # safe rather than rebuilding a live window mid-session.
        pass

    def _build_overview(self, parent):
        c = db.fetch_one("SELECT * FROM mstContractor WHERE ContractorID=?", (self.contractor_id,))
        total_value, total_paid, outstanding, project_count = contractor_financials(self.contractor_id)

        stats_row = ctk.CTkFrame(parent, fg_color="transparent")
        stats_row.pack(fill="x", padx=15, pady=(15, 10))
        stats = [
            (str(project_count), "Projects Worked", None),
            (f"₹{total_value:,.2f}", "Total Contract Value", None),
            (f"₹{total_paid:,.2f}", "Total Paid", None),
            (f"₹{outstanding:,.2f}", "Outstanding", None),
        ]
        if c["DefaultCommissionPercent"]:
            stats.append((f"{c['DefaultCommissionPercent']:.1f}%", "Default Commission", None))
        stats.append((c["CreatedOn"][:10] if c["CreatedOn"] else "-", "Relationship Since", None))
        for value, label, sublabel in stats:
            ui.stat_card(parent, value, label, sublabel).pack(side="left", padx=(15, 0), pady=(0, 10))

        # Real Scope of Work
        scope = db.fetch_all("SELECT s.ScopeName FROM mstContractorScope cs JOIN mstScopeOfWork s ON cs.ScopeID=s.ScopeID "
                             "WHERE cs.ContractorID=? ORDER BY s.ScopeName", (self.contractor_id,))
        if scope:
            ctk.CTkLabel(parent, text="Scope of Work: " + ", ".join(s["ScopeName"] for s in scope),
                        font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=15, pady=(5, 10))

        # Details panel
        details_frame = ctk.CTkFrame(parent, fg_color=theme.WHITE, corner_radius=8)
        details_frame.pack(fill="x", padx=15, pady=(0, 15))
        ctk.CTkLabel(details_frame, text="Contractor Details", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=15, pady=(15, 8))
        detail_fields = [
            ("Business Name", c["BusinessName"]), ("Trade", c["Trade"]), ("Mobile", c["Mobile"]),
            ("Alternate Mobile", c["AltMobile"]), ("Email", c["Email"]), ("GST Number", c["GSTNo"]),
            ("PAN Number", c["PANNo"]), ("Aadhaar Number", c["AadhaarNo"]), ("Address", c["Address"]),
            ("Bank Name", c["BankName"]), ("Account Number", c["BankAccountNumber"]), ("IFSC", c["BankIFSC"]),
            ("UPI ID", c["UPIID"]),
        ]
        for label, value in detail_fields:
            if value:
                row = ctk.CTkFrame(details_frame, fg_color="transparent")
                row.pack(fill="x", padx=15, pady=2)
                ctk.CTkLabel(row, text=label, font=theme.FONT_SMALL, text_color=theme.MUTED, width=140,
                            anchor="w").pack(side="left")
                ctk.CTkLabel(row, text=str(value), font=theme.FONT_SMALL, text_color=theme.INK, anchor="w").pack(side="left")
        ctk.CTkFrame(details_frame, fg_color="transparent", height=10).pack()

    def _build_projects(self, parent):
        contracts = db.fetch_all("""
            SELECT c.*, p.ProjectName, p.ProjectCode FROM trxContract c
            JOIN tblProject p ON c.ProjectID = p.ProjectID
            WHERE c.ContractorID=? ORDER BY c.ContractID DESC
        """, (self.contractor_id,))
        if not contracts:
            ui.empty_state(parent, "No projects yet for this contractor.")
            return
        for ct in contracts:
            paid = db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxContractPayment WHERE ContractID=?",
                                (ct["ContractID"],))["t"]
            status = get_contract_status(ct, paid)
            row = ctk.CTkFrame(parent, fg_color=theme.WHITE, corner_radius=6)
            row.pack(fill="x", padx=15, pady=4)
            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", fill="x", expand=True, padx=12, pady=10)
            ctk.CTkLabel(left, text=ct["ProjectName"], font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(anchor="w")
            ctk.CTkLabel(left, text=f"{ct['ProjectCode']}  ·  {ct['ContractType']}", font=theme.FONT_SMALL,
                        text_color=theme.MUTED).pack(anchor="w")
            right = ctk.CTkFrame(row, fg_color="transparent")
            right.pack(side="right", padx=12, pady=10)
            amount_text = f"₹{ct['ContractAmount']:,.2f}" if ct["ContractAmount"] is not None else "Running"
            ctk.CTkLabel(right, text=amount_text, font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(anchor="e")
            ctk.CTkLabel(right, text=status, font=theme.FONT_SMALL, text_color=theme.MUTED).pack(anchor="e")

    def _build_payments(self, parent):
        payments = db.fetch_all("""
            SELECT cp.*, p.ProjectName FROM trxContractPayment cp
            JOIN trxContract c ON cp.ContractID = c.ContractID
            JOIN tblProject p ON c.ProjectID = p.ProjectID
            WHERE c.ContractorID=? ORDER BY cp.PaymentDate DESC, cp.PaymentID DESC
        """, (self.contractor_id,))
        if not payments:
            ui.empty_state(parent, "No payments recorded yet for this contractor.")
            return
        for pmt in payments:
            row = ctk.CTkFrame(parent, fg_color=theme.WHITE, corner_radius=6)
            row.pack(fill="x", padx=15, pady=4)
            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", fill="x", expand=True, padx=12, pady=10)
            ctk.CTkLabel(left, text=pmt["ProjectName"], font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(anchor="w")
            ctk.CTkLabel(left, text=f"{pmt['PaymentDate'] or '-'}  ·  {pmt['PaymentType'] or '-'}",
                        font=theme.FONT_SMALL, text_color=theme.MUTED).pack(anchor="w")
            ctk.CTkLabel(row, text=f"₹{pmt['Amount']:,.2f}", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
                side="right", padx=12, pady=10)

    def _build_notes(self, parent):
        c = db.fetch_one("SELECT Notes FROM mstContractor WHERE ContractorID=?", (self.contractor_id,))
        notes = c["Notes"] or ""
        if notes.startswith("Migrated from Vendor"):
            notes = ""
        ctk.CTkLabel(parent, text=notes or "No notes yet.", font=theme.FONT_BODY, text_color=theme.INK,
                    wraplength=800, justify="left").pack(anchor="w", padx=15, pady=15)
        ctk.CTkLabel(parent, text="Edit notes via \"Edit Contractor\" above.", font=theme.FONT_SMALL,
                    text_color=theme.MUTED).pack(anchor="w", padx=15)

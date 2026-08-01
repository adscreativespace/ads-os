"""
ADS OS Desktop -- Vendors (Commercial module, fourth of six)
Full vendor profiles (extending the minimal mstVendor table BOQ/Materials
already created), with a Vendor Details panel showing a REAL computed Total
Purchase (All Time) -- summed from actual trxMaterialPurchase and trxBOQItem
records tied to that vendor, not a fabricated number. Deliberately does not
show "Outstanding Payables" -- that requires real invoice/payment data
(Invoice Center, module #5) which doesn't exist yet; showing a number with
nothing real behind it would be worse than not showing it.
"""
import customtkinter as ctk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
import re
import db
import theme
import ui_components as ui
from constants import apply_numeric_only, apply_decimal_only

VENDOR_STATUS_OPTIONS = ["Active", "Inactive", "Blacklisted", "Archived"]
# Business relationship only -- trade detail now lives in Scope of Work,
# not here. Fixes a real overlap: this used to contain "Civil Contractor" /
# "Interior Contractor" / "Labour Contractor" alongside a near-identical
# set in Category, creating genuine ambiguity about which field to use.
PARTNER_TYPE_OPTIONS = ["Supplier", "Contractor", "Consultant", "Transport", "Rental Equipment",
                        "Manufacturer", "Fabricator", "Labour Agency", "Architect", "Engineer", "Surveyor"]
# Supplier-specific: what materials they supply. Only shown/editable when
# Partner Type = Supplier.
PRODUCT_CATEGORY_OPTIONS = ["Cement", "Steel", "Tiles", "Paint", "Hardware", "Wood", "Glass",
                           "Aluminium", "Electrical", "Plumbing", "Miscellaneous"]

# Groups the 26 Scope of Work items into collapsible sections instead of one
# long flat checklist -- purely presentational, doesn't change the data model.
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
STATUS_COLORS = {"Active": "#2E8B57", "Inactive": "#6B6B6B", "Blacklisted": "#8B2E2E"}


def vendor_total_purchase(vendor_id):
    """Real, computed total -- not fabricated. Sums actual purchase/BOQ amounts tied to this vendor."""
    material_total, boq_total = vendor_purchase_breakdown(vendor_id)
    return material_total + boq_total


def vendor_purchase_breakdown(vendor_id):
    """
    Real (materials_total, boq_total) breakdown of a vendor's Total
    Purchases -- added specifically because Total Purchases silently
    combines two separate, legitimate sources (trxMaterialPurchase and
    trxBOQItem), which is correct but not transparent: someone comparing
    Total Purchases against the Materials screen alone (which only shows
    trxMaterialPurchase rows) would see a real gap with no visible
    explanation. Surfacing both numbers here prevents that confusion
    without changing what Total Purchases actually means.
    """
    material_total = db.fetch_one("""
        SELECT COALESCE(SUM(p.TotalCost), 0) AS total FROM trxMaterialPurchase p
        JOIN mstMaterial m ON p.MaterialID = m.MaterialID
        WHERE m.VendorID = ?
    """, (vendor_id,))["total"]
    boq_total = db.fetch_one(
        "SELECT COALESCE(SUM(Amount), 0) AS total FROM trxBOQItem WHERE VendorID = ?", (vendor_id,))["total"]
    return material_total, boq_total


def vendor_projects_worked(vendor_id):
    """Real count of distinct projects this vendor has supplied materials or BOQ items for."""
    material_projects = {r["ProjectID"] for r in db.fetch_all(
        "SELECT DISTINCT ProjectID FROM mstMaterial WHERE VendorID=? AND ProjectID IS NOT NULL", (vendor_id,))}
    boq_projects = {r["ProjectID"] for r in db.fetch_all(
        "SELECT DISTINCT ProjectID FROM trxBOQItem WHERE VendorID=? AND ProjectID IS NOT NULL", (vendor_id,))}
    return len(material_projects | boq_projects)


def vendor_transaction_dates(vendor_id):
    """
    Real first/last transaction dates from actual purchase and BOQ records
    tied to this vendor -- returns (first, last) as ISO date strings, or
    (None, None) if the vendor has no transactions yet (not "-", handled
    by the caller so it can decide how to display "no transactions").
    """
    dates = [r["PurchaseDate"] for r in db.fetch_all("""
        SELECT p.PurchaseDate FROM trxMaterialPurchase p JOIN mstMaterial m ON p.MaterialID = m.MaterialID
        WHERE m.VendorID = ? AND p.PurchaseDate IS NOT NULL
    """, (vendor_id,))]
    dates += [r["CreatedOn"] for r in db.fetch_all(
        "SELECT CreatedOn FROM trxBOQItem WHERE VendorID=? AND CreatedOn IS NOT NULL", (vendor_id,))]
    if not dates:
        return None, None
    dates.sort()
    return dates[0][:10], dates[-1][:10]


def vendor_payments_made(vendor_id):
    """Real sum of actual payments recorded against this vendor. Starts at 0 until a real payment is logged."""
    return db.fetch_one(
        "SELECT COALESCE(SUM(Amount), 0) AS t FROM trxVendorPayment WHERE VendorID=?", (vendor_id,))["t"]


def vendor_outstanding(vendor_id):
    """Real Outstanding = Total Purchases - Payments Made, now genuinely computable with trxVendorPayment."""
    return vendor_total_purchase(vendor_id) - vendor_payments_made(vendor_id)


def vendor_top_materials(vendor_id, limit=5):
    """
    Real materials this vendor has actually supplied, ranked by total
    purchase amount -- derived entirely from existing purchase history,
    no manual entry or fabrication needed.
    """
    rows = db.fetch_all("""
        SELECT m.MaterialName, SUM(p.TotalCost) AS total
        FROM trxMaterialPurchase p JOIN mstMaterial m ON p.MaterialID = m.MaterialID
        WHERE m.VendorID = ?
        GROUP BY m.MaterialName ORDER BY total DESC LIMIT ?
    """, (vendor_id, limit))
    return [(r["MaterialName"], r["total"]) for r in rows]


class VendorsPanel(ctk.CTkFrame):
    def __init__(self, master, project_id):
        super().__init__(master, fg_color="transparent")
        self.project_id = project_id
        self.selected_vendor_id = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 5))
        title_block = ctk.CTkFrame(header, fg_color="transparent")
        title_block.pack(side="left")
        ctk.CTkLabel(title_block, text="Vendors", font=theme.FONT_HEADING, text_color=theme.INK).pack(anchor="w")
        ctk.CTkLabel(title_block, text="Manage vendors, suppliers, and service providers.",
                    font=theme.FONT_SMALL, text_color=theme.MUTED).pack(anchor="w")

        ctk.CTkButton(header, text="+ New Vendor", command=self.open_add_vendor,
                      fg_color=theme.BRASS, hover_color=theme.INK, font=theme.FONT_BODY_BOLD, width=140).pack(
            side="right")

        # Search in the header with Ctrl+K, matching Clients/Projects --
        # no Bell/Help icons, same reasoning as those two modules.
        search_frame = ctk.CTkFrame(header, fg_color=theme.WHITE, corner_radius=8, border_width=1,
                                    border_color=theme.MUTED)
        search_frame.pack(side="right", padx=(0, 20))
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="Search vendor name, category, GST...",
                                         width=260, fg_color="transparent", border_width=0)
        self.search_entry.pack(side="left", padx=(10, 4), pady=4)
        self.search_entry.bind("<KeyRelease>", lambda e: self.refresh())
        ctk.CTkLabel(search_frame, text="Ctrl+K", font=("Segoe UI", 9), text_color=theme.MUTED).pack(
            side="left", padx=(0, 10))

        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=20, pady=(10, 8))

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=20, pady=(0, 18))

        self.status_filter_var = ctk.StringVar(value="All Status")
        ctk.CTkOptionMenu(toolbar, values=["All Status"] + VENDOR_STATUS_OPTIONS,
                          variable=self.status_filter_var, width=130,
                          command=lambda c: self.refresh()).pack(side="left", padx=(0, 8))

        # Category and Partner Type filters -- both real, existing fields
        # on every vendor. No City filter -- there's no separate City
        # column on mstVendor (only a single free-text Address field), so
        # a clean, reliable City filter isn't actually possible without
        # fragile text parsing.
        categories = ["All Categories"] + sorted({v["Category"] for v in db.fetch_all(
            "SELECT DISTINCT Category FROM mstVendor WHERE Category IS NOT NULL")})
        self.category_filter_var = ctk.StringVar(value="All Categories")
        ctk.CTkOptionMenu(toolbar, values=categories, variable=self.category_filter_var, width=150,
                          command=lambda c: self.refresh()).pack(side="left", padx=(0, 8))

        self.partner_type_filter_var = ctk.StringVar(value="All Partner Types")
        ctk.CTkOptionMenu(toolbar, values=["All Partner Types", "Supplier", "Contractor", "Labour Agency"],
                          variable=self.partner_type_filter_var, width=150,
                          command=lambda c: self.refresh()).pack(side="left", padx=(0, 8))

        columns = ctk.CTkFrame(self, fg_color="transparent")
        columns.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        self.table_frame = ctk.CTkFrame(columns, fg_color=theme.WHITE)
        self.table_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        # Added Total Purchases and Projects Worked -- real, computed
        # operational metrics that help prioritize vendors, instead of
        # only contact information. Phone/GST remain in the Details panel.
        cols = ("code", "name", "type", "category", "purchases", "projects", "status", "rating")
        self.tree = ttk.Treeview(self.table_frame, columns=cols, show="headings", height=16)
        headings = {"code": "Vendor Code", "name": "Vendor Name", "type": "Partner Type", "category": "Category",
                    "purchases": "Total Purchases", "projects": "Projects", "status": "Status", "rating": "Rating"}
        widths = {"code": 85, "name": 150, "type": 100, "category": 95, "purchases": 110, "projects": 70,
                  "status": 80, "rating": 70}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c])
        for status, color in STATUS_COLORS.items():
            self.tree.tag_configure(f"status_{status}", foreground=color)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda e: self._open_workspace() if self.selected_vendor_id else None)

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
        details_scroll = ui.AdaptiveScrollFrame(details_panel, fg_color=theme.WHITE)
        details_scroll.pack(fill="both", expand=True)
        self.details_container = details_scroll.content
        self._render_empty_details()

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 15))
        ctk.CTkButton(footer, text="Edit Vendor", command=self.open_edit_vendor,
                      fg_color=theme.INK, font=theme.FONT_SMALL, height=26).pack(side="left", padx=(0, 8))
        ctk.CTkButton(footer, text="Archive Vendor", command=self.delete_vendor,
                      fg_color="#8B2E2E", hover_color="#5E1F1F", font=theme.FONT_SMALL, height=26).pack(side="left")

    def _render_empty_details(self):
        for w in self.details_container.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.details_container, text="Vendor Details", font=theme.FONT_BODY_BOLD,
                    text_color=theme.INK).pack(anchor="w", padx=15, pady=(15, 8))
        ctk.CTkLabel(self.details_container, text="Select a vendor to view:",
                    font=theme.FONT_SMALL, text_color=theme.MUTED, justify="left").pack(
            anchor="w", padx=15, pady=(0, 8))
        for line in ["Purchase Summary", "Projects Worked", "Contact Information",
                    "GST Details", "Recent Transactions"]:
            row = ctk.CTkFrame(self.details_container, fg_color="transparent")
            row.pack(anchor="w", padx=15, pady=2)
            ctk.CTkLabel(row, text="•", font=theme.FONT_SMALL, text_color=theme.BRASS).pack(side="left", padx=(0, 6))
            ctk.CTkLabel(row, text=line, font=theme.FONT_SMALL, text_color=theme.MUTED).pack(side="left")

    def open_quotations(self):
        if self.selected_vendor_id is None:
            messagebox.showinfo("Select a vendor", "Please select a vendor first.", parent=self)
            return
        vendor = db.fetch_one("SELECT VendorID, VendorName FROM mstVendor WHERE VendorID=?", (self.selected_vendor_id,))
        QuotationManagerDialog(self, vendor)

    def refresh(self):
        self._render_stats()
        for row in self.tree.get_children():
            self.tree.delete(row)
        if hasattr(self, "_empty_state_frame"):
            self._empty_state_frame.destroy()
            del self._empty_state_frame

        search = self.search_entry.get().strip().lower()
        status_filter = self.status_filter_var.get()
        category_filter = self.category_filter_var.get()
        partner_type_filter = self.partner_type_filter_var.get()

        # Deliberately NOT filtered to Active=1 here -- that would make
        # Archived vendors unreachable through ANY status filter combination,
        # contradicting the archive feature's own point (reversible via
        # editing Status). Active=1 filtering belongs in the picker
        # dropdowns elsewhere (BOQ/Contract/Material/Purchase), which
        # correctly want only usable vendors -- not in this screen, whose
        # whole job is to let you find and manage every vendor including
        # archived ones.
        vendors = db.fetch_all("SELECT * FROM mstVendor ORDER BY VendorName")
        if search:
            vendors = [v for v in vendors if search in v["VendorName"].lower()
                      or search in (v["Category"] or "").lower()
                      or search in (v["GSTNo"] or "").lower()]
        if status_filter != "All Status":
            vendors = [v for v in vendors if (v["Status"] or "Active") == status_filter]
        if category_filter != "All Categories":
            vendors = [v for v in vendors if v["Category"] == category_filter]
        if partner_type_filter != "All Partner Types":
            vendors = [v for v in vendors if (v["PartnerType"] or "Supplier") == partner_type_filter]

        if not vendors:
            self.tree.pack_forget()
            self._empty_state_frame = ui.empty_state(
                self.table_frame, "No vendors yet.", "+ Add Vendor", self.open_add_vendor)
            return
        self.tree.pack(fill="both", expand=True, side="left")

        for v in vendors:
            status = v["Status"] or "Active"
            rating_display = "★" * int(round(v["Rating"])) if v["Rating"] else "—"
            total_purchase = vendor_total_purchase(v["VendorID"])
            projects_worked = vendor_projects_worked(v["VendorID"])
            self.tree.insert("", "end", iid=v["VendorID"],
                             values=(v["VendorCode"] or "—", v["VendorName"], v["PartnerType"] or "Supplier",
                                    v["Category"] or "—", f"₹{total_purchase:,.0f}", projects_worked,
                                    status, rating_display),
                             tags=(f"status_{status}",))

    def _render_stats(self):
        for w in self.stats_frame.winfo_children():
            w.destroy()
        all_vendors = db.fetch_all("SELECT VendorID, Status, IsPreferred, Rating FROM mstVendor WHERE Active=1")
        total = len(all_vendors)
        active = sum(1 for v in all_vendors if (v["Status"] or "Active") == "Active")
        blacklisted = sum(1 for v in all_vendors if v["Status"] == "Blacklisted")
        preferred = sum(1 for v in all_vendors if v["IsPreferred"])
        total_purchases_all = sum(vendor_total_purchase(v["VendorID"]) for v in all_vendors)
        rated = [v["Rating"] for v in all_vendors if v["Rating"]]
        avg_rating = sum(rated) / len(rated) if rated else 0

        def pct(n):
            return f"{int(round(n / total * 100))}% of total" if total else "0% of total"

        stats = [
            (str(total), "Total Vendors", "All Time", "🏪", "#F5E6D3"),
            (str(active), "Active Vendors", pct(active), "✅", "#D4F0E0"),
            (f"₹{total_purchases_all:,.0f}", "Total Purchases", "All Projects", "🧾", "#D6E8FA"),
            (str(preferred), "Preferred", pct(preferred), "⭐", "#FBF0D6"),
            (f"{avg_rating:.1f}" if rated else "—", "Avg Rating", f"{len(rated)} rated" if rated else "None rated",
             "🌟", "#E8DFF5"),
            (str(blacklisted), "Blacklisted", pct(blacklisted), "⛔", "#FBE0E0"),
        ]
        for col in range(6):
            self.stats_frame.grid_columnconfigure(col, weight=1)
        for col_idx, (value, label, sublabel, icon, bg_color) in enumerate(stats):
            ui.kpi_card(self.stats_frame, value, label, sublabel, icon, bg_color, col_idx)

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        vendor_id = int(sel[0])
        self.selected_vendor_id = vendor_id
        v = db.fetch_one("SELECT * FROM mstVendor WHERE VendorID=?", (vendor_id,))
        total_purchase = vendor_total_purchase(vendor_id)
        materials_total, boq_total = vendor_purchase_breakdown(vendor_id)
        payments_made = vendor_payments_made(vendor_id)
        outstanding = vendor_outstanding(vendor_id)
        projects_worked = vendor_projects_worked(vendor_id)
        first_txn, last_txn = vendor_transaction_dates(vendor_id)
        top_materials = vendor_top_materials(vendor_id)

        for w in self.details_container.winfo_children():
            w.destroy()
        c = self.details_container

        def section_label(text):
            ctk.CTkLabel(c, text=text.upper(), font=("Segoe UI", 9, "bold"), text_color=theme.MUTED).pack(
                anchor="w", padx=15, pady=(14, 4))

        def divider():
            ctk.CTkFrame(c, fg_color=theme.PARCHMENT, height=1).pack(fill="x", padx=15, pady=(4, 0))

        def value_row(label, value, value_color=None):
            row = ctk.CTkFrame(c, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=(6, 0))
            ctk.CTkLabel(row, text=label, font=("Segoe UI", 9), text_color=theme.MUTED, anchor="w").pack(anchor="w")
            ctk.CTkLabel(row, text=value, font=("Segoe UI", 13, "bold"), text_color=value_color or theme.INK,
                        anchor="w", wraplength=310, justify="left").pack(anchor="w")

        # ---------------- Identity ----------------
        header_row = ctk.CTkFrame(c, fg_color="transparent")
        header_row.pack(fill="x", padx=15, pady=(15, 4))
        initials = "".join(w[0].upper() for w in v["VendorName"].split()[:2]) or "?"
        ctk.CTkLabel(header_row, text=initials, font=("Segoe UI", 13, "bold"), text_color=theme.WHITE,
                    fg_color=theme.BRASS, corner_radius=18, width=36, height=36).pack(side="left", padx=(0, 10))
        name_block = ctk.CTkFrame(header_row, fg_color="transparent")
        name_block.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(name_block, text=v["VendorName"], font=("Segoe UI", 16, "bold"), text_color=theme.INK,
                    anchor="w").pack(fill="x")
        ctk.CTkLabel(name_block, text=v["VendorCode"] or "—", font=("Segoe UI", 10), text_color=theme.MUTED,
                    anchor="w").pack(fill="x")
        badges = ctk.CTkFrame(c, fg_color="transparent")
        badges.pack(fill="x", padx=15, pady=(6, 0))
        if v["IsPreferred"]:
            ui.pill_badge(badges, "⭐ Preferred", "#B68100").pack(side="left", padx=(0, 6))
        ui.pill_badge(badges, v["PartnerType"] or "Supplier", "#1E5FA8").pack(side="left")
        if v["Rating"]:
            ctk.CTkLabel(c, text="★" * int(round(v["Rating"])) + f"  ({v['Rating']:.1f}/5)",
                        font=("Segoe UI", 12), text_color=theme.BRASS).pack(anchor="w", padx=15, pady=(6, 0))
        divider()

        # ---------------- Financial Summary (real -- now genuinely computable) ----------------
        section_label("Financial Summary")
        value_row("Total Purchases", f"₹{total_purchase:,.0f}")
        # Breakdown shown only when it's actually informative -- if a
        # vendor has no BOQ items, Total Purchases already equals their
        # material purchases exactly, and a redundant breakdown line
        # would just be clutter. Shown specifically to prevent the exact
        # confusion this was built to address: someone comparing Total
        # Purchases against the Materials screen (which only shows
        # trxMaterialPurchase rows) seeing an unexplained gap.
        if boq_total > 0:
            ctk.CTkLabel(c, text=f"  (₹{materials_total:,.0f} materials + ₹{boq_total:,.0f} BOQ items)",
                        font=("Segoe UI", 9), text_color=theme.MUTED).pack(anchor="w", padx=15)
        value_row("Payments Made", f"₹{payments_made:,.0f}", "#2E8B57")
        value_row("Outstanding", f"₹{outstanding:,.0f}", "#8B2E2E" if outstanding > 0 else theme.INK)
        last_payment = db.fetch_one(
            "SELECT Amount, PaymentDate FROM trxVendorPayment WHERE VendorID=? ORDER BY PaymentDate DESC LIMIT 1",
            (vendor_id,))
        if last_payment:
            value_row("Last Payment", f"₹{last_payment['Amount']:,.0f}  ({last_payment['PaymentDate']})")
        # Real payment-status badge -- purely a comparison of two real
        # numbers already computed above, not a new metric.
        if total_purchase == 0:
            status_text, status_color = "No Purchases Yet", "#6B6B6B"
        elif outstanding <= 0:
            status_text, status_color = "● Fully Paid", "#2E8B57"
        elif payments_made > 0:
            status_text, status_color = "● Partial Payment", "#B68100"
        else:
            status_text, status_color = "● Payment Due", "#8B2E2E"
        ui.pill_badge(c, status_text, status_color).pack(anchor="w", padx=15, pady=(6, 0))
        ctk.CTkButton(c, text="+ Record Payment", command=self._open_record_payment,
                     fg_color=theme.INK, hover_color=theme.BRASS, font=theme.FONT_SMALL, height=26).pack(
            fill="x", padx=15, pady=(8, 0))
        divider()

        # ---------------- Supply Profile (real, derived from purchase history) ----------------
        section_label("Supply Profile")
        value_row("Category", v["Category"] or "—")
        if top_materials:
            ctk.CTkLabel(c, text="Top Materials Supplied", font=("Segoe UI", 9), text_color=theme.MUTED,
                        anchor="w").pack(anchor="w", padx=15, pady=(8, 2))
            for name, amt in top_materials:
                row = ctk.CTkFrame(c, fg_color="transparent")
                row.pack(fill="x", padx=15, pady=1)
                ctk.CTkLabel(row, text=f"• {name}", font=theme.FONT_SMALL, text_color=theme.INK).pack(side="left")
                ctk.CTkLabel(row, text=f"₹{amt:,.0f}", font=theme.FONT_SMALL, text_color=theme.BRASS).pack(side="right")
        else:
            ctk.CTkLabel(c, text="No materials purchased from this vendor yet.", font=theme.FONT_SMALL,
                        text_color=theme.MUTED, wraplength=310, justify="left").pack(anchor="w", padx=15, pady=(6, 0))
        divider()

        # ---------------- Business Relationship ----------------
        section_label("Business Relationship")
        value_row("Projects Worked", str(projects_worked))
        value_row("First Purchase", first_txn or "—")
        value_row("Last Purchase", last_txn or "—")
        divider()

        # ---------------- Contact ----------------
        section_label("Contact")
        value_row("Contact Person", v["ContactPerson"] or "—")
        value_row("Phone", v["Phone"] or "—")
        value_row("Email", v["Email"] or "—")
        value_row("GST No.", v["GSTNo"] or "—")

        # Open Vendor Workspace is now real (built this round) -- primary
        # action, matching the same Open-Workspace-first pattern already
        # established for Clients/Contractors. Manage Quotations stays as
        # a secondary, separate action rather than being folded into or
        # replaced by the workspace, since it's its own real, working
        # screen already.
        ctk.CTkButton(c, text="Open Vendor Workspace  →", command=self._open_workspace,
                     fg_color=theme.BRASS, hover_color=theme.INK, font=("Segoe UI", 12, "bold"), height=32).pack(
            fill="x", padx=15, pady=(14, 6))
        ctk.CTkButton(c, text="Manage Quotations", command=self.open_quotations,
                     fg_color=theme.INK, hover_color=theme.BRASS, font=theme.FONT_SMALL, height=28).pack(
            fill="x", padx=15, pady=(0, 15))

    def _open_workspace(self):
        VendorWorkspace(self, self.selected_vendor_id, on_close=self.refresh)

    def _open_record_payment(self):
        if self.selected_vendor_id is None:
            return
        v = db.fetch_one("SELECT * FROM mstVendor WHERE VendorID=?", (self.selected_vendor_id,))
        RecordVendorPaymentDialog(self, v, on_save=lambda: self._on_select())

    def _selected_vendor_id_or_warn(self):
        if self.selected_vendor_id is None:
            messagebox.showinfo("Select a vendor", "Please select a vendor from the list first.", parent=self)
            return None
        return self.selected_vendor_id

    def open_add_vendor(self):
        VendorForm(self, on_save=self.refresh)

    def open_edit_vendor(self):
        vendor_id = self._selected_vendor_id_or_warn()
        if vendor_id is None:
            return
        vendor = db.fetch_one("SELECT * FROM mstVendor WHERE VendorID=?", (vendor_id,))
        VendorForm(self, on_save=self.refresh, existing=vendor)

    def delete_vendor(self):
        vendor_id = self._selected_vendor_id_or_warn()
        if vendor_id is None:
            return
        in_use = db.fetch_one("SELECT COUNT(*) AS n FROM trxBOQItem WHERE VendorID=?", (vendor_id,))["n"] + \
                 db.fetch_one("SELECT COUNT(*) AS n FROM mstMaterial WHERE VendorID=?", (vendor_id,))["n"] + \
                 db.fetch_one("SELECT COUNT(*) AS n FROM trxContract WHERE VendorID=?", (vendor_id,))["n"]
        # Soft delete (Archive), not a hard DELETE -- a vendor/contractor
        # accumulates real history (contracts, purchases, payments) the
        # moment they're used on a real project. Permanently erasing the
        # master record would orphan or lose that history. "Archived" keeps
        # them out of active-vendor pickers/dropdowns everywhere those
        # already filter on Active=1, without destroying anything.
        if in_use > 0:
            message = (f"This vendor has {in_use} real record(s) attached (contracts, BOQ items, or materials). "
                       f"Archive them instead of deleting -- this removes them from active vendor lists "
                       f"everywhere, but keeps all their history intact. Archive this vendor?")
        else:
            message = "Archive this vendor? This removes them from active vendor lists, but can be reversed later by editing their Status."
        if messagebox.askyesno("Archive vendor", message, parent=self):
            db.execute("UPDATE mstVendor SET Status='Archived', Active=0, ModifiedOn=datetime('now') WHERE VendorID=?", (vendor_id,))
            db.log_activity("System", vendor_id, "Vendor Archived", "")
            self.selected_vendor_id = None
            self.refresh()


class VendorWorkspace(ui.EntityWorkspace):
    """
    Full vendor profile, built on the same EntityWorkspace framework
    already proven for Client and Contractor workspaces -- Overview
    (Financial Summary, Supply Profile, Current Projects, all already
    real), Purchases (real purchase history), Payments (real payment
    history, now genuinely trackable via trxVendorPayment). Deliberately
    NOT built: Quotations (already has its own real screen -- Manage
    Quotations -- duplicating it here would split one feature across two
    places), Documents/Notes (no file storage or notes infrastructure
    exists anywhere in this app), Performance/Analytics (no delivery-
    tracking or price-history data exists to make either honest).
    """
    def __init__(self, master, vendor_id, on_close=None):
        self.vendor_id = vendor_id
        v = db.fetch_one("SELECT * FROM mstVendor WHERE VendorID=?", (vendor_id,))
        tags = [v["PartnerType"] or "Supplier"]
        if v["IsPreferred"]:
            tags.insert(0, "Preferred")
        super().__init__(master, breadcrumb_root="Vendors", entity_name=v["VendorName"],
                         subtitle=v["VendorCode"], tags=tags,
                         quick_actions=[("Edit Vendor", self._edit), ("Record Payment", self._record_payment)],
                         on_close=on_close)
        self.add_tab("Overview", self._build_overview)
        self.add_tab("Purchases", self._build_purchases)
        self.add_tab("Payments", self._build_payments)
        self.build()

    def _edit(self):
        v = db.fetch_one("SELECT * FROM mstVendor WHERE VendorID=?", (self.vendor_id,))
        VendorForm(self, on_save=lambda: None, existing=v)

    def _record_payment(self):
        v = db.fetch_one("SELECT * FROM mstVendor WHERE VendorID=?", (self.vendor_id,))
        RecordVendorPaymentDialog(self, v, on_save=lambda: None)

    def _build_overview(self, parent):
        total_purchase = vendor_total_purchase(self.vendor_id)
        materials_total, boq_total = vendor_purchase_breakdown(self.vendor_id)
        payments_made = vendor_payments_made(self.vendor_id)
        outstanding = vendor_outstanding(self.vendor_id)
        projects_worked = vendor_projects_worked(self.vendor_id)
        top_materials = vendor_top_materials(self.vendor_id)

        stats_row = ctk.CTkFrame(parent, fg_color="transparent")
        stats_row.pack(fill="x", padx=15, pady=(15, 10))
        # Sublabel only shown when it's actually informative -- see the
        # matching note in _on_select for why (no BOQ component means no
        # gap to explain). When it IS shown, every card in this row grows
        # uniformly (not just this one) so the row stays visually
        # consistent -- the same "grow together, not one card alone"
        # principle already established for kpi_card's own fix.
        purchase_sublabel = f"₹{materials_total:,.0f} materials + ₹{boq_total:,.0f} BOQ" if boq_total > 0 else None
        row_height = 104 if purchase_sublabel else 90
        ui.stat_card(stats_row, f"₹{total_purchase:,.0f}", "Total Purchases", purchase_sublabel,
                    height=row_height, sublabel_wrap=150 if purchase_sublabel else None).pack(
            side="left", padx=(0, 12))
        ui.stat_card(stats_row, f"₹{payments_made:,.0f}", "Payments Made", height=row_height).pack(side="left", padx=(0, 12))
        ui.stat_card(stats_row, f"₹{outstanding:,.0f}", "Outstanding", height=row_height).pack(side="left", padx=(0, 12))
        ui.stat_card(stats_row, str(projects_worked), "Projects Worked", height=row_height).pack(side="left", padx=(0, 12))

        # Real "Supplies" -- distinct categories of materials this vendor
        # has actually supplied, not the single Category field alone.
        categories = db.fetch_all(
            "SELECT DISTINCT Category FROM mstMaterial WHERE VendorID=? AND Category IS NOT NULL",
            (self.vendor_id,))
        supply_frame = ctk.CTkFrame(parent, fg_color=theme.WHITE, corner_radius=8)
        supply_frame.pack(fill="x", padx=15, pady=(0, 15))
        ctk.CTkLabel(supply_frame, text="Supply Profile", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=15, pady=(15, 8))
        if categories:
            cat_row = ctk.CTkFrame(supply_frame, fg_color="transparent")
            cat_row.pack(fill="x", padx=15, pady=(0, 8))
            for c in categories:
                ui.pill_badge(cat_row, c["Category"], "#1E5FA8").pack(side="left", padx=(0, 6))
        if top_materials:
            ctk.CTkLabel(supply_frame, text="Top Materials Supplied", font=("Segoe UI", 9),
                        text_color=theme.MUTED).pack(anchor="w", padx=15, pady=(4, 2))
            for name, amt in top_materials:
                row = ctk.CTkFrame(supply_frame, fg_color="transparent")
                row.pack(fill="x", padx=15, pady=1)
                ctk.CTkLabel(row, text=f"• {name}", font=theme.FONT_SMALL, text_color=theme.INK).pack(side="left")
                ctk.CTkLabel(row, text=f"₹{amt:,.0f}", font=theme.FONT_SMALL, text_color=theme.BRASS).pack(side="right")
        ctk.CTkFrame(supply_frame, fg_color="transparent", height=10).pack()

        # Real Current Projects -- active (not completed/cancelled)
        # projects this vendor has supplied materials or BOQ items for.
        current_projects = db.fetch_all("""
            SELECT DISTINCT p.ProjectID, p.ProjectName, p.ProjectStatus FROM tblProject p
            WHERE p.ProjectStatus NOT IN ('Completed', 'Cancelled') AND (
                p.ProjectID IN (SELECT ProjectID FROM mstMaterial WHERE VendorID=?)
                OR p.ProjectID IN (SELECT ProjectID FROM trxBOQItem WHERE VendorID=?)
            )
        """, (self.vendor_id, self.vendor_id))
        proj_frame = ctk.CTkFrame(parent, fg_color=theme.WHITE, corner_radius=8)
        proj_frame.pack(fill="x", padx=15, pady=(0, 15))
        ctk.CTkLabel(proj_frame, text="Current Projects", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=15, pady=(15, 8))
        if not current_projects:
            ctk.CTkLabel(proj_frame, text="No active projects for this vendor right now.", font=theme.FONT_SMALL,
                        text_color=theme.MUTED).pack(anchor="w", padx=15, pady=(0, 15))
        else:
            for p in current_projects:
                row = ctk.CTkFrame(proj_frame, fg_color="transparent")
                row.pack(fill="x", padx=15, pady=3)
                ctk.CTkLabel(row, text=p["ProjectName"], font=theme.FONT_SMALL, text_color=theme.INK).pack(side="left")
                ctk.CTkLabel(row, text=p["ProjectStatus"], font=("Segoe UI", 9), text_color=theme.MUTED).pack(
                    side="right")
            ctk.CTkFrame(proj_frame, fg_color="transparent", height=10).pack()

    def _build_purchases(self, parent):
        purchases = db.fetch_all("""
            SELECT p.PurchaseID, p.PurchaseDate, p.Quantity, p.UnitCost, p.TotalCost, m.MaterialName, m.ProjectID
            FROM trxMaterialPurchase p JOIN mstMaterial m ON p.MaterialID = m.MaterialID
            WHERE m.VendorID=? ORDER BY p.PurchaseDate DESC
        """, (self.vendor_id,))
        if not purchases:
            ui.empty_state(parent, "No purchases recorded from this vendor yet.")
            return
        for pu in purchases:
            project = db.fetch_one("SELECT ProjectName FROM tblProject WHERE ProjectID=?", (pu["ProjectID"],))
            row = ctk.CTkFrame(parent, fg_color=theme.WHITE, corner_radius=6)
            row.pack(fill="x", padx=15, pady=4)
            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", fill="x", expand=True, padx=12, pady=10)
            ctk.CTkLabel(left, text=pu["MaterialName"], font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(anchor="w")
            proj_name = project["ProjectName"] if project else "—"
            ctk.CTkLabel(left, text=f"{pu['PurchaseDate']}  ·  {proj_name}  ·  Qty {pu['Quantity']} @ ₹{pu['UnitCost']:,.0f}",
                        font=theme.FONT_SMALL, text_color=theme.MUTED).pack(anchor="w")
            ctk.CTkLabel(row, text=f"₹{pu['TotalCost']:,.0f}", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
                side="right", padx=12, pady=10)

    def _build_payments(self, parent):
        payments = db.fetch_all(
            "SELECT * FROM trxVendorPayment WHERE VendorID=? ORDER BY PaymentDate DESC", (self.vendor_id,))
        if not payments:
            ui.empty_state(parent, "No payments recorded for this vendor yet.", "+ Record Payment",
                          self._record_payment)
            return
        for pay in payments:
            row = ctk.CTkFrame(parent, fg_color=theme.WHITE, corner_radius=6)
            row.pack(fill="x", padx=15, pady=4)
            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", fill="x", expand=True, padx=12, pady=10)
            ctk.CTkLabel(left, text=pay["PaymentDate"], font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(anchor="w")
            ctk.CTkLabel(left, text=pay["PaymentMode"] or "—", font=theme.FONT_SMALL, text_color=theme.MUTED).pack(anchor="w")
            ctk.CTkLabel(row, text=f"₹{pay['Amount']:,.0f}", font=theme.FONT_BODY_BOLD, text_color="#2E8B57").pack(
                side="right", padx=12, pady=10)


class VendorForm(ui.ScrollableDialog):
    def __init__(self, master, on_save, existing=None):
        super().__init__(master, title="Edit Vendor" if existing else "New Vendor",
                         natural_width=460, natural_height=900)
        self.on_save = on_save
        self.existing = existing

        row = 0
        ctk.CTkLabel(self.body, text=self.title(), font=theme.FONT_SUBHEADING, text_color=theme.INK).grid(
            row=row, column=0, columnspan=2, padx=15, pady=(15, 10), sticky="w")
        row += 1

        fields = [
            ("Vendor Name *", "name_entry", existing["VendorName"] if existing else ""),
            ("Contact Person", "contact_entry", existing["ContactPerson"] if existing and existing["ContactPerson"] else ""),
            ("Address", "address_entry", existing["Address"] if existing and existing["Address"] else ""),
        ]
        self.entries = {}
        for label, key, default in fields:
            ctk.CTkLabel(self.body, text=label, font=theme.FONT_BODY, text_color=theme.INK).grid(
                row=row, column=0, sticky="w", padx=15, pady=8)
            entry = ctk.CTkEntry(self.body, width=250)
            entry.insert(0, default)
            entry.grid(row=row, column=1, padx=15, pady=8)
            self.entries[key] = entry
            row += 1

        # Phone: digits only, matching the same validation Clients already use --
        # this was a real gap (plain free-text entry, no numeric enforcement).
        ctk.CTkLabel(self.body, text="Phone", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.entries["phone_entry"] = ctk.CTkEntry(self.body, width=250, placeholder_text="10-digit mobile number")
        apply_numeric_only(self, self.entries["phone_entry"], max_length=15)
        if existing and existing["Phone"]:
            self.entries["phone_entry"].insert(0, existing["Phone"])
        self.entries["phone_entry"].grid(row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self.body, text="Email", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.entries["email_entry"] = ctk.CTkEntry(self.body, width=250, placeholder_text="name@example.com")
        if existing and existing["Email"]:
            self.entries["email_entry"].insert(0, existing["Email"])
        self.entries["email_entry"].grid(row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self.body, text="GST No.", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.entries["gst_entry"] = ctk.CTkEntry(self.body, width=250, placeholder_text="15-character GSTIN")
        if existing and existing["GSTNo"]:
            self.entries["gst_entry"].insert(0, existing["GSTNo"])
        self.entries["gst_entry"].grid(row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self.body, text="Partner Type *", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.partner_type_var = ctk.StringVar(
            value=(existing["PartnerType"] if existing and existing["PartnerType"] else "Supplier"))
        ctk.CTkOptionMenu(self.body, values=PARTNER_TYPE_OPTIONS, variable=self.partner_type_var, width=250,
                          command=self._on_partner_type_change).grid(row=row, column=1, padx=15, pady=8)
        row += 1
        ctk.CTkLabel(self.body, text="The business relationship (Supplier, Contractor, Consultant...). "
                                 "What they actually work on goes in Scope of Work below.",
                     font=theme.FONT_SMALL, text_color=theme.MUTED, wraplength=380, justify="left").grid(
            row=row, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 6))
        row += 1

        self.category_label = ctk.CTkLabel(self.body, text="Product Category (Suppliers only)", font=theme.FONT_BODY,
                                           text_color=theme.INK)
        self.category_label.grid(row=row, column=0, sticky="w", padx=15, pady=8)
        self.category_var = ctk.StringVar(
            value=(existing["Category"] if existing and existing["Category"] in PRODUCT_CATEGORY_OPTIONS
                  else PRODUCT_CATEGORY_OPTIONS[0]))
        self.category_menu = ctk.CTkOptionMenu(self.body, values=PRODUCT_CATEGORY_OPTIONS, variable=self.category_var, width=250)
        self.category_menu.grid(row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self.body, text="Scope of Work", font=theme.FONT_BODY_BOLD, text_color=theme.INK).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=15, pady=(10, 6))
        row += 1
        all_scope_items = db.fetch_all("SELECT ScopeID, ScopeName FROM mstScopeOfWork ORDER BY ScopeName")
        scope_by_name = {item["ScopeName"]: item["ScopeID"] for item in all_scope_items}
        existing_scope_ids = set()
        if existing:
            existing_scope_ids = {r["ScopeID"] for r in db.fetch_all(
                "SELECT ScopeID FROM trxVendorScope WHERE VendorID=?", (existing["VendorID"],))}

        scope_outer = ctk.CTkFrame(self.body, fg_color="transparent")
        scope_outer.grid(row=row, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 10))
        self.scope_vars = {}
        self._scope_group_frames = {}
        for group_name, item_names in SCOPE_GROUPS.items():
            self._build_scope_group(scope_outer, group_name, item_names, scope_by_name, existing_scope_ids)
        row += 1

        ctk.CTkLabel(self.body, text="Status", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.status_var = ctk.StringVar(value=(existing["Status"] if existing and existing["Status"] else "Active"))
        ctk.CTkOptionMenu(self.body, values=VENDOR_STATUS_OPTIONS, variable=self.status_var, width=250).grid(
            row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self.body, text="Rating (0-5)", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.rating_var = ctk.StringVar(value=(str(existing["Rating"]) if existing and existing["Rating"] else "0"))
        ctk.CTkOptionMenu(self.body, values=["0", "1", "2", "3", "4", "5"], variable=self.rating_var, width=250).grid(
            row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkButton(self.body, text="Save", command=self.save, fg_color=theme.BRASS,
                      hover_color=theme.INK, font=theme.FONT_BODY_BOLD).grid(
            row=row, column=0, columnspan=2, pady=20)

        self._on_partner_type_change(self.partner_type_var.get())

    def _build_scope_group(self, parent, group_name, item_names, scope_by_name, existing_scope_ids):
        # A group starts expanded if any of its items are already checked
        # (so an existing vendor's selections are visible on open), collapsed
        # otherwise -- avoids a wall of 26 checkboxes for a new vendor.
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

    def _on_partner_type_change(self, choice):
        """Product Category only makes sense for Suppliers -- hide it otherwise."""
        if choice == "Supplier":
            self.category_label.grid()
            self.category_menu.grid()
        else:
            self.category_label.grid_remove()
            self.category_menu.grid_remove()

    def save(self):
        name = self.entries["name_entry"].get().strip()
        if not name:
            messagebox.showerror("Missing field", "Vendor Name is required.", parent=self)
            return

        # Category only makes sense for Suppliers -- don't overwrite it with a
        # stale Supplier-only value if the partner type isn't Supplier. Existing
        # historical Category data for non-Suppliers is preserved untouched
        # (from before this field split), not cleared.
        partner_type = self.partner_type_var.get()
        category = self.category_var.get().strip() if partner_type == "Supplier" else \
                   (self.existing["Category"] if self.existing else None)
        contact = self.entries["contact_entry"].get().strip()
        phone = self.entries["phone_entry"].get().strip()
        email = self.entries["email_entry"].get().strip()
        gst = self.entries["gst_entry"].get().strip()
        address = self.entries["address_entry"].get().strip()
        rating = float(self.rating_var.get())

        if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            messagebox.showerror("Invalid email", "Please enter a valid email address.", parent=self)
            return
        if gst and len(gst) != 15:
            messagebox.showerror("Invalid GST No.", "GSTIN must be exactly 15 characters.", parent=self)
            return

        if self.existing:
            vendor_id = self.existing["VendorID"]
            # Active is always derived from Status, never set independently --
            # otherwise editing Status back to "Active" (the actual restore
            # path for an archived vendor) would update the Status text but
            # leave Active=0, keeping them invisible in every picker dropdown
            # despite showing "Active". Same logic applies to Inactive/
            # Blacklisted, which should equally exclude a vendor from active
            # pickers, not just Archived.
            active_flag = 1 if self.status_var.get() == "Active" else 0
            db.execute(
                """UPDATE mstVendor SET VendorName=?, Category=?, PartnerType=?, ContactPerson=?, Phone=?, Email=?, GSTNo=?,
                   Address=?, Status=?, Active=?, Rating=?, ModifiedOn=datetime('now') WHERE VendorID=?""",
                (name, category, partner_type, contact, phone, email, gst, address,
                 self.status_var.get(), active_flag, rating, vendor_id)
            )
            db.log_activity("System", vendor_id, "Vendor Updated", name)
        else:
            active_flag = 1 if self.status_var.get() == "Active" else 0
            vendor_id = db.execute(
                "INSERT INTO mstVendor (VendorName, Category, PartnerType, ContactPerson, Phone, Email, GSTNo, Address, Status, Active, Rating, CreatedOn, ModifiedOn) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))",
                (name, category, partner_type, contact, phone, email, gst, address,
                 self.status_var.get(), active_flag, rating)
            )
            code = f"VEN-{vendor_id:04d}"
            db.execute("UPDATE mstVendor SET VendorCode=? WHERE VendorID=?", (code, vendor_id))
            db.log_activity("System", vendor_id, "Vendor Added", name)

        # Scope of Work: replace the full selection each save (simplest correct
        # approach for a checklist -- delete then re-insert what's checked now).
        db.execute("DELETE FROM trxVendorScope WHERE VendorID=?", (vendor_id,))
        for scope_id, var in self.scope_vars.items():
            if var.get():
                db.execute("INSERT INTO trxVendorScope (VendorID, ScopeID) VALUES (?,?)", (vendor_id, scope_id))

        self.on_save()
        self.destroy()


UNIT_OPTIONS = ["Sq.ft", "RFT", "Nos.", "Fixed Amount", "CFT", "Cum", "Kg", "Custom"]
# Board Calculation deliberately NOT included -- formula confirmed (BR-006 in
# BUSINESS_RULES.md) but implementation explicitly deferred to v4.5.0 per the
# agreed phased roadmap.


class RecordVendorPaymentDialog(ctk.CTkToplevel):
    """Real, functional dialog to record an actual payment against a vendor -- the only way Payments Made/
    Outstanding become genuinely real numbers instead of always reading zero."""
    def __init__(self, master, vendor, on_save):
        super().__init__(master)
        self.vendor = vendor
        self.on_save = on_save
        self.title(f"Record Payment -- {vendor['VendorName']}")
        self.geometry("380x320")
        self.configure(fg_color=theme.PARCHMENT)
        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(self, text=f"Record Payment to {vendor['VendorName']}", font=theme.FONT_BODY_BOLD,
                    text_color=theme.INK).pack(anchor="w", padx=20, pady=(20, 15))

        outstanding = vendor_outstanding(vendor["VendorID"])
        ctk.CTkLabel(self, text=f"Current Outstanding: ₹{outstanding:,.0f}", font=theme.FONT_SMALL,
                    text_color=theme.MUTED).pack(anchor="w", padx=20, pady=(0, 15))

        ctk.CTkLabel(self, text="Amount", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.amount_entry = ctk.CTkEntry(self, width=300)
        self.amount_entry.pack(padx=20, pady=(2, 12))

        ctk.CTkLabel(self, text="Payment Date", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.date_entry = DateEntry(self, width=25, date_pattern="yyyy-mm-dd", background=theme.BRASS,
                                    foreground="white", borderwidth=1)
        self.date_entry.pack(anchor="w", padx=20, pady=(2, 12))

        ctk.CTkLabel(self, text="Payment Mode", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.mode_var = ctk.StringVar(value="Bank Transfer")
        ctk.CTkOptionMenu(self, values=["Bank Transfer", "Cheque", "Cash", "UPI", "Other"],
                         variable=self.mode_var, width=300).pack(padx=20, pady=(2, 12))

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
        db.execute("INSERT INTO trxVendorPayment (VendorID, Amount, PaymentDate, PaymentMode) VALUES (?,?,?,?)",
                  (self.vendor["VendorID"], amount, self.date_entry.get_date().isoformat(), self.mode_var.get()))
        db.log_activity("Vendor", self.vendor["VendorID"], "Payment Recorded")
        self.on_save()
        self.destroy()


class QuotationManagerDialog(ctk.CTkToplevel):
    """
    Manages a Business Partner's Default Quotations (BR-002: these are
    reusable templates, never referenced live by a project -- a Project
    Contract COPIES a quotation's items at creation time).
    """
    def __init__(self, master, vendor):
        super().__init__(master)
        self.transient(self.master.winfo_toplevel())
        self.vendor = vendor
        self.title(f"Quotations — {vendor['VendorName']}")
        self.geometry("620x560")
        self.configure(fg_color=theme.PARCHMENT)
        self.grab_set()

        ctk.CTkLabel(self, text=f"Default Quotations — {vendor['VendorName']}", font=theme.FONT_SUBHEADING,
                     text_color=theme.INK).pack(anchor="w", padx=20, pady=(15, 10))

        ctk.CTkButton(self, text="+ New Quotation Version", command=self._new_quotation,
                      fg_color=theme.BRASS, hover_color=theme.INK, font=theme.FONT_SMALL, height=28).pack(
            anchor="w", padx=20, pady=(0, 10))

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color=theme.WHITE)
        self.list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        self.refresh()

    def refresh(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        quotations = db.fetch_all(
            "SELECT * FROM mstPartnerQuotation WHERE VendorID=? ORDER BY VersionNumber DESC", (self.vendor["VendorID"],))
        if not quotations:
            ctk.CTkLabel(self.list_frame, text="No quotations yet.", font=theme.FONT_SMALL,
                        text_color=theme.MUTED).pack(pady=10)
            return
        for q in quotations:
            items = db.fetch_all("SELECT * FROM mstPartnerQuotationItem WHERE QuotationID=?", (q["QuotationID"],))
            card = ctk.CTkFrame(self.list_frame, fg_color=theme.PARCHMENT, corner_radius=6)
            card.pack(fill="x", pady=5, padx=5)
            header = ctk.CTkFrame(card, fg_color="transparent")
            header.pack(fill="x", padx=10, pady=(8, 4))
            active_tag = " (Active)" if q["IsActive"] else ""
            ctk.CTkLabel(header, text=f"v{q['VersionNumber']} — {q['QuotationName'] or 'Untitled'}{active_tag}",
                        font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(side="left")
            ctk.CTkButton(header, text="+ Add Item", command=lambda qid=q["QuotationID"]: self._add_item(qid),
                         fg_color=theme.INK, font=("Segoe UI", 9), height=22, width=70).pack(side="right")
            for item in items:
                ctk.CTkLabel(card, text=f"  • {item['ItemName']} — {item['Unit']} — ₹{item['DefaultRate']:,.2f}",
                            font=theme.FONT_SMALL, text_color=theme.INK, anchor="w").pack(fill="x", padx=10)
            if not items:
                ctk.CTkLabel(card, text="  No items yet.", font=theme.FONT_SMALL, text_color=theme.MUTED,
                            anchor="w").pack(fill="x", padx=10, pady=(0, 8))
            else:
                ctk.CTkFrame(card, fg_color="transparent", height=8).pack()

    def _new_quotation(self):
        latest = db.fetch_one(
            "SELECT MAX(VersionNumber) AS v FROM mstPartnerQuotation WHERE VendorID=?", (self.vendor["VendorID"],))
        next_version = (latest["v"] or 0) + 1
        db.execute("INSERT INTO mstPartnerQuotation (VendorID, VersionNumber, QuotationName) VALUES (?,?,?)",
                   (self.vendor["VendorID"], next_version, f"Quotation v{next_version}"))
        db.log_activity("System", self.vendor["VendorID"], "Quotation Created", f"v{next_version}")
        self.refresh()

    def _add_item(self, quotation_id):
        AddQuotationItemDialog(self, quotation_id, on_save=self.refresh)


class AddQuotationItemDialog(ctk.CTkToplevel):
    def __init__(self, master, quotation_id, on_save):
        super().__init__(master)
        self.transient(self.master.winfo_toplevel())
        self.quotation_id = quotation_id
        self.on_save = on_save
        self.title("Add Quotation Item")
        self.geometry("380x320")
        self.configure(fg_color=theme.PARCHMENT)
        self.grab_set()

        ctk.CTkLabel(self, text="Item Name *", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20, pady=(15, 0))
        self.name_entry = ctk.CTkEntry(self, width=300)
        self.name_entry.pack(padx=20, pady=(0, 10))

        ctk.CTkLabel(self, text="Unit", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.unit_var = ctk.StringVar(value=UNIT_OPTIONS[0])
        ctk.CTkOptionMenu(self, values=UNIT_OPTIONS, variable=self.unit_var, width=300).pack(padx=20, pady=(0, 10))

        ctk.CTkLabel(self, text="Default Rate (₹) *", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.rate_entry = ctk.CTkEntry(self, width=300)
        apply_decimal_only(self, self.rate_entry)
        self.rate_entry.pack(padx=20, pady=(0, 15))

        ctk.CTkButton(self, text="Add Item", command=self.save, fg_color=theme.BRASS,
                     hover_color=theme.INK, font=theme.FONT_BODY_BOLD).pack(pady=10)

    def save(self):
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showerror("Missing name", "Item Name is required.", parent=self)
            return
        try:
            rate = float(self.rate_entry.get().strip() or 0)
        except ValueError:
            messagebox.showerror("Invalid number", "Default Rate must be a number.", parent=self)
            return
        db.execute("INSERT INTO mstPartnerQuotationItem (QuotationID, ItemName, Unit, DefaultRate) VALUES (?,?,?,?)",
                   (self.quotation_id, name, self.unit_var.get(), rate))
        self.on_save()
        self.destroy()

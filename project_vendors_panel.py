"""
ADS OS Desktop -- Project-scoped Vendors panel.

Real bug fix: the "Vendors" tab inside a project's Commercial section was
previously just the global VendorsPanel (the same one used for the
company-wide sidebar screen) -- it accepted project_id but never actually
used it to filter anything, showing every vendor in the whole business
regardless of which project you were looking at, with Total Purchases
and every other figure computed all-time/all-projects. Inside a specific
project, that's the wrong question to answer: what you actually want to
know is "who has supplied THIS project" -- not "here's everyone we've
ever bought from." Same bug already fixed once for Contractors
(see project_contractors_panel.py); this is the vendor counterpart.

One real difference from Contractors: a contractor is linked to a
project through an explicit trxContract record, so that panel offers a
genuine "+ Assign Contractor" action. Vendors have no equivalent
assignment table -- a vendor becomes linked to a project only by being
referenced on a real trxBOQItem or mstMaterial row for that project,
which happens naturally through the BOQ and Materials screens. So this
panel is deliberately read/derived: no "assign" action, just the real,
filtered list, with a link out to those screens for anyone not showing
up yet.

Second real difference: trxVendorPayment has no ProjectID, and its
PurchaseID column is never actually populated by the Record Payment
dialog (RecordVendorPaymentDialog always leaves it NULL). That means
Payments Made / Outstanding genuinely cannot be attributed to one
project with the data that exists today -- showing a "per-project"
number there would be fabricated, not computed. So this panel shows
real, project-scoped Total Purchases, but leaves Payments/Outstanding
to the vendor's global workspace, clearly labeled there as all-project
figures -- same honesty principle vendors_panel.py already applies by
omitting numbers it can't back up.
"""
import customtkinter as ctk
from tkinter import ttk
import theme
import db
import ui_components as ui
from vendors_panel import VendorForm, VendorWorkspace


def vendor_ids_for_project(project_id):
    """
    Real vendor IDs linked to this project -- via a real trxBOQItem or
    mstMaterial row carrying both ProjectID and VendorID. These are the
    only two places that linkage exists; there is no separate
    project-vendor assignment table.
    """
    boq_vendors = {r["VendorID"] for r in db.fetch_all(
        "SELECT DISTINCT VendorID FROM trxBOQItem WHERE ProjectID=? AND VendorID IS NOT NULL",
        (project_id,))}
    material_vendors = {r["VendorID"] for r in db.fetch_all(
        "SELECT DISTINCT VendorID FROM mstMaterial WHERE ProjectID=? AND VendorID IS NOT NULL",
        (project_id,))}
    return boq_vendors | material_vendors


def vendor_purchase_breakdown_for_project(vendor_id, project_id):
    """
    Real (materials_total, boq_total) for one vendor, scoped to a single
    project -- the project-specific counterpart to vendors_panel.py's
    vendor_purchase_breakdown(), which deliberately aggregates across
    every project a vendor has ever supplied.
    """
    material_total = db.fetch_one("""
        SELECT COALESCE(SUM(p.TotalCost), 0) AS total FROM trxMaterialPurchase p
        JOIN mstMaterial m ON p.MaterialID = m.MaterialID
        WHERE m.VendorID = ? AND m.ProjectID = ?
    """, (vendor_id, project_id))["total"]
    boq_total = db.fetch_one(
        "SELECT COALESCE(SUM(Amount), 0) AS total FROM trxBOQItem WHERE VendorID = ? AND ProjectID = ?",
        (vendor_id, project_id))["total"]
    return material_total, boq_total


def vendor_purchase_for_project(vendor_id, project_id):
    material_total, boq_total = vendor_purchase_breakdown_for_project(vendor_id, project_id)
    return material_total + boq_total


def vendor_last_transaction_for_project(vendor_id, project_id):
    """Real most-recent purchase/BOQ date for this vendor on THIS project only. (None if none yet.)"""
    dates = [r["PurchaseDate"] for r in db.fetch_all("""
        SELECT p.PurchaseDate FROM trxMaterialPurchase p JOIN mstMaterial m ON p.MaterialID = m.MaterialID
        WHERE m.VendorID = ? AND m.ProjectID = ? AND p.PurchaseDate IS NOT NULL
    """, (vendor_id, project_id))]
    dates += [r["CreatedOn"] for r in db.fetch_all(
        "SELECT CreatedOn FROM trxBOQItem WHERE VendorID=? AND ProjectID=? AND CreatedOn IS NOT NULL",
        (vendor_id, project_id))]
    return max(dates)[:10] if dates else None


class ProjectVendorsPanel(ctk.CTkFrame):
    def __init__(self, master, project_id):
        super().__init__(master, fg_color="transparent")
        self.project_id = project_id
        self.selected_vendor_id = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(15, 5))
        ctk.CTkLabel(header, text="Vendors", font=theme.FONT_HEADING, text_color=theme.INK).pack(side="left")
        ctk.CTkButton(header, text="+ New Vendor", command=self.open_new_vendor, fg_color=theme.BRASS,
                     hover_color=theme.INK, font=theme.FONT_BODY_BOLD, height=28).pack(side="right")
        ctk.CTkLabel(self, text="Vendors who have supplied materials or BOQ items on this project -- a "
                                "vendor appears here automatically once used in BOQ or Materials for this "
                                "project. For the full company-wide list, use Vendors in the main sidebar.",
                     font=theme.FONT_SMALL, text_color=theme.MUTED, wraplength=700, justify="left").pack(
            anchor="w", padx=20, pady=(0, 10))

        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=20, pady=(0, 10))

        columns = ctk.CTkFrame(self, fg_color="transparent")
        columns.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        self.table_frame = ctk.CTkFrame(columns, fg_color=theme.WHITE)
        self.table_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        cols = ("code", "name", "type", "category", "purchases", "status")
        self.tree = ttk.Treeview(self.table_frame, columns=cols, show="headings", height=14)
        headings = {"code": "Vendor Code", "name": "Vendor Name", "type": "Partner Type", "category": "Category",
                    "purchases": "Total Purchases (this project)", "status": "Status"}
        widths = {"code": 90, "name": 150, "type": 100, "category": 95, "purchases": 190, "status": 80}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c])
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda e: self.open_workspace() if self.selected_vendor_id else None)
        scrollbar = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True, side="left")

        self.details_panel = ctk.CTkFrame(columns, fg_color=theme.WHITE, corner_radius=8, width=280)
        self.details_panel.pack(side="left", fill="y")
        self.details_panel.pack_propagate(False)
        self._render_empty_details()

    def _render_empty_details(self):
        for w in self.details_panel.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.details_panel, text="Select a vendor to see details. If a vendor you expect "
                                              "isn't listed, they haven't been used in BOQ or Materials "
                                              "on this project yet.", font=theme.FONT_SMALL,
                    text_color=theme.MUTED, justify="left", wraplength=240).pack(anchor="w", padx=15, pady=15)

    def refresh(self):
        for w in self.stats_frame.winfo_children():
            w.destroy()
        for row in self.tree.get_children():
            self.tree.delete(row)
        if hasattr(self, "_empty_state_frame"):
            self._empty_state_frame.destroy()
            del self._empty_state_frame

        vendor_ids = vendor_ids_for_project(self.project_id)
        vendors = [db.fetch_one("SELECT * FROM mstVendor WHERE VendorID=?", (vid,)) for vid in vendor_ids]
        vendors = [v for v in vendors if v is not None]
        vendors.sort(key=lambda v: v["VendorName"])

        total_purchases_all = sum(vendor_purchase_for_project(v["VendorID"], self.project_id) for v in vendors)
        active = sum(1 for v in vendors if (v["Status"] or "Active") == "Active")

        stats = [
            (str(len(vendors)), "Vendors on this Project", None),
            (str(active), "Active", None),
            (f"₹{total_purchases_all:,.0f}", "Total Purchases", "This project"),
        ]
        for value, label, sublabel in stats:
            ui.stat_card(self.stats_frame, value, label, sublabel).pack(side="left", padx=(0, 12))

        if not vendors:
            self.tree.pack_forget()
            self._empty_state_frame = ui.empty_state(
                self.table_frame, "No vendors used on this project yet -- add one via BOQ or Materials, "
                                   "or create a new vendor to use there.", "+ New Vendor", self.open_new_vendor)
            return
        self.tree.pack(fill="both", expand=True, side="left")

        for v in vendors:
            purchase_total = vendor_purchase_for_project(v["VendorID"], self.project_id)
            self.tree.insert("", "end", iid=v["VendorID"],
                             values=(v["VendorCode"] or "—", v["VendorName"], v["PartnerType"] or "Supplier",
                                    v["Category"] or "—", f"₹{purchase_total:,.0f}", v["Status"] or "Active"))

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        vendor_id = int(sel[0])
        self.selected_vendor_id = vendor_id
        v = db.fetch_one("SELECT * FROM mstVendor WHERE VendorID=?", (vendor_id,))
        materials_total, boq_total = vendor_purchase_breakdown_for_project(vendor_id, self.project_id)
        purchase_total = materials_total + boq_total
        last_txn = vendor_last_transaction_for_project(vendor_id, self.project_id)

        for w in self.details_panel.winfo_children():
            w.destroy()
        c = self.details_panel
        ctk.CTkLabel(c, text=v["VendorName"], font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=15, pady=(15, 2))
        ctk.CTkLabel(c, text=v["PartnerType"] or "Supplier", font=theme.FONT_SMALL,
                    text_color=theme.MUTED).pack(anchor="w", padx=15, pady=(0, 10))

        info_rows = [("Total Purchases (this project)", f"₹{purchase_total:,.0f}")]
        if boq_total > 0:
            info_rows.append(("  Breakdown", f"₹{materials_total:,.0f} materials + ₹{boq_total:,.0f} BOQ"))
        info_rows.append(("Last Transaction (this project)", last_txn or "—"))
        info_rows.append(("Contact", v["Phone"] or v["Email"] or "—"))
        for label, val in info_rows:
            ctk.CTkLabel(c, text=label, font=("Segoe UI", 9), text_color=theme.MUTED).pack(
                anchor="w", padx=15, pady=(6, 0))
            ctk.CTkLabel(c, text=val, font=theme.FONT_SMALL, text_color=theme.INK, wraplength=240,
                        justify="left").pack(anchor="w", padx=15)

        # Payments Made / Outstanding deliberately NOT shown here -- see
        # module docstring. trxVendorPayment carries no ProjectID and its
        # PurchaseID is never populated, so there is no honest way to
        # attribute a payment to this specific project. Full, real
        # (all-project) payment figures live in the Vendor Workspace.
        ctk.CTkLabel(c, text="Payments Made / Outstanding are recorded at the vendor level, not per "
                             "project -- see full figures in Vendor Workspace.", font=("Segoe UI", 9),
                    text_color=theme.MUTED, wraplength=240, justify="left").pack(
            anchor="w", padx=15, pady=(10, 0))

        ctk.CTkButton(c, text="Open Vendor Workspace  →", command=self.open_workspace,
                     fg_color=theme.BRASS, hover_color=theme.INK, font=("Segoe UI", 12, "bold"), height=32).pack(
            fill="x", padx=15, pady=(15, 15))

    def open_workspace(self):
        if self.selected_vendor_id is None:
            return
        VendorWorkspace(self, self.selected_vendor_id, on_close=self.refresh)

    def open_new_vendor(self):
        # Creates in the global vendor master, same VendorForm the
        # company-wide Vendors screen uses -- a brand-new vendor won't
        # appear in this project's list until they're actually used on a
        # BOQ item or Material here, same as everywhere else in the app.
        VendorForm(self, on_save=self.refresh)

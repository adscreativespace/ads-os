"""
ADS OS Desktop -- Commercial Reports (Commercial module, sixth of six)
Pure aggregation over the five modules already built -- no new tables needed.

Deliberately narrower than the reference mockup. Built: Total Invoiced/
Received/Outstanding (from Invoice Center), Total Direct Costs (BOQ + real
Material purchases), Gross Margin (= Invoiced - Direct Costs, labeled
precisely as that, not "Net Profit"), real Receivables Aging (bucketed from
actual invoice due dates), and Top Vendors by Purchase (reusing the same
computation from the Vendors module).

NOT built, with reasons:
  - Tax Summary (CGST/SGST/IGST split) -- Fee Calculator only stores a single
    GST %, no itemized tax breakdown exists to report on.
  - Cash Flow Summary with Opening/Closing Balance -- needs a full cash
    ledger (all money in and out); only invoice payments are tracked as
    money in, and no vendor-payment/expense-out tracking exists yet.
  - Key Financial Ratios (Current Ratio, Payables Turnover, etc.) -- needs a
    real accounting model (assets/liabilities) this app doesn't have.
  - Project Comparison -- every Commercial module lives inside a single
    project's workspace; comparing across projects needs an app-level
    Reports area, not a tab nested in one project. Separate future feature.
  - "Net Profit" -- what the mockup calls this doesn't account for overheads,
    labor, or indirect costs, none of which are tracked. Calling a number
    "Net Profit" without that data would be a real, misleading overclaim.
"""
import customtkinter as ctk
from tkinter import ttk
import datetime
import db
import theme
from vendors_panel import vendor_total_purchase


class CommercialReportsPanel(ctk.CTkFrame):
    def __init__(self, master, project_id):
        super().__init__(master, fg_color="transparent")
        self.project_id = project_id
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        ctk.CTkLabel(self, text="Commercial Reports", font=theme.FONT_HEADING, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 5))
        ctk.CTkLabel(self, text="Financial overview for this project, built from Fee Calculator, BOQ, Materials, "
                                 "Vendors, and Invoice Center data.",
                     font=theme.FONT_SMALL, text_color=theme.MUTED, wraplength=700, justify="left").pack(
            anchor="w", padx=20, pady=(0, 10))

        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=20, pady=(0, 15))

        columns = ctk.CTkFrame(self, fg_color="transparent")
        columns.pack(fill="both", expand=True, padx=20)

        left = ctk.CTkFrame(columns, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right = ctk.CTkFrame(columns, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        # ---------------- LEFT: Cost breakdown + Receivables Aging ----------------
        cost_card = ctk.CTkFrame(left, fg_color=theme.WHITE, corner_radius=8)
        cost_card.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(cost_card, text="Cost Breakdown", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=15, pady=(15, 8))
        self.cost_label = ctk.CTkLabel(cost_card, text="", font=theme.FONT_BODY, text_color=theme.INK, justify="left")
        self.cost_label.pack(anchor="w", padx=15, pady=(0, 15))

        aging_card = ctk.CTkFrame(left, fg_color=theme.WHITE, corner_radius=8)
        aging_card.pack(fill="both", expand=True)
        ctk.CTkLabel(aging_card, text="Receivables Aging", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=15, pady=(15, 8))
        aging_cols = ("bucket", "amount")
        self.aging_tree = ttk.Treeview(aging_card, columns=aging_cols, show="headings", height=6)
        self.aging_tree.heading("bucket", text="Aging")
        self.aging_tree.heading("amount", text="Amount (₹)")
        self.aging_tree.column("bucket", width=150)
        self.aging_tree.column("amount", width=120)
        self.aging_tree.pack(fill="x", padx=15, pady=(0, 15))

        # ---------------- RIGHT: Top Vendors ----------------
        vendor_card = ctk.CTkFrame(right, fg_color=theme.WHITE, corner_radius=8)
        vendor_card.pack(fill="both", expand=True)
        ctk.CTkLabel(vendor_card, text="Top Vendors by Purchase (This Project)", font=theme.FONT_BODY_BOLD,
                     text_color=theme.INK).pack(anchor="w", padx=15, pady=(15, 8))
        vendor_cols = ("name", "category", "amount")
        self.vendor_tree = ttk.Treeview(vendor_card, columns=vendor_cols, show="headings", height=10)
        self.vendor_tree.heading("name", text="Vendor")
        self.vendor_tree.heading("category", text="Category")
        self.vendor_tree.heading("amount", text="Purchase Value (₹)")
        self.vendor_tree.column("name", width=160)
        self.vendor_tree.column("category", width=100)
        self.vendor_tree.column("amount", width=130)
        self.vendor_tree.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        ctk.CTkLabel(self, text="Note: this report covers Fee Calculator, BOQ, Materials, Vendors, and Invoice "
                                 "Center data only. It does not include indirect overheads, labor, itemized tax "
                                 "breakdowns, or costs recorded outside these modules.",
                     font=theme.FONT_SMALL, text_color=theme.MUTED, wraplength=700, justify="left").pack(
            anchor="w", padx=20, pady=(10, 15))

    def refresh(self):
        # ---------------- Real aggregates ----------------
        invoices = db.fetch_all("SELECT * FROM trxInvoice WHERE ProjectID=? AND Status != 'Cancelled'", (self.project_id,))
        total_invoiced = sum(i["Amount"] for i in invoices)
        total_received = 0
        outstanding_by_bucket = {"0-30 Days": 0, "31-60 Days": 0, "61-90 Days": 0, "90+ Days": 0}
        today = datetime.date.today()

        for inv in invoices:
            paid = db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS total FROM trxInvoicePayment WHERE InvoiceID=?",
                                (inv["InvoiceID"],))["total"]
            total_received += paid
            balance = inv["Amount"] - paid
            if balance > 0.01 and inv["DueDate"]:
                try:
                    due = datetime.date.fromisoformat(inv["DueDate"])
                    days_overdue = (today - due).days
                except ValueError:
                    days_overdue = 0
                if days_overdue <= 30:
                    outstanding_by_bucket["0-30 Days"] += balance
                elif days_overdue <= 60:
                    outstanding_by_bucket["31-60 Days"] += balance
                elif days_overdue <= 90:
                    outstanding_by_bucket["61-90 Days"] += balance
                else:
                    outstanding_by_bucket["90+ Days"] += balance
            elif balance > 0.01:
                outstanding_by_bucket["0-30 Days"] += balance

        total_outstanding = total_invoiced - total_received

        boq_cost = db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS total FROM trxBOQItem WHERE ProjectID=?",
                                (self.project_id,))["total"]
        material_cost = db.fetch_one("""
            SELECT COALESCE(SUM(p.TotalCost),0) AS total FROM trxMaterialPurchase p
            JOIN mstMaterial m ON p.MaterialID = m.MaterialID WHERE m.ProjectID=?
        """, (self.project_id,))["total"]
        total_direct_cost = boq_cost + material_cost
        gross_margin = total_invoiced - total_direct_cost
        gross_margin_pct = (gross_margin / total_invoiced * 100) if total_invoiced else 0

        # ---------------- Stat cards ----------------
        for w in self.stats_frame.winfo_children():
            w.destroy()
        stats = [
            ("Total Invoiced", f"₹{total_invoiced:,.2f}"),
            ("Total Received", f"₹{total_received:,.2f}"),
            ("Outstanding", f"₹{total_outstanding:,.2f}"),
            ("Total Direct Costs", f"₹{total_direct_cost:,.2f}"),
            ("Gross Margin", f"₹{gross_margin:,.2f}"),
            ("Gross Margin %", f"{gross_margin_pct:.1f}%"),
        ]
        for label, value in stats:
            card = ctk.CTkFrame(self.stats_frame, fg_color=theme.WHITE, corner_radius=8, width=150, height=70)
            card.pack(side="left", padx=(0, 10))
            card.pack_propagate(False)
            ctk.CTkLabel(card, text=value, font=theme.FONT_BODY_BOLD, text_color=theme.BRASS).pack(pady=(10, 0))
            ctk.CTkLabel(card, text=label, font=theme.FONT_SMALL, text_color=theme.MUTED).pack()

        # ---------------- Cost breakdown ----------------
        self.cost_label.configure(text=(
            f"BOQ Cost: ₹{boq_cost:,.2f}\n"
            f"Material Cost: ₹{material_cost:,.2f}\n"
            f"Total Direct Cost: ₹{total_direct_cost:,.2f}"
        ))

        # ---------------- Receivables Aging ----------------
        for row in self.aging_tree.get_children():
            self.aging_tree.delete(row)
        for bucket, amount in outstanding_by_bucket.items():
            self.aging_tree.insert("", "end", values=(bucket, f"{amount:,.2f}"))
        self.aging_tree.insert("", "end", values=("Total Outstanding", f"{sum(outstanding_by_bucket.values()):,.2f}"))

        # ---------------- Top Vendors (real, this project only) ----------------
        for row in self.vendor_tree.get_children():
            self.vendor_tree.delete(row)
        vendor_ids = set()
        for row in db.fetch_all("SELECT DISTINCT VendorID FROM trxBOQItem WHERE ProjectID=? AND VendorID IS NOT NULL",
                                (self.project_id,)):
            vendor_ids.add(row["VendorID"])
        for row in db.fetch_all("SELECT DISTINCT VendorID FROM mstMaterial WHERE ProjectID=? AND VendorID IS NOT NULL",
                                (self.project_id,)):
            vendor_ids.add(row["VendorID"])

        vendor_totals = []
        for vid in vendor_ids:
            v = db.fetch_one("SELECT VendorName, Category FROM mstVendor WHERE VendorID=?", (vid,))
            if v:
                total = vendor_total_purchase(vid)
                vendor_totals.append((v["VendorName"], v["Category"] or "-", total))
        vendor_totals.sort(key=lambda x: x[2], reverse=True)
        for name, category, total in vendor_totals[:10]:
            self.vendor_tree.insert("", "end", values=(name, category, f"{total:,.2f}"))

"""
ADS OS Desktop -- Commercial Dashboard (v4.3)
The landing page for Commercial, not a 7th tab -- becomes the default entry
when Commercial opens, per the explicit "landing page, not another tab
nobody clicks" requirement. Every number is real, aggregated from the same
tables the six existing Commercial modules already use -- nothing
fabricated, nothing estimated. Quick Actions open the EXISTING dialogs from
those modules directly (NewPurchaseDialog, VendorForm, MaterialForm,
BOQItemForm, InvoiceForm) -- no new implementations, per explicit
instruction.

Deliberately omitted: Site Expenditure KPIs and "Recent Site Expenses" --
that module doesn't exist yet. Fabricating numbers for a module that isn't
built would be worse than not showing the section at all.

Does NOT touch Vendors, Materials, BOQ, Invoice Center, Fee Calculator, or
Proposal Builder -- those are completely untouched by this change, per
explicit instruction. This is a new file, not a modification of any of them.
"""
import customtkinter as ctk
from tkinter import ttk
import db
import theme
import ui_components as ui


class CommercialDashboardPanel(ctk.CTkFrame):
    def __init__(self, master, project_id):
        super().__init__(master, fg_color="transparent")
        self.project_id = project_id
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        ctk.CTkLabel(self, text="Commercial Dashboard", font=theme.FONT_HEADING, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 5))
        ctk.CTkLabel(self, text="Real-time overview of this project's commercial activity -- real data, "
                                 "aggregated from Fee Calculator, BOQ, Materials, Vendors, and Invoice Center.",
                     font=theme.FONT_SMALL, text_color=theme.MUTED, wraplength=700, justify="left").pack(
            anchor="w", padx=20, pady=(0, 10))

        # Real restructure, matching a reviewed mockup: the old single
        # undifferentiated row mixed client revenue with vendor/material
        # spend, and "Vendors Used" was a raw count with no rupee figure
        # at all. Each section below answers one real question, grouped
        # the way the mockup groups them -- Procurement combines Vendors/
        # Materials/Site Expenses (all real project spend on goods and
        # services), BOQ Overview is its own section, and Project
        # Financial Position closes with a rough profit estimate.
        #
        # Deliberately NOT built here: the mockup's "This Project Only ▾"
        # scope dropdown and funnel icon -- that implies switching between
        # this project's data and a cross-project/company-wide view,
        # which is new functionality, not a visual reskin, and isn't
        # wired to anything real yet.
        ctk.CTkLabel(self, text="👤  CLIENT BILLING", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(0, 5))
        self.client_stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.client_stats_frame.pack(fill="x", padx=20, pady=(0, 15))

        ctk.CTkLabel(self, text="💼  CONTRACTS", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(0, 5))
        self.contract_stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.contract_stats_frame.pack(fill="x", padx=20, pady=(0, 8))
        self.commission_stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.commission_stats_frame.pack(fill="x", padx=20, pady=(0, 15))

        ctk.CTkLabel(self, text="🛒  PROCUREMENT", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(0, 5))
        self.procurement_stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.procurement_stats_frame.pack(fill="x", padx=20, pady=(0, 2))
        ctk.CTkLabel(self, text="Payment status isn't shown here -- vendor payments aren't recorded per "
                                "project, so Paid/Outstanding can't honestly be split by project. See the "
                                "Vendors tab for each vendor's real, company-wide payment status.",
                     font=("Segoe UI", 9), text_color=theme.MUTED, wraplength=700, justify="left").pack(
            anchor="w", padx=20, pady=(0, 13))

        ctk.CTkLabel(self, text="📋  BOQ OVERVIEW", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(0, 5))
        self.boq_stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.boq_stats_frame.pack(fill="x", padx=20, pady=(0, 15))

        ctk.CTkLabel(self, text="👤  PROJECT FINANCIAL POSITION", font=theme.FONT_BODY_BOLD,
                    text_color=theme.INK).pack(anchor="w", padx=20, pady=(0, 5))
        self.summary_stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.summary_stats_frame.pack(fill="x", padx=20, pady=(0, 2))
        ctk.CTkLabel(self, text="* Cash in Hand = Amount Received − Paid to Contractors − Material Purchases "
                                "− Site Expenses (every real recorded transaction on this project). Excludes "
                                "BOQ Value (a quoted/budgeted figure, not a recorded transaction) and vendor "
                                "payment status specifically (whether a vendor has been paid isn't recorded "
                                "per project -- see the note under Procurement above; this figure already "
                                "includes what this project actually spent on vendor-supplied materials).",
                     font=("Segoe UI", 9), text_color=theme.MUTED, wraplength=700, justify="left").pack(
            anchor="w", padx=20, pady=(0, 15))

        quick_actions = ctk.CTkFrame(self, fg_color=theme.WHITE, corner_radius=8)
        quick_actions.pack(fill="x", padx=20, pady=(0, 15))
        ctk.CTkLabel(quick_actions, text="Quick Actions", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=15, pady=(12, 8))
        actions_row = ctk.CTkFrame(quick_actions, fg_color="transparent")
        actions_row.pack(fill="x", padx=15, pady=(0, 15))
        actions = [
            ("+ Purchase", self._quick_new_purchase), ("+ Material", self._quick_new_material),
            ("+ Vendor", self._quick_new_vendor), ("+ Contractor", self._quick_new_contractor),
            ("+ BOQ Item", self._quick_new_boq_item), ("+ Invoice", self._quick_new_invoice),
        ]
        for label, command in actions:
            ctk.CTkButton(actions_row, text=label, command=command, fg_color=theme.BRASS,
                         hover_color=theme.INK, font=theme.FONT_SMALL, height=32).pack(
                side="left", padx=(0, 8), fill="x", expand=True)

        columns = ctk.CTkFrame(self, fg_color="transparent")
        columns.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        purchases_card = ctk.CTkFrame(columns, fg_color=theme.WHITE, corner_radius=8)
        purchases_card.pack(side="left", fill="both", expand=True, padx=(0, 10))
        ctk.CTkLabel(purchases_card, text="Recent Purchases", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=15, pady=(15, 8))
        self.purchases_tree_frame = ctk.CTkFrame(purchases_card, fg_color="transparent")
        self.purchases_tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 15))

        activity_card = ctk.CTkFrame(columns, fg_color=theme.WHITE, corner_radius=8)
        activity_card.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(activity_card, text="Recent Commercial Activity", font=theme.FONT_BODY_BOLD,
                     text_color=theme.INK).pack(anchor="w", padx=15, pady=(15, 8))
        self.activity_scroll = ctk.CTkScrollableFrame(activity_card, fg_color="transparent", height=220)
        self.activity_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 15))

        ctk.CTkLabel(self, text="🛡  All data shown is project-specific and does not include information "
                                "from other projects.", font=("Segoe UI", 9), text_color=theme.MUTED).pack(
            anchor="w", padx=20, pady=(0, 15))

    def refresh(self):
        self._render_client_stats()
        self._render_contract_stats()
        self._render_procurement_stats()
        self._render_boq_stats()
        self._render_summary_stats()
        self._render_recent_purchases()
        self._render_recent_activity()

    def _get_client_billing(self):
        invoices = db.fetch_all("SELECT * FROM trxInvoice WHERE ProjectID=? AND Status != 'Cancelled'",
                                (self.project_id,))
        total_invoiced = sum(i["Amount"] for i in invoices)
        total_received = sum(db.fetch_one(
            "SELECT COALESCE(SUM(Amount),0) AS t FROM trxInvoicePayment WHERE InvoiceID=?",
            (i["InvoiceID"],))["t"] for i in invoices)
        return total_invoiced, total_received, total_invoiced - total_received

    def _get_contract_totals(self):
        from contract_panel import get_contract_paid, get_contract_effective_amount
        contracts = db.fetch_all("SELECT * FROM trxContract WHERE ProjectID=?", (self.project_id,))
        total_value = sum(get_contract_effective_amount(c) or 0 for c in contracts)
        total_paid = sum(get_contract_paid(c["ContractID"]) for c in contracts)
        return total_value, total_paid, total_value - total_paid

    def _render_client_stats(self):
        for w in self.client_stats_frame.winfo_children():
            w.destroy()
        total_invoiced, total_received, outstanding = self._get_client_billing()
        stats = [
            (f"₹{total_invoiced:,.0f}", "Total Invoiced", None, "📄", "#D6E8FA"),
            (f"₹{total_received:,.0f}", "Amount Received", "From client", "💰", "#D4F0E0"),
            (f"₹{outstanding:,.0f}", "Outstanding (Receivable)", "Owed by client", "⏰", "#F5E6D3"),
        ]
        for col_idx, (value, label, sublabel, icon, bg_color) in enumerate(stats):
            card = ui.kpi_card(self.client_stats_frame, value, label, sublabel, icon, bg_color, col_idx)
            card.grid_configure(padx=(0, 12))

    def _render_contract_stats(self):
        from contract_panel import get_contract_paid, get_contract_status, get_commission_expected, \
            get_contract_effective_amount
        for w in self.contract_stats_frame.winfo_children():
            w.destroy()
        for w in self.commission_stats_frame.winfo_children():
            w.destroy()

        contracts = db.fetch_all("SELECT * FROM trxContract WHERE ProjectID=?", (self.project_id,))
        active_contracts = [c for c in contracts
                           if get_contract_status(c, get_contract_paid(c["ContractID"])) != "Paid in Full"]
        total_contract_value = sum(get_contract_effective_amount(c) or 0 for c in contracts)
        total_paid = sum(get_contract_paid(c["ContractID"]) for c in contracts)
        contract_outstanding = total_contract_value - total_paid

        commission_expected = sum(get_commission_expected(c) for c in contracts)
        commission_received = sum(db.fetch_one(
            "SELECT COALESCE(SUM(Amount),0) AS t FROM trxCommissionReceipt WHERE ContractID=?",
            (c["ContractID"],))["t"] for c in contracts)
        commission_outstanding = commission_expected - commission_received

        if not contracts:
            ctk.CTkLabel(self.contract_stats_frame, text="No contracts on this project yet.",
                        font=theme.FONT_SMALL, text_color=theme.MUTED).pack(anchor="w", pady=5)
            return

        stats = [
            (str(len(active_contracts)), "Active Contracts", f"{len(contracts)} total", "👥", "#E8DFF5"),
            (f"₹{total_contract_value:,.0f}", "Contract Value", "Includes recorded adjustments", "📄", "#D6E8FA"),
            (f"₹{total_paid:,.0f}", "Paid", "To contractors", "✅", "#D4F0E0"),
            (f"₹{contract_outstanding:,.0f}", "Outstanding", "To contractors", "⏳", "#FBE0E0"),
        ]
        for col_idx, (value, label, sublabel, icon, bg_color) in enumerate(stats):
            card = ui.kpi_card(self.contract_stats_frame, value, label, sublabel, icon, bg_color, col_idx)
            card.grid_configure(padx=(0, 12))

        commission_stats = [
            (f"₹{commission_expected:,.0f}", "Commission Expected", None, "🎗", "#FBF0D6"),
            (f"₹{commission_received:,.0f}", "Commission Received", None, "🎁", "#D4F0E0"),
            (f"₹{commission_outstanding:,.0f}", "Commission Outstanding", None, "🔔", "#FBE0E0"),
        ]
        for col_idx, (value, label, sublabel, icon, bg_color) in enumerate(commission_stats):
            card = ui.kpi_card(self.commission_stats_frame, value, label, sublabel, icon, bg_color, col_idx)
            card.grid_configure(padx=(0, 12))

    def _render_procurement_stats(self):
        from site_expense_panel import get_site_expenses_total
        for w in self.procurement_stats_frame.winfo_children():
            w.destroy()

        material_purchase_value = db.fetch_one("""
            SELECT COALESCE(SUM(p.TotalCost),0) AS t FROM trxMaterialPurchase p
            JOIN mstMaterial m ON p.MaterialID=m.MaterialID WHERE m.ProjectID=?
        """, (self.project_id,))["t"]
        vendor_count = db.fetch_one("""
            SELECT COUNT(DISTINCT v) AS n FROM (
                SELECT VendorID AS v FROM trxBOQItem WHERE ProjectID=? AND VendorID IS NOT NULL
                UNION SELECT VendorID AS v FROM mstMaterial WHERE ProjectID=? AND VendorID IS NOT NULL
            )
        """, (self.project_id, self.project_id))["n"]
        site_expense_total = get_site_expenses_total(self.project_id)

        # Real, project-scoped figures only -- deliberately no vendor
        # Paid/Outstanding here (see the note in _build_ui). Site
        # Expenses are genuinely already paid-out cash (recorded at the
        # time they're incurred), unlike Vendor purchases which may
        # still be owed -- so it isn't folded into the same figure as
        # Material Purchases, to avoid implying they share a payment
        # status they don't.
        stats = [
            (str(vendor_count), "Vendors Used", "This project", "🏪", "#E8DFF5"),
            (f"₹{material_purchase_value:,.0f}", "Material Purchases", "This project", "📦", "#D4F0E0"),
            (f"₹{site_expense_total:,.0f}", "Site Expenses", "This project", "🧺", "#D6E8FA"),
        ]
        for col_idx, (value, label, sublabel, icon, bg_color) in enumerate(stats):
            card = ui.kpi_card(self.procurement_stats_frame, value, label, sublabel, icon, bg_color, col_idx)
            card.grid_configure(padx=(0, 12))

    def _get_procurement_totals(self):
        """
        Real, project-scoped actual spend -- Material Purchases (real
        recorded trxMaterialPurchase transactions) and Site Expenses
        (real recorded trxSiteExpense entries). Deliberately does NOT
        include BOQ Value -- that's a quoted/budgeted line-item figure,
        not a recorded transaction, and a BOQ item may or may not have
        actually been purchased yet. Folding it in here would risk
        double-counting (if it has been purchased, that purchase is
        already in Material Purchases) or overstating spend that hasn't
        actually happened yet.
        """
        from site_expense_panel import get_site_expenses_total
        material_purchase_value = db.fetch_one("""
            SELECT COALESCE(SUM(p.TotalCost),0) AS t FROM trxMaterialPurchase p
            JOIN mstMaterial m ON p.MaterialID=m.MaterialID WHERE m.ProjectID=?
        """, (self.project_id,))["t"]
        site_expense_total = get_site_expenses_total(self.project_id)
        return material_purchase_value, site_expense_total

    def _render_boq_stats(self):
        for w in self.boq_stats_frame.winfo_children():
            w.destroy()
        boq_count = db.fetch_one("SELECT COUNT(*) AS n FROM trxBOQItem WHERE ProjectID=?", (self.project_id,))["n"]
        boq_total = db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxBOQItem WHERE ProjectID=?",
                                 (self.project_id,))["t"]
        stats = [
            (str(boq_count), "BOQ Items", "Total items", "📋", "#F5E6D3"),
            (f"₹{boq_total:,.0f}", "BOQ Value", "Total value", "💵", "#D4F0E0"),
        ]
        for col_idx, (value, label, sublabel, icon, bg_color) in enumerate(stats):
            card = ui.kpi_card(self.boq_stats_frame, value, label, sublabel, icon, bg_color, col_idx)
            card.grid_configure(padx=(0, 12))

    def _render_summary_stats(self):
        for w in self.summary_stats_frame.winfo_children():
            w.destroy()
        _, total_received, client_outstanding = self._get_client_billing()
        _, contract_paid, contract_outstanding = self._get_contract_totals()
        material_purchase_value, site_expense_total = self._get_procurement_totals()

        net_position = total_received - contract_paid
        # Cash in Hand: every real, recorded transaction this project has
        # -- money actually received from the client, minus money
        # actually paid to contractors, minus real material purchases,
        # minus real site expenses. Deliberately excludes BOQ Value (a
        # quoted/budgeted figure, not a recorded transaction -- see
        # _get_procurement_totals) and vendor PAYMENT status specifically
        # (whether a vendor has been paid isn't trackable per project --
        # trxVendorPayment has no ProjectID), which is a different
        # question from vendor SPEND (how much this project cost in
        # vendor-supplied materials), which IS included here via Material
        # Purchases.
        cash_in_hand = net_position - material_purchase_value - site_expense_total

        stats = [
            (f"₹{net_position:,.0f}", "Net Cash Position", "Received minus paid to contractors", "📈", "#D4F0E0"),
            (f"₹{client_outstanding:,.0f}", "Still to Collect", "From client", "⬇", "#F5E6D3"),
            (f"₹{contract_outstanding:,.0f}", "Still to Pay", "To contractors", "⬆", "#FBE0E0"),
            (f"₹{cash_in_hand:,.0f}", "Cash in Hand", "After materials + site expenses", "₹", "#D4F0E0"),
        ]
        for col_idx, (value, label, sublabel, icon, bg_color) in enumerate(stats):
            card = ui.kpi_card(self.summary_stats_frame, value, label, sublabel, icon, bg_color, col_idx)
            card.grid_configure(padx=(0, 12))

    def _render_recent_purchases(self):
        for w in self.purchases_tree_frame.winfo_children():
            w.destroy()
        purchases = db.fetch_all("""
            SELECT p.*, m.MaterialName FROM trxMaterialPurchase p JOIN mstMaterial m ON p.MaterialID=m.MaterialID
            WHERE m.ProjectID=? ORDER BY p.PurchaseDate DESC LIMIT 8
        """, (self.project_id,))
        if not purchases:
            ctk.CTkLabel(self.purchases_tree_frame, text="No purchases recorded yet.",
                        font=theme.FONT_SMALL, text_color=theme.MUTED).pack(pady=10)
            return
        cols = ("material", "qty", "cost", "date")
        tree = ttk.Treeview(self.purchases_tree_frame, columns=cols, show="headings", height=7)
        headings = {"material": "Material", "qty": "Qty", "cost": "Total Cost (₹)", "date": "Date"}
        widths = {"material": 140, "qty": 60, "cost": 100, "date": 90}
        for c in cols:
            tree.heading(c, text=headings[c])
            tree.column(c, width=widths[c])
        tree.pack(fill="both", expand=True)
        for p in purchases:
            tree.insert("", "end", values=(p["MaterialName"], f"{p['Quantity']:.1f}",
                                           f"{p['TotalCost']:,.2f}", p["PurchaseDate"]))

    def _render_recent_activity(self):
        for w in self.activity_scroll.winfo_children():
            w.destroy()
        commercial_actions = ["Fee Calculation Saved", "BOQ Item Added", "BOQ Item Updated", "BOQ Item Deleted",
                              "Material Added", "Material Updated", "Material Purchase Recorded",
                              "Purchase Recorded", "Vendor Added", "Vendor Updated", "Invoice Created",
                              "Invoice Updated", "Payment Recorded", "Proposal Created", "Proposal PDF Generated"]
        placeholders = ",".join("?" * len(commercial_actions))
        entries = db.fetch_all(
            f"SELECT Action, Details, LoggedOn FROM logActivity WHERE EntityID=? AND EntityType='Project' "
            f"AND Action IN ({placeholders}) ORDER BY LoggedOn DESC LIMIT 10",
            (self.project_id, *commercial_actions))
        if not entries:
            ctk.CTkLabel(self.activity_scroll, text="No commercial activity yet.",
                        font=theme.FONT_SMALL, text_color=theme.MUTED).pack(pady=10)
            return
        for e in entries:
            ui.activity_card(self.activity_scroll, e["Action"], e["Details"], e["LoggedOn"])

    def _quick_new_purchase(self):
        from materials_panel import NewPurchaseDialog
        NewPurchaseDialog(self, self.project_id, on_save=self.refresh)

    def _quick_new_vendor(self):
        from vendors_panel import VendorForm
        VendorForm(self, on_save=self.refresh)

    def _quick_new_contractor(self):
        from contractors_panel import ContractorForm
        ContractorForm(self, on_save=self.refresh)

    def _quick_new_material(self):
        from materials_panel import MaterialForm
        MaterialForm(self, self.project_id, on_save=self.refresh)

    def _quick_new_boq_item(self):
        from boq_panel import BOQItemForm
        BOQItemForm(self, self.project_id, on_save=self.refresh)

    def _quick_new_invoice(self):
        from invoice_panel import InvoiceForm
        InvoiceForm(self, self.project_id, on_save=self.refresh)

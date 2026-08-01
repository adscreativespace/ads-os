"""
ADS OS Desktop -- Reports Module (Phase 1)
Business intelligence layer -- consumes data from every other module,
never creates or edits anything. Built on the reusable ReportScreen
framework (ui_components.py) rather than as three separate one-off
screens, matching the same discipline as EntityWorkspace.

Deliberately scoped to exactly the "Phase 2: three flagship reports"
recommendation from the request this was built against -- Financial
Summary, Project Summary, Contractor Payment Summary -- not the full
7-category, ~50-report vision. The landing page shows only these three
real, working reports, not placeholder cards for the other ~47 -- applying
the same "don't create empty Coming Soon cards" principle already agreed
on for the Financial Dashboard.

Every report reuses financial_calcs.py rather than recomputing its own
aggregation logic, so a fix there applies to the Dashboard, every report,
and any future report built the same way.
"""
import customtkinter as ctk
import theme
import db
import ui_components as ui
import financial_calcs as fc
from vendors_panel import vendor_total_purchase, vendor_payments_made, vendor_outstanding, vendor_top_materials


class ReportsLandingScreen(ctk.CTkFrame):
    """
    Real fix for a genuine navigation lifecycle bug: report frames used
    to be created as children of self.master (this screen's OWN parent,
    i.e. main.py's shared container) -- making them SIBLINGS of this
    screen, not children of it. App.show() only ever knew about and hid
    the fixed set of top-level screens it registers (Dashboard, Clients,
    Reports, etc.); it had no idea these dynamically-created report
    frames existed at all, so switching to another module never hid
    them -- they just sat there, overlapping whatever screen came next.

    Fixed by giving this screen one dedicated content_frame that holds
    EITHER the landing cards OR the currently-open report, mutually
    exclusive, with the previous one always destroyed before the next is
    built. Report frames are now genuine children of this screen -- when
    App.show() hides THIS screen (which it already correctly does, since
    Reports is one of its registered top-level screens), whatever is
    currently inside content_frame is hidden right along with it. No
    changes needed in main.py at all.
    """
    def __init__(self, master, app=None):
        super().__init__(master, fg_color=theme.PARCHMENT)
        self.app = app
        self.current_report = None
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True)
        self._build_landing()

    def _build_landing(self):
        self._clear_content()
        self.current_report = None

        header = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 5))
        ctk.CTkLabel(header, text="Reports", font=theme.FONT_HEADING, text_color=theme.INK).pack(anchor="w")
        ctk.CTkLabel(self.content_frame, text="Generate a report -- financial, project, vendor, or contractor. "
                                              "For live business metrics, see Dashboard or Financial Dashboard.",
                     font=theme.FONT_SMALL, text_color=theme.MUTED).pack(anchor="w", padx=20, pady=(0, 15))

        # Search -- filters the catalog below by name/description as the
        # person types. Deliberately no executive KPI row here (Total
        # Reports/Reports Generated This Month/etc.) -- per explicit
        # instruction, this screen answers "what report do you want to
        # generate", not "how is my business doing" (that's what
        # Dashboard and Financial Dashboard already do).
        search_row = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        search_row.pack(fill="x", padx=20, pady=(0, 15))
        self.search_entry = ctk.CTkEntry(search_row, placeholder_text="Search reports...", width=300)
        self.search_entry.pack(anchor="w")
        self.search_entry.bind("<KeyRelease>", lambda e: self._render_catalog())

        self.catalog_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.catalog_frame.pack(fill="both", expand=True, padx=20)
        self._render_catalog()

    # Real report catalog, grouped by category -- exactly the entities
    # ADS OS is actually organized around (Financial/Project/Vendor/
    # Contractor). Only real, working reports are listed; no placeholder
    # entries for reports that don't exist yet.
    def _report_catalog(self):
        return [
            ("Financial", "Financial Summary", "Revenue, expenses, and outstanding balances, per project.",
             self._open_financial_summary),
            ("Project", "Project Summary", "Every project with contract value, invoiced, received, and outstanding.",
             self._open_project_summary),
            ("Vendor", "Vendor Ledger", "Every vendor's total purchases, payments made, outstanding, and top materials.",
             self._open_vendor_ledger),
            ("Contractor", "Contractor Payment Summary",
             "Every contractor with total contract value, paid, and outstanding.", self._open_contractor_summary),
        ]

    def _render_catalog(self):
        for w in self.catalog_frame.winfo_children():
            w.destroy()
        query = self.search_entry.get().strip().lower()
        catalog = self._report_catalog()
        if query:
            catalog = [r for r in catalog if query in r[1].lower() or query in r[2].lower() or query in r[0].lower()]

        if not catalog:
            ui.empty_state(self.catalog_frame, f"No reports match '{query}'.")
            return

        # Grouped by category, in a fixed, predictable order -- matches
        # how the rest of ADS OS is organized (Clients/Projects/Vendors/
        # Contractors), so this feels like the same application, not a
        # separate reporting tool bolted on.
        category_order = ["Financial", "Project", "Vendor", "Contractor", "Client"]
        by_category = {}
        for category, title, description, command in catalog:
            by_category.setdefault(category, []).append((title, description, command))

        for category in category_order:
            if category not in by_category:
                continue
            ctk.CTkLabel(self.catalog_frame, text=f"{category} Reports", font=("Segoe UI", 11, "bold"),
                        text_color=theme.MUTED).pack(anchor="w", pady=(10, 6))
            for title, description, command in by_category[category]:
                row = ctk.CTkFrame(self.catalog_frame, fg_color=theme.WHITE, corner_radius=8)
                row.pack(fill="x", pady=(0, 8))
                text_block = ctk.CTkFrame(row, fg_color="transparent")
                text_block.pack(side="left", fill="x", expand=True, padx=15, pady=10)
                ctk.CTkLabel(text_block, text=title, font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(anchor="w")
                ctk.CTkLabel(text_block, text=description, font=("Segoe UI", 9), text_color=theme.MUTED,
                            wraplength=600, justify="left").pack(anchor="w")
                ctk.CTkButton(row, text="Open Report →", command=command, fg_color=theme.BRASS,
                            hover_color=theme.INK, font=theme.FONT_SMALL, width=130).pack(
                    side="right", padx=15, pady=10)

    def _open_financial_summary(self):
        self._clear_content()
        self._push_report(FinancialSummaryReport(self.content_frame, on_back=self._build_landing))

    def _open_project_summary(self):
        self._clear_content()
        self._push_report(ProjectSummaryReport(self.content_frame, app=self.app, on_back=self._build_landing))

    def _open_vendor_ledger(self):
        self._clear_content()
        self._push_report(VendorLedgerReport(self.content_frame, app=self.app, on_back=self._build_landing))

    def _open_contractor_summary(self):
        self._clear_content()
        self._push_report(ContractorPaymentSummaryReport(self.content_frame, app=self.app, on_back=self._build_landing))

    def _clear_content(self):
        """
        Real fix for a real regression: previously the destroy-loop lived
        inside _push_report, which runs AFTER the report widget is
        constructed -- but constructing FinancialSummaryReport(self.content_frame, ...)
        makes it a child of content_frame immediately, at construction
        time, before _push_report ever runs. That meant the destroy-loop
        was destroying the brand-new report right after creating it, and
        the following .pack() call failed on an already-destroyed widget
        -- confirmed directly: report in content_frame.winfo_children()
        was True immediately after construction, before _push_report's
        cleanup even started.

        Clearing content_frame's existing children BEFORE constructing
        the new report (not after) is the actual fix -- the new report
        is the only thing created after this point, so nothing destroys it.
        """
        for w in self.content_frame.winfo_children():
            w.destroy()

    def _push_report(self, report):
        self.current_report = report
        report.pack(fill="both", expand=True)

    def refresh(self):
        """
        Called by App.show() whenever Reports is navigated to.

        Honest current state: ui.ReportScreen (what every report is
        actually built on) has no refresh() method yet, so this is a
        safe no-op for now rather than a working data-refresh -- it
        will not error, but reopening Reports with a report already
        open won't re-query fresh data yet either. Wired up now (rather
        than left out) so that adding refresh() to ui.ReportScreen later
        is the only change needed to make revisiting Reports genuinely
        re-query, matching every other module's behavior -- a real,
        separate, smaller follow-up, not attempted in this pass since
        the actual reported bug (overlapping screens) doesn't depend on it.
        """
        if self.current_report is not None and hasattr(self.current_report, "refresh"):
            self.current_report.refresh()


class FinancialSummaryReport(ctk.CTkFrame):
    """Revenue/expenses/outstanding, one row per project."""
    def __init__(self, master, on_back):
        super().__init__(master, fg_color=theme.PARCHMENT)
        self.on_back = on_back
        back_btn = ctk.CTkButton(self, text="← Back to Reports", command=self._go_back, fg_color="transparent",
                                 hover_color=theme.PARCHMENT, text_color=theme.BRASS, font=theme.FONT_SMALL,
                                 anchor="w", height=24)
        back_btn.pack(anchor="w", padx=20, pady=(10, 0))
        self.report = ui.ReportScreen(self, title="Financial Summary", build_data=self._build_data)
        self.report.pack(fill="both", expand=True)

    def _go_back(self):
        self.pack_forget()
        self.on_back()

    def _build_data(self, start_date, end_date):
        revenue = fc.get_revenue_summary(start_date, end_date)
        expenses = fc.get_expenses_summary(start_date, end_date)
        cash = fc.get_cash_position(start_date, end_date)
        summary_cards = [
            (f"₹{revenue['total_invoiced']:,.0f}", "Total Invoiced", None),
            (f"₹{revenue['total_received']:,.0f}", "Amount Received", None),
            (f"₹{expenses['total_purchases']:,.0f}", "Material Purchases", None),
            (f"₹{expenses['total_additional_charges']:,.0f}", "Additional Charges", "Transportation, loading, etc."),
            (f"₹{expenses['total_contractor_payments']:,.0f}", "Contractor Payments", None),
            (f"₹{expenses['total_site_expenses']:,.0f}", "Site Expenses", "Labour, transport, misc. site costs"),
            (f"₹{cash['net_position']:,.0f}", "Net Position", "Simple estimate, not a formal P&L"),
        ]

        projects = db.fetch_all("SELECT ProjectID, ProjectName, ProjectCode FROM tblProject ORDER BY ProjectName")
        headers = ["Project", "Code", "Contract Value", "Invoiced", "Received", "Outstanding"]
        rows = []
        for p in projects:
            contract_value = db.fetch_one("SELECT COALESCE(SUM(ContractAmount),0) AS t FROM trxContract WHERE ProjectID=?",
                                          (p["ProjectID"],))["t"]
            invoice_query = "SELECT InvoiceID, Amount FROM trxInvoice WHERE ProjectID=? AND Status != 'Cancelled'"
            params = [p["ProjectID"]]
            if start_date:
                invoice_query += " AND InvoiceDate >= ?"
                params.append(start_date)
            if end_date:
                invoice_query += " AND InvoiceDate <= ?"
                params.append(end_date)
            invoices = db.fetch_all(invoice_query, tuple(params))
            invoiced = sum(i["Amount"] for i in invoices)
            received = sum(db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxInvoicePayment WHERE InvoiceID=?",
                                        (i["InvoiceID"],))["t"] for i in invoices)
            if invoiced == 0 and contract_value == 0:
                continue
            rows.append((p["ProjectName"], p["ProjectCode"], f"₹{contract_value:,.0f}", f"₹{invoiced:,.0f}",
                        f"₹{received:,.0f}", f"₹{invoiced - received:,.0f}"))
        return summary_cards, headers, rows


class ProjectSummaryReport(ctk.CTkFrame):
    def __init__(self, master, app, on_back):
        super().__init__(master, fg_color=theme.PARCHMENT)
        self.app = app
        self.on_back = on_back
        self._project_ids = []
        back_btn = ctk.CTkButton(self, text="← Back to Reports", command=self._go_back, fg_color="transparent",
                                 hover_color=theme.PARCHMENT, text_color=theme.BRASS, font=theme.FONT_SMALL,
                                 anchor="w", height=24)
        back_btn.pack(anchor="w", padx=20, pady=(10, 0))
        ctk.CTkLabel(self, text="Double-click a row to open that project.", font=theme.FONT_SMALL,
                    text_color=theme.MUTED).pack(anchor="w", padx=20, pady=(0, 5))
        self.report = ui.ReportScreen(self, title="Project Summary", build_data=self._build_data,
                                      on_row_open=self._open_project)
        self.report.pack(fill="both", expand=True)

    def _go_back(self):
        self.pack_forget()
        self.on_back()

    def _open_project(self, row_index, row_data):
        project_id = self._project_ids[row_index]
        if self.app:
            from project_workspace import ProjectWorkspace
            ProjectWorkspace(self.app, project_id)

    def _build_data(self, start_date, end_date):
        ops = fc.get_operations_summary()
        summary_cards = [
            (str(ops["active_projects"]), "Active Projects", None),
        ]
        project_query = "SELECT ProjectID, ProjectName, ProjectCode, ProjectStatus FROM tblProject"
        params = []
        if start_date:
            project_query += " WHERE CreatedOn >= ?"
            params.append(start_date)
            if end_date:
                project_query += " AND CreatedOn <= ?"
                params.append(end_date)
        elif end_date:
            project_query += " WHERE CreatedOn <= ?"
            params.append(end_date)
        project_query += " ORDER BY ProjectName"
        projects = db.fetch_all(project_query, tuple(params))

        headers = ["Project", "Code", "Status", "Contract Value", "Invoiced", "Received", "Outstanding"]
        rows = []
        self._project_ids = []
        for p in projects:
            contract_value = db.fetch_one("SELECT COALESCE(SUM(ContractAmount),0) AS t FROM trxContract WHERE ProjectID=?",
                                          (p["ProjectID"],))["t"]
            invoices = db.fetch_all("SELECT InvoiceID, Amount FROM trxInvoice WHERE ProjectID=? AND Status != 'Cancelled'",
                                    (p["ProjectID"],))
            invoiced = sum(i["Amount"] for i in invoices)
            received = sum(db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxInvoicePayment WHERE InvoiceID=?",
                                        (i["InvoiceID"],))["t"] for i in invoices)
            rows.append((p["ProjectName"], p["ProjectCode"], p["ProjectStatus"], f"₹{contract_value:,.0f}",
                        f"₹{invoiced:,.0f}", f"₹{received:,.0f}", f"₹{invoiced - received:,.0f}"))
            self._project_ids.append(p["ProjectID"])
        return summary_cards, headers, rows


class ContractorPaymentSummaryReport(ctk.CTkFrame):
    def __init__(self, master, app, on_back):
        super().__init__(master, fg_color=theme.PARCHMENT)
        self.app = app
        self.on_back = on_back
        self._contractor_ids = []
        back_btn = ctk.CTkButton(self, text="← Back to Reports", command=self._go_back, fg_color="transparent",
                                 hover_color=theme.PARCHMENT, text_color=theme.BRASS, font=theme.FONT_SMALL,
                                 anchor="w", height=24)
        back_btn.pack(anchor="w", padx=20, pady=(10, 0))
        ctk.CTkLabel(self, text="Double-click a row to open that contractor's workspace.", font=theme.FONT_SMALL,
                    text_color=theme.MUTED).pack(anchor="w", padx=20, pady=(0, 5))
        self.report = ui.ReportScreen(self, title="Contractor Payment Summary", build_data=self._build_data,
                                      on_row_open=self._open_contractor)
        self.report.pack(fill="both", expand=True)

    def _go_back(self):
        self.pack_forget()
        self.on_back()

    def _open_contractor(self, row_index, row_data):
        contractor_id = self._contractor_ids[row_index]
        from contractors_panel import ContractorWorkspace
        ContractorWorkspace(self, contractor_id)

    def _build_data(self, start_date, end_date):
        out = fc.get_outstanding_summary()
        summary_cards = [
            (f"₹{out['contractor_outstanding']:,.0f}", "Total Contractor Outstanding", None),
        ]
        contractors = db.fetch_all("SELECT ContractorID, Name, Trade FROM mstContractor WHERE Active=1 ORDER BY Name")
        headers = ["Contractor", "Trade", "Contracts", "Total Value", "Total Paid", "Outstanding"]
        rows = []
        self._contractor_ids = []
        for c in contractors:
            contract_query = "SELECT ContractID, ContractAmount FROM trxContract WHERE ContractorID=?"
            params = [c["ContractorID"]]
            if start_date:
                contract_query += " AND CreatedOn >= ?"
                params.append(start_date)
            if end_date:
                contract_query += " AND CreatedOn <= ?"
                params.append(end_date)
            contracts = db.fetch_all(contract_query, tuple(params))
            if not contracts:
                continue
            total_value = sum(ct["ContractAmount"] for ct in contracts if ct["ContractAmount"] is not None)
            total_paid = sum(db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxContractPayment WHERE ContractID=?",
                                          (ct["ContractID"],))["t"] for ct in contracts)
            rows.append((c["Name"], c["Trade"] or "-", str(len(contracts)), f"₹{total_value:,.0f}",
                        f"₹{total_paid:,.0f}", f"₹{total_value - total_paid:,.0f}"))
            self._contractor_ids.append(c["ContractorID"])
        return summary_cards, headers, rows


class VendorLedgerReport(ctk.CTkFrame):
    """
    Real vendor-centric report -- reuses the same already-tested helper
    functions from vendors_panel.py (vendor_total_purchase,
    vendor_payments_made, vendor_outstanding) rather than duplicating
    that query logic here, so a fix in one place applies to both the
    Vendors screen and this report.
    """
    def __init__(self, master, app, on_back):
        super().__init__(master, fg_color=theme.PARCHMENT)
        self.app = app
        self.on_back = on_back
        self._vendor_ids = []
        back_btn = ctk.CTkButton(self, text="← Back to Reports", command=self._go_back, fg_color="transparent",
                                 hover_color=theme.PARCHMENT, text_color=theme.BRASS, font=theme.FONT_SMALL,
                                 anchor="w", height=24)
        back_btn.pack(anchor="w", padx=20, pady=(10, 0))
        ctk.CTkLabel(self, text="Double-click a row to open that vendor's workspace.", font=theme.FONT_SMALL,
                    text_color=theme.MUTED).pack(anchor="w", padx=20, pady=(0, 5))
        self.report = ui.ReportScreen(self, title="Vendor Ledger", build_data=self._build_data,
                                      on_row_open=self._open_vendor)
        self.report.pack(fill="both", expand=True)

    def _go_back(self):
        self.pack_forget()
        self.on_back()

    def _open_vendor(self, row_index, row_data):
        vendor_id = self._vendor_ids[row_index]
        from vendors_panel import VendorWorkspace
        VendorWorkspace(self, vendor_id)

    def _build_data(self, start_date, end_date):
        # Deliberately NOT date-filtered -- Total Purchases/Payments Made/
        # Outstanding are current, point-in-time facts about each vendor
        # (matching the same reasoning already applied to
        # get_outstanding_summary() in financial_calcs.py), not something
        # that makes sense to ask "as of a past date" without a full
        # historical ledger this app doesn't have.
        vendors = db.fetch_all("SELECT VendorID, VendorName, Category, IsPreferred FROM mstVendor WHERE Active=1 "
                               "ORDER BY VendorName")
        total_purchases_all = 0
        total_paid_all = 0
        total_outstanding_all = 0
        headers = ["Vendor", "Category", "Total Purchases", "Payments Made", "Outstanding", "Top Material"]
        rows = []
        self._vendor_ids = []
        for v in vendors:
            total_purchase = vendor_total_purchase(v["VendorID"])
            if total_purchase == 0:
                continue  # no real activity yet -- nothing to report for this vendor
            payments_made = vendor_payments_made(v["VendorID"])
            outstanding = vendor_outstanding(v["VendorID"])
            top_materials = vendor_top_materials(v["VendorID"], limit=1)
            top_material = top_materials[0][0] if top_materials else "-"
            name_display = f"⭐ {v['VendorName']}" if v["IsPreferred"] else v["VendorName"]
            rows.append((name_display, v["Category"] or "-", f"₹{total_purchase:,.0f}", f"₹{payments_made:,.0f}",
                        f"₹{outstanding:,.0f}", top_material))
            self._vendor_ids.append(v["VendorID"])
            total_purchases_all += total_purchase
            total_paid_all += payments_made
            total_outstanding_all += outstanding

        summary_cards = [
            (f"₹{total_purchases_all:,.0f}", "Total Purchases", None),
            (f"₹{total_paid_all:,.0f}", "Total Paid", None),
            (f"₹{total_outstanding_all:,.0f}", "Total Outstanding", None),
        ]
        return summary_cards, headers, rows

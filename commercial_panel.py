"""
ADS OS Desktop -- Commercial module switcher.
Dashboard is now the landing page (first entry -- the switcher already
defaults to whichever module is listed first, so this alone makes it the
entry point without touching the switching logic itself). The six existing
modules (Fee Calculator, BOQ, Materials, Vendors, Invoice Center, Reports,
Proposal Builder) are completely unchanged -- reachable exactly as before,
one click from the same switcher, just no longer the first thing you see.
"""
import customtkinter as ctk
import theme
from commercial_dashboard_panel import CommercialDashboardPanel
from commercial_fee_calculator import FeeCalculatorPanel
from boq_panel import BOQPanel
from materials_panel import MaterialsPanel
from project_vendors_panel import ProjectVendorsPanel
from project_contractors_panel import ProjectContractorsPanel
from site_expense_panel import SiteExpensePanel
from invoice_panel import InvoiceCenterPanel
from commercial_reports_panel import CommercialReportsPanel
from proposal_panel import ProposalBuilderPanel
from contract_panel import ContractsPanel

MODULES = {
    "Dashboard": CommercialDashboardPanel,
    "Fee Calculator": FeeCalculatorPanel,
    "Proposal Builder": ProposalBuilderPanel,
    "Vendors": ProjectVendorsPanel,
    "Contractors": ProjectContractorsPanel,
    "Contracts": ContractsPanel,
    "Materials": MaterialsPanel,
    "Site Expenses": SiteExpensePanel,
    "BOQ": BOQPanel,
    "Invoice Center": InvoiceCenterPanel,
    "Reports": CommercialReportsPanel,
}


class CommercialPanel(ctk.CTkFrame):
    def __init__(self, master, project_id, initial_module=None):
        super().__init__(master, fg_color="transparent")
        self.project_id = project_id
        self.current_panel = None

        switcher_row = ctk.CTkFrame(self, fg_color="transparent")
        switcher_row.pack(fill="x", padx=20, pady=(15, 0))
        default_module = initial_module if initial_module in MODULES else list(MODULES.keys())[0]
        self.switcher_var = ctk.StringVar(value=default_module)
        ctk.CTkSegmentedButton(switcher_row, values=list(MODULES.keys()), variable=self.switcher_var,
                               command=self._on_switch, fg_color=theme.WHITE, selected_color=theme.BRASS,
                               unselected_color=theme.WHITE, text_color=theme.INK,
                               selected_hover_color=theme.INK).pack(anchor="w")

        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True)

        self._on_switch(self.switcher_var.get())

    def _on_switch(self, module_name):
        for w in self.content_frame.winfo_children():
            w.destroy()
        panel_class = MODULES[module_name]
        self.current_panel = panel_class(self.content_frame, self.project_id)
        self.current_panel.pack(fill="both", expand=True)

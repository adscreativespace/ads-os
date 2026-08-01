"""
ADS OS Desktop -- Project-scoped Contractors panel.

Real bug fix: the "Contractors" tab inside a project's Commercial section
was previously just the global ContractorsPanel (the same one used for
the company-wide sidebar screen) -- it accepted project_id but never
actually used it to filter anything, showing every contractor in the
whole business regardless of which project you were looking at. Inside
a specific project, that's the wrong question to answer: what you
actually want to know is "who is assigned to THIS project" and "let me
assign someone new" -- not "here's everyone we've ever worked with."

This panel answers the right question: contractors with a real
trxContract record for this specific project, with genuine actions to
assign an existing contractor (reusing ContractForm, already proven and
project-aware) or create a brand new one (reusing ContractorForm, the
same dialog the global Contractors screen uses) and then assign them.
"""
import customtkinter as ctk
from tkinter import messagebox
import theme
import db
import ui_components as ui
from contract_panel import ContractForm
from contractors_panel import ContractorForm, ContractorWorkspace


def contractor_financials_for_project(contractor_id, project_id):
    """
    Real (total_value, total_paid, outstanding) for one contractor,
    scoped to a single project -- the project-specific counterpart to
    contractors_panel.py's contractor_financials(), which deliberately
    aggregates across every project a contractor has ever worked on.
    Both are needed for different real questions: "how much has this
    contractor been paid overall" vs "how much do we owe them on THIS
    project specifically."

    total_value is the effective (adjusted) contract amount -- the
    originally agreed ContractAmount plus any real, dated adjustments
    recorded against it (see trxContractAdjustment / migrate_v398) --
    not the raw, un-adjusted ContractAmount. This keeps Outstanding here
    consistent with the Contracts tab, which uses the same effective
    amount.
    """
    contracts = db.fetch_all(
        "SELECT ContractID, ContractAmount FROM trxContract WHERE ContractorID=? AND ProjectID=?",
        (contractor_id, project_id))
    total_value = 0
    for c in contracts:
        if c["ContractAmount"] is None:
            continue
        adjustments = db.fetch_one(
            "SELECT COALESCE(SUM(Amount),0) AS t FROM trxContractAdjustment WHERE ContractID=?",
            (c["ContractID"],))["t"]
        total_value += c["ContractAmount"] + adjustments
    total_paid = sum(db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxContractPayment WHERE ContractID=?",
                                  (c["ContractID"],))["t"] for c in contracts)
    return total_value, total_paid, total_value - total_paid


def contractor_last_payment_for_project(contractor_id, project_id):
    """
    Real last payment (amount, date) for this contractor, scoped to
    THIS project specifically -- the project-scoped counterpart to
    contractors_panel.py's contractor_last_payment(), which looks across
    every contract the contractor has anywhere. Everything else in this
    panel is scoped to one project; this should be too, rather than
    silently showing a payment date from a different project entirely.
    Returns (None, None) if no payment has been recorded on this
    project yet.
    """
    row = db.fetch_one("""
        SELECT cp.Amount, cp.PaymentDate FROM trxContractPayment cp
        JOIN trxContract c ON cp.ContractID = c.ContractID
        WHERE c.ContractorID = ? AND c.ProjectID = ? ORDER BY cp.PaymentDate DESC LIMIT 1
    """, (contractor_id, project_id))
    return (row["Amount"], row["PaymentDate"]) if row else (None, None)


class ProjectContractorsPanel(ctk.CTkFrame):
    def __init__(self, master, project_id):
        super().__init__(master, fg_color="transparent")
        self.project_id = project_id
        self.selected_contractor_id = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(15, 5))
        ctk.CTkLabel(header, text="Contractors", font=theme.FONT_HEADING, text_color=theme.INK).pack(side="left")
        ctk.CTkButton(header, text="+ New Contractor", command=self.open_new_contractor, fg_color=theme.INK,
                     hover_color=theme.BRASS, font=theme.FONT_SMALL, height=28).pack(side="right", padx=(8, 0))
        ctk.CTkButton(header, text="+ Assign Contractor", command=self.open_assign_contractor, fg_color=theme.BRASS,
                     hover_color=theme.INK, font=theme.FONT_BODY_BOLD, height=28).pack(side="right")
        ctk.CTkLabel(self, text="Contractors assigned to this project -- for the full company-wide list, "
                                "use Contractors in the main sidebar.",
                     font=theme.FONT_SMALL, text_color=theme.MUTED).pack(anchor="w", padx=20, pady=(0, 10))

        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=20, pady=(0, 10))

        columns = ctk.CTkFrame(self, fg_color="transparent")
        columns.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        self.table_frame = ctk.CTkFrame(columns, fg_color=theme.WHITE)
        self.table_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        from tkinter import ttk
        cols = ("name", "trade", "value", "paid", "outstanding", "status")
        self.tree = ttk.Treeview(self.table_frame, columns=cols, show="headings", height=14)
        headings = {"name": "Contractor", "trade": "Trade", "value": "Contract Value", "paid": "Paid",
                    "outstanding": "Outstanding", "status": "Status"}
        widths = {"name": 150, "trade": 110, "value": 110, "paid": 100, "outstanding": 100, "status": 90}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c])
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda e: self.open_workspace())
        scrollbar = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True, side="left")

        self.details_panel = ctk.CTkFrame(columns, fg_color=theme.WHITE, corner_radius=8, width=260)
        self.details_panel.pack(side="left", fill="y")
        self.details_panel.pack_propagate(False)
        self._render_empty_details()

    def _render_empty_details(self):
        for w in self.details_panel.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.details_panel, text="Select a contractor to see details, or assign one to this "
                                              "project if none are listed yet.", font=theme.FONT_SMALL,
                    text_color=theme.MUTED, justify="left", wraplength=220).pack(anchor="w", padx=15, pady=15)

    def refresh(self):
        for w in self.stats_frame.winfo_children():
            w.destroy()
        for row in self.tree.get_children():
            self.tree.delete(row)
        if hasattr(self, "_empty_state_frame"):
            self._empty_state_frame.destroy()
            del self._empty_state_frame

        # Real contractors assigned to THIS project -- via an actual
        # trxContract record, not the global master list.
        assigned = db.fetch_all("""
            SELECT DISTINCT c.ContractorID, c.Name, c.Trade, c.Status FROM mstContractor c
            JOIN trxContract ct ON ct.ContractorID = c.ContractorID
            WHERE ct.ProjectID = ? ORDER BY c.Name
        """, (self.project_id,))

        total_value_all, total_paid_all = 0, 0
        for c in assigned:
            value, paid, outstanding = contractor_financials_for_project(c["ContractorID"], self.project_id)
            total_value_all += value
            total_paid_all += paid

        stats = [
            (str(len(assigned)), "Assigned Contractors", None),
            (f"₹{total_value_all:,.0f}", "Total Contract Value", "This project"),
            (f"₹{total_paid_all:,.0f}", "Total Paid", "This project"),
            (f"₹{total_value_all - total_paid_all:,.0f}", "Outstanding", "This project"),
        ]
        for value, label, sublabel in stats:
            ui.stat_card(self.stats_frame, value, label, sublabel).pack(side="left", padx=(0, 12))

        if not assigned:
            self.tree.pack_forget()
            self._empty_state_frame = ui.empty_state(
                self.table_frame, "No contractors assigned to this project yet.",
                "+ Assign Contractor", self.open_assign_contractor)
            return
        self.tree.pack(fill="both", expand=True, side="left")

        for c in assigned:
            value, paid, outstanding = contractor_financials_for_project(c["ContractorID"], self.project_id)
            self.tree.insert("", "end", iid=c["ContractorID"],
                             values=(c["Name"], c["Trade"] or "—", f"₹{value:,.0f}", f"₹{paid:,.0f}",
                                    f"₹{outstanding:,.0f}", c["Status"] or "Active"))

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        contractor_id = int(sel[0])
        self.selected_contractor_id = contractor_id
        c = db.fetch_one("SELECT * FROM mstContractor WHERE ContractorID=?", (contractor_id,))
        value, paid, outstanding = contractor_financials_for_project(contractor_id, self.project_id)
        last_amount, last_date = contractor_last_payment_for_project(contractor_id, self.project_id)

        for w in self.details_panel.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.details_panel, text=c["Name"], font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=15, pady=(15, 2))
        ctk.CTkLabel(self.details_panel, text=c["Trade"] or "—", font=theme.FONT_SMALL,
                    text_color=theme.MUTED).pack(anchor="w", padx=15, pady=(0, 10))
        info_rows = [("Contract Value (this project)", f"₹{value:,.0f}"),
                    ("Paid (this project)", f"₹{paid:,.0f}"),
                    ("Outstanding (this project)", f"₹{outstanding:,.0f}")]
        # Only shown when a real payment exists on this project -- an
        # empty "Last Payment: —" row would just be noise for a
        # contractor who hasn't been paid on this project yet.
        if last_amount is not None:
            info_rows.append(("Last Payment (this project)", f"₹{last_amount:,.0f}  ({last_date})"))
        info_rows.append(("Mobile", c["Mobile"] or "—"))
        for label, val in info_rows:
            ctk.CTkLabel(self.details_panel, text=label, font=("Segoe UI", 9), text_color=theme.MUTED).pack(
                anchor="w", padx=15, pady=(6, 0))
            ctk.CTkLabel(self.details_panel, text=val, font=theme.FONT_SMALL, text_color=theme.INK).pack(
                anchor="w", padx=15)
        ctk.CTkButton(self.details_panel, text="Edit Assignment", command=self.edit_assignment,
                     fg_color=theme.INK, hover_color=theme.BRASS, font=theme.FONT_SMALL, height=28).pack(
            fill="x", padx=15, pady=(0, 8))
        ctk.CTkButton(self.details_panel, text="Remove from Project", command=self.remove_assignment,
                     fg_color="#8B2E2E", hover_color="#5E1F1F", font=theme.FONT_SMALL, height=28).pack(
            fill="x", padx=15, pady=(0, 8))
        ctk.CTkButton(self.details_panel, text="Open Contractor Workspace →", command=self.open_workspace,
                     fg_color=theme.BRASS, hover_color=theme.INK, font=theme.FONT_SMALL, height=28).pack(
            fill="x", padx=15, pady=(15, 15))

    def open_workspace(self):
        if self.selected_contractor_id is None:
            return
        ContractorWorkspace(self, self.selected_contractor_id, on_close=self.refresh)

    def _contracts_for_selected(self):
        """Real trxContract rows for the currently-selected contractor on THIS project -- usually exactly
        one, but a contractor can in principle have more than one contract on the same project."""
        return db.fetch_all("SELECT * FROM trxContract WHERE ContractorID=? AND ProjectID=?",
                           (self.selected_contractor_id, self.project_id))

    def edit_assignment(self):
        if self.selected_contractor_id is None:
            return
        contracts = self._contracts_for_selected()
        if not contracts:
            return
        if len(contracts) == 1:
            ContractForm(self, self.project_id, on_save=self.refresh, existing=contracts[0])
        else:
            self._pick_contract(contracts, "Edit which contract?",
                               lambda ct: ContractForm(self, self.project_id, on_save=self.refresh, existing=ct))

    def remove_assignment(self):
        if self.selected_contractor_id is None:
            return
        contracts = self._contracts_for_selected()
        if not contracts:
            return
        if len(contracts) == 1:
            self._delete_contract_with_guard(contracts[0])
        else:
            self._pick_contract(contracts, "Remove which contract?", self._delete_contract_with_guard)

    def _delete_contract_with_guard(self, contract):
        """Same real guard as ContractsPanel -- blocks deletion if real payments or commission receipts
        already exist against this contract, rather than silently destroying that payment history."""
        payments = db.fetch_one("SELECT COUNT(*) AS n FROM trxContractPayment WHERE ContractID=?",
                               (contract["ContractID"],))["n"]
        commission = db.fetch_one("SELECT COUNT(*) AS n FROM trxCommissionReceipt WHERE ContractID=?",
                                 (contract["ContractID"],))["n"]
        if payments > 0 or commission > 0:
            messagebox.showerror(
                "Cannot remove",
                f"This contract has {payments} real payment(s) and {commission} commission receipt(s) recorded "
                "against it. Removing it would destroy that payment history -- use Edit Assignment instead if "
                "only the amount or contract details were entered wrong.", parent=self)
            return
        if not messagebox.askyesno("Remove from project?",
                                   "Remove this contractor's assignment from this project? This cannot be undone.",
                                   parent=self):
            return
        db.execute("DELETE FROM trxContractItem WHERE ContractID=?", (contract["ContractID"],))
        db.execute("DELETE FROM trxContractScope WHERE ContractID=?", (contract["ContractID"],))
        db.execute("DELETE FROM trxContract WHERE ContractID=?", (contract["ContractID"],))
        db.log_activity("Project", self.project_id, "Contractor Removed from Project", "")
        self.selected_contractor_id = None
        self._render_empty_details()
        self.refresh()

    def _pick_contract(self, contracts, title, on_pick):
        """Small picker for the rare case of multiple contracts for the same contractor on one project --
        avoids guessing which one the person meant."""
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("360x300")
        dialog.configure(fg_color=theme.PARCHMENT)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        ctk.CTkLabel(dialog, text=title, font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 10))
        for ct in contracts:
            amount_display = f"₹{ct['ContractAmount']:,.0f}" if ct["ContractAmount"] is not None else "Running"
            row = ctk.CTkButton(dialog, text=f"{ct['ContractType']} -- {amount_display}",
                               command=lambda c=ct: (dialog.destroy(), on_pick(c)),
                               fg_color=theme.WHITE, hover_color=theme.PARCHMENT, text_color=theme.INK,
                               font=theme.FONT_SMALL, anchor="w", height=32)
            row.pack(fill="x", padx=20, pady=4)

    def open_assign_contractor(self):
        """Real assignment -- reuses ContractForm, which already creates a genuine trxContract linking an
        existing contractor to this project. Not a duplicate flow; the same one Contracts already uses."""
        ContractForm(self, self.project_id, on_save=self.refresh)

    def open_new_contractor(self):
        """Creates a brand new contractor (global master data), then immediately offers to assign them to
        this project, so the person doesn't have to separately hunt for the Assign step afterward."""
        def _after_new_contractor():
            self.refresh()
            ContractForm(self, self.project_id, on_save=self.refresh)
        ContractorForm(self, on_save=_after_new_contractor)

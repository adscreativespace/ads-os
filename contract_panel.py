"""
ADS OS Desktop -- Contract Management (v4.4.0 Foundation)
Per BUSINESS_RULES.md: assigns a Business Partner (mstVendor) to a project,
optionally copying one of their Default Quotations (BR-002: copy, never
reference live). Payments are additive with computed status (BR-004).
Commission belongs to the contract, never the partner (BR-003). Fixed vs
Running contracts are structurally distinct (BR-005).

Deliberately excluded from this release, per the agreed phased roadmap:
Board Calculation (BR-006 -- formula confirmed, implementation deferred to
v4.5.0), Weekly Labour (v4.6.0, pending a real example), Work Orders,
Variations, Material Issue, Recovery, Retention, TDS, Performance Ratings,
Attachments, Drawing Revisions (v4.7+, only if real usage confirms the need).
"""
import customtkinter as ctk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
import db
import theme
import ui_components as ui
from constants import apply_decimal_only

CONTRACT_TYPE_OPTIONS = ["Fixed", "Running"]
COMMISSION_TYPE_OPTIONS = ["-- None --", "Percentage", "Fixed Amount"]
PAYMENT_TYPE_OPTIONS = ["Advance", "Partial", "Final"]
PAYMENT_MODE_OPTIONS = ["Cash", "UPI", "Bank Transfer", "Cheque", "NEFT", "RTGS", "IMPS", "Card", "Other"]
STATUS_COLORS = {"Not Started": "#6B6B6B", "Partially Paid": "#B68100",
                 "Paid in Full": "#2E8B57", "Running": "#1E5FA8"}


def get_contract_paid(contract_id):
    return db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxContractPayment WHERE ContractID=?",
                        (contract_id,))["t"]


def get_contract_adjustments_total(contract_id):
    """Real sum of every adjustment recorded against this contract (can be negative -- a discount -- or
    positive -- extra scope/charge). Starts at 0 until a real adjustment is recorded."""
    return db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxContractAdjustment WHERE ContractID=?",
                        (contract_id,))["t"]


def get_contract_effective_amount(contract):
    """
    Real, current committed amount for a Fixed contract -- the originally
    agreed ContractAmount plus every real, dated, reasoned adjustment
    recorded against it since (see trxContractAdjustment / migrate_v398).
    This is what Outstanding, Status, and commission are computed from
    everywhere in this app -- not the raw, un-adjusted ContractAmount,
    which stays untouched as "what was originally agreed." Returns None
    for Running contracts (no fixed total to adjust) or if ContractAmount
    itself was never set.
    """
    if contract["ContractAmount"] is None:
        return None
    return contract["ContractAmount"] + get_contract_adjustments_total(contract["ContractID"])


def get_contract_status(contract, paid):
    """Always computed (BR-004) -- never manually set. Uses the effective (adjusted) amount so a recorded
    adjustment is reflected in status immediately, not just the originally agreed ContractAmount."""
    effective = get_contract_effective_amount(contract)
    if contract["ContractType"] == "Running" or effective is None:
        return "Running"
    if paid >= effective:
        return "Paid in Full"
    if paid > 0:
        return "Partially Paid"
    return "Not Started"


def get_commission_expected(contract):
    if not contract["CommissionType"] or contract["CommissionType"] == "-- None --":
        return 0
    if contract["CommissionType"] == "Percentage":
        # Commission on the final, adjusted amount -- if the contract
        # value itself changed via a negotiated adjustment, the
        # percentage-based commission owed should reflect that, not the
        # pre-adjustment number.
        return (get_contract_effective_amount(contract) or 0) * (contract["CommissionValue"] or 0) / 100
    return contract["CommissionValue"] or 0


class ContractsPanel(ctk.CTkFrame):
    def __init__(self, master, project_id):
        super().__init__(master, fg_color="transparent")
        self.project_id = project_id
        self.selected_contract_id = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        ctk.CTkLabel(self, text="Contracts", font=theme.FONT_HEADING, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 5))
        ctk.CTkLabel(self, text="Manage contractor/partner contracts, payments, and commission for this project.",
                     font=theme.FONT_SMALL, text_color=theme.MUTED).pack(anchor="w", padx=20, pady=(0, 10))

        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=20, pady=(0, 10))

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkButton(toolbar, text="+ New Contract", command=self.open_add_contract,
                      fg_color=theme.BRASS, hover_color=theme.INK, font=theme.FONT_SMALL, height=28).pack(side="right")

        columns = ctk.CTkFrame(self, fg_color="transparent")
        columns.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        self.table_frame = ctk.CTkFrame(columns, fg_color=theme.WHITE)
        self.table_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        cols = ("vendor", "type", "amount", "paid", "outstanding", "status")
        self.tree = ttk.Treeview(self.table_frame, columns=cols, show="headings", height=14)
        headings = {"vendor": "Business Partner", "type": "Type", "amount": "Contract Amt (₹)",
                    "paid": "Paid (₹)", "outstanding": "Outstanding (₹)", "status": "Status"}
        widths = {"vendor": 160, "type": 70, "amount": 100, "paid": 90, "outstanding": 100, "status": 100}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c])
        for status, color in STATUS_COLORS.items():
            self.tree.tag_configure(f"status_{status}", foreground=color)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        hscrollbar = ttk.Scrollbar(self.table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscroll=hscrollbar.set)
        hscrollbar.pack(side="bottom", fill="x")

        scrollbar = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self.tree.pack(fill="both", expand=True, side="left")

        details_panel = ctk.CTkFrame(columns, fg_color=theme.WHITE, corner_radius=8, width=280)
        details_panel.pack(side="left", fill="y")
        details_panel.pack_propagate(False)
        ctk.CTkLabel(details_panel, text="Contract Details", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=15, pady=(15, 10))
        self.details_label = ctk.CTkLabel(details_panel, text="Select a contract to see details.",
                                          font=theme.FONT_BODY, text_color=theme.MUTED, justify="left", wraplength=250)
        self.details_label.pack(anchor="w", padx=15, pady=(0, 10))
        ctk.CTkButton(details_panel, text="Record Payment", command=self.open_record_payment,
                      fg_color=theme.BRASS, hover_color=theme.INK, font=theme.FONT_SMALL, height=28).pack(
            fill="x", padx=15, pady=(0, 8))
        ctk.CTkButton(details_panel, text="Manage Items", command=self.open_manage_items,
                      fg_color=theme.INK, hover_color=theme.BRASS, font=theme.FONT_SMALL, height=28).pack(
            fill="x", padx=15, pady=(0, 8))
        ctk.CTkButton(details_panel, text="Record Adjustment", command=self.open_record_adjustment,
                      fg_color=theme.INK, hover_color=theme.BRASS, font=theme.FONT_SMALL, height=28).pack(
            fill="x", padx=15, pady=(0, 8))
        ctk.CTkButton(details_panel, text="Record Commission Receipt", command=self.open_record_commission,
                      fg_color=theme.INK, hover_color=theme.BRASS, font=theme.FONT_SMALL, height=28).pack(
            fill="x", padx=15, pady=(0, 8))
        ctk.CTkButton(details_panel, text="Edit Contract", command=self.open_edit_contract,
                      fg_color=theme.INK, hover_color=theme.BRASS, font=theme.FONT_SMALL, height=28).pack(
            fill="x", padx=15, pady=(0, 8))
        ctk.CTkButton(details_panel, text="Delete Contract", command=self.delete_contract,
                      fg_color="#8B2E2E", hover_color="#5E1F1F", font=theme.FONT_SMALL, height=28).pack(
            fill="x", padx=15, pady=(0, 15))

    def refresh(self):
        self._render_stats()
        for row in self.tree.get_children():
            self.tree.delete(row)
        if hasattr(self, "_empty_state_frame"):
            self._empty_state_frame.destroy()
            del self._empty_state_frame

        contracts = db.fetch_all("""
            SELECT c.*, co.Name AS ContractorName, v.VendorName FROM trxContract c
            LEFT JOIN mstContractor co ON c.ContractorID = co.ContractorID
            LEFT JOIN mstVendor v ON c.VendorID = v.VendorID
            WHERE c.ProjectID=? ORDER BY c.ContractID DESC
        """, (self.project_id,))

        if not contracts:
            self.tree.pack_forget()
            self._empty_state_frame = ui.empty_state(
                self.table_frame, "No contracts yet.", "+ New Contract", self.open_add_contract)
            return
        self.tree.pack(fill="both", expand=True, side="left")

        for c in contracts:
            paid = get_contract_paid(c["ContractID"])
            status = get_contract_status(c, paid)
            effective = get_contract_effective_amount(c)
            outstanding = (effective - paid) if effective is not None else None
            self.tree.insert("", "end", iid=c["ContractID"],
                             values=(c["ContractorName"] or c["VendorName"] or "-", c["ContractType"],
                                    f"{effective:,.2f}" if effective is not None else "-",
                                    f"{paid:,.2f}", f"{outstanding:,.2f}" if outstanding is not None else "-", status),
                             tags=(f"status_{status}",))

    def _render_stats(self):
        for w in self.stats_frame.winfo_children():
            w.destroy()
        contracts = db.fetch_all("SELECT * FROM trxContract WHERE ProjectID=?", (self.project_id,))
        total_contracts = len(contracts)
        total_committed = sum(get_contract_effective_amount(c) or 0 for c in contracts
                              if get_contract_effective_amount(c) is not None)
        total_paid = sum(get_contract_paid(c["ContractID"]) for c in contracts)
        total_outstanding = total_committed - total_paid

        stats = [
            (str(total_contracts), "Total Contracts", None),
            (f"₹{total_committed:,.0f}", "Total Committed", None),
            (f"₹{total_paid:,.0f}", "Total Paid", None),
            (f"₹{total_outstanding:,.0f}", "Outstanding", None),
        ]
        for value, label, sublabel in stats:
            ui.stat_card(self.stats_frame, value, label, sublabel).pack(side="left", padx=(0, 12))

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        contract_id = int(sel[0])
        self.selected_contract_id = contract_id
        c = db.fetch_one("""
            SELECT ct.*, co.Name AS ContractorName, v.VendorName FROM trxContract ct
            LEFT JOIN mstContractor co ON ct.ContractorID = co.ContractorID
            LEFT JOIN mstVendor v ON ct.VendorID=v.VendorID
            WHERE ct.ContractID=?
        """, (contract_id,))
        paid = get_contract_paid(contract_id)
        status = get_contract_status(c, paid)
        items = db.fetch_all("SELECT * FROM trxContractItem WHERE ContractID=?", (contract_id,))
        payments = db.fetch_all("SELECT * FROM trxContractPayment WHERE ContractID=? ORDER BY PaymentDate DESC", (contract_id,))
        adjustments = db.fetch_all(
            "SELECT * FROM trxContractAdjustment WHERE ContractID=? ORDER BY AdjustmentDate DESC", (contract_id,))

        lines = [f"{c['ContractorName'] or c['VendorName'] or '-'}", f"Type: {c['ContractType']}", f"Status: {status}"]
        if c["ContractAmount"] is not None:
            adjustments_total = get_contract_adjustments_total(contract_id)
            effective = c["ContractAmount"] + adjustments_total
            lines.append(f"Original Contract Amount: ₹{c['ContractAmount']:,.2f}")
            if adjustments_total != 0:
                sign = "+" if adjustments_total > 0 else ""
                lines.append(f"Adjustments: {sign}₹{adjustments_total:,.2f}")
                lines.append(f"Adjusted Contract Amount: ₹{effective:,.2f}")
            lines.append(f"Paid: ₹{paid:,.2f}")
            lines.append(f"Outstanding: ₹{effective - paid:,.2f}")
        else:
            lines.append(f"Paid to date: ₹{paid:,.2f} (Running -- no fixed total)")

        if c["CommissionType"] and c["CommissionType"] != "-- None --":
            expected = get_commission_expected(c)
            received = db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxCommissionReceipt WHERE ContractID=?",
                                    (contract_id,))["t"]
            lines.append(f"\nCommission ({c['CommissionType']}):")
            lines.append(f"Expected: ₹{expected:,.2f} · Received: ₹{received:,.2f} · Outstanding: ₹{expected-received:,.2f}")

        if items:
            lines.append(f"\nItems ({len(items)}):")
            for item in items[:5]:
                lines.append(f"  {item['ItemName']} — {item['Unit']} @ ₹{item['Rate']:,.2f}")

        if adjustments:
            lines.append(f"\nAdjustments ({len(adjustments)}):")
            for a in adjustments[:5]:
                sign = "+" if a["Amount"] > 0 else ""
                lines.append(f"  {a['AdjustmentDate']}: {sign}₹{a['Amount']:,.2f} — {a['Reason']}")

        if payments:
            lines.append(f"\nPayments ({len(payments)}):")
            for p in payments[:5]:
                lines.append(f"  {p['PaymentDate']}: ₹{p['Amount']:,.2f} ({p['PaymentType']})")

        self.details_label.configure(text="\n".join(lines))

    def _selected_or_warn(self):
        if self.selected_contract_id is None:
            messagebox.showinfo("Select a contract", "Please select a contract from the list first.", parent=self)
            return None
        return self.selected_contract_id

    def open_add_contract(self):
        ContractForm(self, self.project_id, on_save=self.refresh)

    def open_edit_contract(self):
        contract_id = self._selected_or_warn()
        if contract_id is None:
            return
        existing = db.fetch_one("SELECT * FROM trxContract WHERE ContractID=?", (contract_id,))
        ContractForm(self, self.project_id, on_save=self.refresh, existing=existing)

    def delete_contract(self):
        contract_id = self._selected_or_warn()
        if contract_id is None:
            return
        payments = db.fetch_one("SELECT COUNT(*) AS n FROM trxContractPayment WHERE ContractID=?", (contract_id,))["n"]
        commission = db.fetch_one("SELECT COUNT(*) AS n FROM trxCommissionReceipt WHERE ContractID=?", (contract_id,))["n"]
        if payments > 0 or commission > 0:
            messagebox.showerror(
                "Cannot delete",
                f"This contract has {payments} real payment(s) and {commission} commission receipt(s) recorded "
                "against it. Deleting it would destroy that payment history, not just undo a data-entry "
                "mistake -- remove those first if you're certain, or use Edit Contract instead if only the "
                "amount or contractor was entered wrong.",
                parent=self)
            return
        contract = db.fetch_one("""
            SELECT c.*, co.Name AS ContractorName FROM trxContract c
            LEFT JOIN mstContractor co ON c.ContractorID = co.ContractorID WHERE c.ContractID=?
        """, (contract_id,))
        if not messagebox.askyesno("Delete contract?",
                                   f"Delete the contract with {contract['ContractorName'] or 'this partner'}? "
                                   "This cannot be undone.", parent=self):
            return
        db.execute("DELETE FROM trxContractItem WHERE ContractID=?", (contract_id,))
        db.execute("DELETE FROM trxContractScope WHERE ContractID=?", (contract_id,))
        db.execute("DELETE FROM trxContract WHERE ContractID=?", (contract_id,))
        db.log_activity("Project", self.project_id, "Contract Deleted", contract["ContractorName"] or "")
        self.selected_contract_id = None
        self.refresh()

    def open_record_payment(self):
        contract_id = self._selected_or_warn()
        if contract_id is None:
            return
        contract = db.fetch_one("SELECT * FROM trxContract WHERE ContractID=?", (contract_id,))
        RecordContractPaymentDialog(self, contract, on_save=self.refresh)

    def open_record_commission(self):
        contract_id = self._selected_or_warn()
        if contract_id is None:
            return
        contract = db.fetch_one("SELECT * FROM trxContract WHERE ContractID=?", (contract_id,))
        if not contract["CommissionType"] or contract["CommissionType"] == "-- None --":
            messagebox.showinfo("No commission on this contract", "This contract has no commission terms set.", parent=self)
            return
        RecordCommissionReceiptDialog(self, contract, on_save=self.refresh)

    def open_manage_items(self):
        contract_id = self._selected_or_warn()
        if contract_id is None:
            return
        ManageContractItemsDialog(self, contract_id, on_save=self.refresh)

    def open_record_adjustment(self):
        contract_id = self._selected_or_warn()
        if contract_id is None:
            return
        contract = db.fetch_one("SELECT * FROM trxContract WHERE ContractID=?", (contract_id,))
        if contract["ContractAmount"] is None:
            messagebox.showinfo(
                "Not applicable",
                "Adjustments apply to Fixed contracts with a set Contract Amount -- this is a Running "
                "contract, which has no fixed total to adjust.", parent=self)
            return
        RecordContractAdjustmentDialog(self, contract, on_save=self.refresh)


class ContractForm(ctk.CTkToplevel):
    def __init__(self, master, project_id, on_save, existing=None):
        super().__init__(master)
        self.transient(self.master.winfo_toplevel())
        self.project_id = project_id
        self.on_save = on_save
        self.existing = existing
        self.title("Edit Contract" if existing else "New Contract")
        self.geometry("460x620")
        self.configure(fg_color=theme.PARCHMENT)
        self.grab_set()

        self.contractors = db.fetch_all("SELECT ContractorID, Name, IsPreferred FROM mstContractor WHERE Active=1 ORDER BY IsPreferred DESC, Name")

        row = 0
        ctk.CTkLabel(self, text=self.title(), font=theme.FONT_SUBHEADING, text_color=theme.INK).grid(
            row=row, column=0, columnspan=2, padx=15, pady=(15, 10), sticky="w")
        row += 1

        ctk.CTkLabel(self, text="Contractor *", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        contractor_labels = [f"{'⭐ ' if c['IsPreferred'] else ''}{c['Name']}" for c in self.contractors]
        # When editing, default to the contract's real, currently-assigned
        # contractor rather than whichever comes first in the dropdown.
        default_label = contractor_labels[0] if contractor_labels else ""
        if existing:
            match = next((lbl for c, lbl in zip(self.contractors, contractor_labels)
                        if c["ContractorID"] == existing["ContractorID"]), None)
            if match:
                default_label = match
        self.contractor_var = ctk.StringVar(value=default_label)
        ctk.CTkOptionMenu(self, values=contractor_labels or ["-- No contractors yet --"], variable=self.contractor_var,
                          width=250).grid(row=row, column=1, padx=15, pady=8)
        row += 1
        if not contractor_labels:
            ctk.CTkLabel(self, text="No contractors yet. Add one under Commercial -> Contractors first.",
                        font=theme.FONT_SMALL, text_color=theme.MUTED, wraplength=380, justify="left").grid(
                row=row, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 6))
            row += 1

        ctk.CTkLabel(self, text="Contract Type", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.type_var = ctk.StringVar(value=existing["ContractType"] if existing else "Fixed")
        ctk.CTkOptionMenu(self, values=CONTRACT_TYPE_OPTIONS, variable=self.type_var, width=250,
                          command=self._on_type_change).grid(row=row, column=1, padx=15, pady=8)
        row += 1

        self.amount_row = row
        ctk.CTkLabel(self, text="Contract Amount (₹)", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.amount_entry = ctk.CTkEntry(self, width=250)
        apply_decimal_only(self, self.amount_entry)
        if existing and existing["ContractAmount"] is not None:
            self.amount_entry.insert(0, str(existing["ContractAmount"]))
        self.amount_entry.grid(row=row, column=1, padx=15, pady=8)
        row += 1
        self.amount_hint = ctk.CTkLabel(self, text="Leave blank for Running contracts (no fixed total, e.g. weekly work).",
                                        font=theme.FONT_SMALL, text_color=theme.MUTED, wraplength=380, justify="left")
        self.amount_hint.grid(row=row, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 6))
        row += 1

        ctk.CTkLabel(self, text="Commission Type", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.commission_type_var = ctk.StringVar(value=existing["CommissionType"] if existing and existing["CommissionType"] else COMMISSION_TYPE_OPTIONS[0])
        ctk.CTkOptionMenu(self, values=COMMISSION_TYPE_OPTIONS, variable=self.commission_type_var, width=250).grid(
            row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self, text="Commission Value", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.commission_value_entry = ctk.CTkEntry(self, width=250, placeholder_text="% or ₹ depending on type above")
        apply_decimal_only(self, self.commission_value_entry)
        if existing and existing["CommissionValue"] is not None:
            self.commission_value_entry.insert(0, str(existing["CommissionValue"]))
        self.commission_value_entry.grid(row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self, text="Notes", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.notes_entry = ctk.CTkEntry(self, width=250)
        if existing and existing["Notes"]:
            self.notes_entry.insert(0, existing["Notes"])
        self.notes_entry.grid(row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkButton(self, text="Save Contract", command=self.save, fg_color=theme.BRASS,
                      hover_color=theme.INK, font=theme.FONT_BODY_BOLD).grid(row=row, column=0, columnspan=2, pady=20)

        if existing:
            self._on_type_change(self.type_var.get())

    def _on_type_change(self, choice):
        if choice == "Running":
            self.amount_entry.configure(state="disabled")
            self.amount_entry.delete(0, "end")
        else:
            self.amount_entry.configure(state="normal")

    def _selected_contractor(self):
        label = self.contractor_var.get()
        clean_label = label.replace("⭐ ", "")
        return next((c for c in self.contractors if c["Name"] == clean_label), None)

    def save(self):
        contractor = self._selected_contractor()
        if not contractor:
            messagebox.showerror("Missing contractor", "Select a Contractor.", parent=self)
            return

        contract_type = self.type_var.get()
        amount = None
        if contract_type == "Fixed":
            try:
                amount = float(self.amount_entry.get().strip() or 0)
            except ValueError:
                messagebox.showerror("Invalid number", "Contract Amount must be a number.", parent=self)
                return
            if amount <= 0:
                messagebox.showerror("Missing amount", "Fixed contracts need a Contract Amount greater than zero.", parent=self)
                return

        commission_type = self.commission_type_var.get()
        commission_value = None
        if commission_type != "-- None --":
            try:
                commission_value = float(self.commission_value_entry.get().strip() or 0)
            except ValueError:
                messagebox.showerror("Invalid number", "Commission Value must be a number.", parent=self)
                return

        if self.existing:
            db.execute(
                """UPDATE trxContract SET ContractorID=?, ContractType=?, ContractAmount=?,
                   CommissionType=?, CommissionValue=?, Notes=?, ModifiedOn=datetime('now') WHERE ContractID=?""",
                (contractor["ContractorID"], contract_type, amount,
                 commission_type if commission_type != "-- None --" else None, commission_value,
                 self.notes_entry.get().strip(), self.existing["ContractID"])
            )
            db.log_activity("Project", self.project_id, "Contract Edited", contractor["Name"])
            self.on_save()
            self.destroy()
            return

        contract_id = db.execute(
            """INSERT INTO trxContract (ProjectID, ContractorID, ContractType, ContractAmount,
               CommissionType, CommissionValue, Notes) VALUES (?,?,?,?,?,?,?)""",
            (self.project_id, contractor["ContractorID"], contract_type, amount,
             commission_type if commission_type != "-- None --" else None, commission_value,
             self.notes_entry.get().strip())
        )

        # Copy the contractor's current Scope of Work into this contract --
        # same copy-not-reference pattern as everything else (BR-002).
        # Editable per-project afterward without touching the contractor's
        # master profile.
        contractor_scope = db.fetch_all("SELECT ScopeID FROM mstContractorScope WHERE ContractorID=?", (contractor["ContractorID"],))
        for scope_row in contractor_scope:
            db.execute("INSERT INTO trxContractScope (ContractID, ScopeID) VALUES (?,?)", (contract_id, scope_row["ScopeID"]))

        db.log_activity("Project", self.project_id, "Contract Created", contractor["Name"])
        self.on_save()
        self.destroy()


class RecordContractPaymentDialog(ctk.CTkToplevel):
    def __init__(self, master, contract, on_save):
        super().__init__(master)
        self.transient(self.master.winfo_toplevel())
        self.contract = contract
        self.on_save = on_save
        paid_so_far = get_contract_paid(contract["ContractID"])

        self.title("Record Contract Payment")
        self.geometry("380x420")
        self.configure(fg_color=theme.PARCHMENT)
        self.grab_set()

        ctk.CTkLabel(self, text="Record Payment", font=theme.FONT_SUBHEADING, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 5))
        if contract["ContractAmount"] is not None:
            effective = get_contract_effective_amount(contract)
            balance = effective - paid_so_far
            ctk.CTkLabel(self, text=f"Balance due: ₹{balance:,.2f}", font=theme.FONT_SMALL,
                        text_color=theme.MUTED).pack(anchor="w", padx=20, pady=(0, 15))
        else:
            ctk.CTkLabel(self, text=f"Running contract -- paid to date: ₹{paid_so_far:,.2f}",
                        font=theme.FONT_SMALL, text_color=theme.MUTED).pack(anchor="w", padx=20, pady=(0, 15))

        ctk.CTkLabel(self, text="Payment Date", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.date_entry = DateEntry(self, width=20, date_pattern="yyyy-mm-dd", background=theme.BRASS,
                                    foreground="white", borderwidth=1, headersbackground=theme.INK,
                                    headersforeground="white", selectbackground=theme.BRASS)
        self.date_entry.pack(anchor="w", padx=20, pady=(0, 10))

        ctk.CTkLabel(self, text="Amount (₹) *", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.amount_entry = ctk.CTkEntry(self, width=250)
        apply_decimal_only(self, self.amount_entry)
        self.amount_entry.pack(padx=20, pady=(0, 10))

        ctk.CTkLabel(self, text="Payment Type", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.type_var = ctk.StringVar(value="Partial")
        ctk.CTkOptionMenu(self, values=PAYMENT_TYPE_OPTIONS, variable=self.type_var, width=250).pack(padx=20, pady=(0, 10))

        ctk.CTkLabel(self, text="Payment Mode", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.mode_var = ctk.StringVar(value=PAYMENT_MODE_OPTIONS[0])
        ctk.CTkOptionMenu(self, values=PAYMENT_MODE_OPTIONS, variable=self.mode_var, width=250).pack(padx=20, pady=(0, 15))

        ctk.CTkButton(self, text="Save Payment", command=self.save, fg_color=theme.BRASS,
                     hover_color=theme.INK, font=theme.FONT_BODY_BOLD).pack(pady=10)

    def save(self):
        try:
            amount = float(self.amount_entry.get().strip() or 0)
        except ValueError:
            messagebox.showerror("Invalid number", "Amount must be a number.", parent=self)
            return
        if amount <= 0:
            messagebox.showerror("Invalid amount", "Amount must be greater than zero.", parent=self)
            return

        payment_date = self.date_entry.get_date().isoformat()
        db.execute("INSERT INTO trxContractPayment (ContractID, PaymentDate, Amount, PaymentType, PaymentMode) VALUES (?,?,?,?,?)",
                   (self.contract["ContractID"], payment_date, amount, self.type_var.get(), self.mode_var.get()))
        db.log_activity("Project", self.contract["ProjectID"], "Contract Payment Recorded",
                        f"₹{amount:,.2f} ({self.type_var.get()})")
        self.on_save()
        self.destroy()


class RecordContractAdjustmentDialog(ctk.CTkToplevel):
    """
    Real, audited change to a Fixed contract's final committed amount --
    for a negotiated discount, a scope change, or a rounding correction
    made after the original amount was agreed. Unlike Edit Contract
    (which silently overwrites ContractAmount with no record of what
    changed or why), every adjustment here is kept as its own dated,
    reasoned row in trxContractAdjustment. The original ContractAmount is
    never touched, so the full history of what changed and why stays
    visible on the contract going forward.
    """
    def __init__(self, master, contract, on_save):
        super().__init__(master)
        self.transient(self.master.winfo_toplevel())
        self.contract = contract
        self.on_save = on_save
        self.title("Record Contract Adjustment")
        self.geometry("400x480")
        self.configure(fg_color=theme.PARCHMENT)
        self.grab_set()

        original = contract["ContractAmount"]
        adjustments_total = get_contract_adjustments_total(contract["ContractID"])
        effective = original + adjustments_total

        ctk.CTkLabel(self, text="Record Adjustment", font=theme.FONT_SUBHEADING, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 5))
        ctk.CTkLabel(self, text=f"Original Contract Amount: ₹{original:,.2f}\n"
                                f"Adjustments so far: ₹{adjustments_total:,.2f}\n"
                                f"Current Adjusted Amount: ₹{effective:,.2f}",
                    font=theme.FONT_SMALL, text_color=theme.MUTED, justify="left").pack(
            anchor="w", padx=20, pady=(0, 15))

        ctk.CTkLabel(self, text="Adjustment Type", font=theme.FONT_BODY, text_color=theme.INK).pack(
            anchor="w", padx=20)
        self.direction_var = ctk.StringVar(value="Decrease (discount / reduction)")
        ctk.CTkOptionMenu(self, values=["Decrease (discount / reduction)", "Increase (extra scope / charge)"],
                         variable=self.direction_var, width=340).pack(padx=20, pady=(0, 10))

        ctk.CTkLabel(self, text="Amount (₹) *", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.amount_entry = ctk.CTkEntry(self, width=340)
        apply_decimal_only(self, self.amount_entry)
        self.amount_entry.pack(padx=20, pady=(0, 10))

        ctk.CTkLabel(self, text="Adjustment Date", font=theme.FONT_BODY, text_color=theme.INK).pack(
            anchor="w", padx=20)
        self.date_entry = DateEntry(self, width=20, date_pattern="yyyy-mm-dd", background=theme.BRASS,
                                    foreground="white", borderwidth=1, headersbackground=theme.INK,
                                    headersforeground="white", selectbackground=theme.BRASS)
        self.date_entry.pack(anchor="w", padx=20, pady=(0, 10))

        ctk.CTkLabel(self, text="Reason *", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.reason_entry = ctk.CTkTextbox(self, width=340, height=80)
        self.reason_entry.pack(padx=20, pady=(0, 15))

        ctk.CTkButton(self, text="Save Adjustment", command=self.save, fg_color=theme.BRASS,
                     hover_color=theme.INK, font=theme.FONT_BODY_BOLD).pack(pady=10)

    def save(self):
        try:
            amount = float(self.amount_entry.get().strip() or 0)
        except ValueError:
            messagebox.showerror("Invalid number", "Amount must be a number.", parent=self)
            return
        if amount <= 0:
            messagebox.showerror(
                "Invalid amount",
                "Enter the adjustment size as a positive number -- use the Adjustment Type dropdown above "
                "to set whether it increases or decreases the contract amount.", parent=self)
            return
        reason = self.reason_entry.get("1.0", "end").strip()
        if not reason:
            messagebox.showerror(
                "Reason required",
                "Enter a reason for this adjustment -- it becomes a permanent part of the contract's record.",
                parent=self)
            return
        signed_amount = -amount if self.direction_var.get().startswith("Decrease") else amount
        adjustment_date = self.date_entry.get_date().isoformat()
        db.execute("INSERT INTO trxContractAdjustment (ContractID, AdjustmentDate, Amount, Reason) VALUES (?,?,?,?)",
                   (self.contract["ContractID"], adjustment_date, signed_amount, reason))
        db.log_activity("Project", self.contract["ProjectID"], "Contract Adjustment Recorded",
                        f"{'−' if signed_amount < 0 else '+'}₹{abs(signed_amount):,.2f} — {reason}")
        self.on_save()
        self.destroy()


class RecordCommissionReceiptDialog(ctk.CTkToplevel):
    def __init__(self, master, contract, on_save):
        super().__init__(master)
        self.transient(self.master.winfo_toplevel())
        self.contract = contract
        self.on_save = on_save
        expected = get_commission_expected(contract)
        received = db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxCommissionReceipt WHERE ContractID=?",
                                (contract["ContractID"],))["t"]

        self.title("Record Commission Receipt")
        self.geometry("380x280")
        self.configure(fg_color=theme.PARCHMENT)
        self.grab_set()

        ctk.CTkLabel(self, text="Record Commission Receipt", font=theme.FONT_SUBHEADING, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 5))
        ctk.CTkLabel(self, text=f"Expected: ₹{expected:,.2f}  ·  Received: ₹{received:,.2f}  ·  "
                                f"Outstanding: ₹{expected-received:,.2f}", font=theme.FONT_SMALL,
                    text_color=theme.MUTED, wraplength=320, justify="left").pack(anchor="w", padx=20, pady=(0, 15))

        ctk.CTkLabel(self, text="Amount (₹) *", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.amount_entry = ctk.CTkEntry(self, width=250)
        apply_decimal_only(self, self.amount_entry)
        self.amount_entry.pack(padx=20, pady=(0, 15))

        ctk.CTkButton(self, text="Save Receipt", command=self.save, fg_color=theme.BRASS,
                     hover_color=theme.INK, font=theme.FONT_BODY_BOLD).pack(pady=10)

    def save(self):
        try:
            amount = float(self.amount_entry.get().strip() or 0)
        except ValueError:
            messagebox.showerror("Invalid number", "Amount must be a number.", parent=self)
            return
        if amount <= 0:
            messagebox.showerror("Invalid amount", "Amount must be greater than zero.", parent=self)
            return
        db.execute("INSERT INTO trxCommissionReceipt (ContractID, Amount) VALUES (?,?)",
                   (self.contract["ContractID"], amount))
        db.log_activity("Project", self.contract["ProjectID"], "Commission Receipt Recorded", f"₹{amount:,.2f}")
        self.on_save()
        self.destroy()


CALCULATION_METHOD_OPTIONS = ["Direct", "Board Calculation"]
ITEM_UNIT_OPTIONS = ["Sq.ft", "RFT", "Nos.", "Fixed Amount", "CFT", "Cum", "Kg", "Custom"]

# Real, confirmed board sizes for common materials -- "Custom" is the
# default and leaves every field exactly as the person typed it. Gypsum
# Board's 6' x 4' size is per direct, explicit confirmation (the actual
# standard size this business's suppliers use for false ceiling work,
# not assumed from a generic industry figure). Plywood's 8' x 4' is the
# same board size already confirmed and documented in BUSINESS_RULES.md
# (BR-006's own worked example) -- offered here as a named preset too,
# not left as an undocumented one-off. Only these two are listed because
# only these two have a real, confirmed size; guessing at sizes for
# other materials would risk silently entering a wrong dimension.
BOARD_PRESETS = {
    "Custom": (None, None),
    "Gypsum Board (6' x 4')": (6.0, 4.0),
    "Plywood Board (8' x 4')": (8.0, 4.0),
}


def calculate_board_area(length, width, quantity):
    """BR-006: Sq.ft = Length x Width x Quantity. Board is never a unit itself."""
    return (length or 0) * (width or 0) * (quantity or 0)


class ManageContractItemsDialog(ctk.CTkToplevel):
    def __init__(self, master, contract_id, on_save):
        super().__init__(master)
        self.transient(self.master.winfo_toplevel())
        self.contract_id = contract_id
        self.on_save = on_save
        self.title("Manage Contract Items")
        self.geometry("620x520")
        self.configure(fg_color=theme.PARCHMENT)
        self.grab_set()

        ctk.CTkLabel(self, text="Contract Items", font=theme.FONT_SUBHEADING, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 10))
        ctk.CTkButton(self, text="+ Add Item", command=self._add_item, fg_color=theme.BRASS,
                     hover_color=theme.INK, font=theme.FONT_SMALL, height=28).pack(anchor="w", padx=20, pady=(0, 10))

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color=theme.WHITE)
        self.list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        self.refresh()

    def refresh(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        items = db.fetch_all("SELECT * FROM trxContractItem WHERE ContractID=? ORDER BY ContractItemID", (self.contract_id,))
        if not items:
            ctk.CTkLabel(self.list_frame, text="No items yet.", font=theme.FONT_SMALL, text_color=theme.MUTED).pack(pady=10)
            return
        for item in items:
            row = ctk.CTkFrame(self.list_frame, fg_color=theme.PARCHMENT, corner_radius=6)
            row.pack(fill="x", pady=4, padx=4)
            if item["CalculationMethod"] == "Board Calculation":
                detail = (f"{item['ItemName']} — {item['BoardLength']:.1f}' x {item['BoardWidth']:.1f}' x "
                         f"{item['BoardQty']:.0f} boards = {item['Quantity']:.1f} {item['Unit']} @ ₹{item['Rate']:,.2f}")
            else:
                detail = f"{item['ItemName']} — {item['Quantity'] or 0:.1f} {item['Unit']} @ ₹{item['Rate']:,.2f}"
            ctk.CTkLabel(row, text=detail, font=theme.FONT_SMALL, text_color=theme.INK, anchor="w").pack(
                side="left", padx=10, pady=8, fill="x", expand=True)
            ctk.CTkLabel(row, text=f"₹{item['Amount']:,.2f}", font=theme.FONT_BODY_BOLD, text_color=theme.BRASS).pack(
                side="right", padx=10)

    def _add_item(self):
        ContractItemDialog(self, self.contract_id, on_save=self._on_item_saved)

    def _on_item_saved(self):
        self.refresh()
        self.on_save()


class ContractItemDialog(ctk.CTkToplevel):
    def __init__(self, master, contract_id, on_save):
        super().__init__(master)
        self.transient(self.master.winfo_toplevel())
        self.contract_id = contract_id
        self.on_save = on_save
        self.title("Add Contract Item")
        self.geometry("420x520")
        self.configure(fg_color=theme.PARCHMENT)
        self.grab_set()

        ctk.CTkLabel(self, text="Add Contract Item", font=theme.FONT_SUBHEADING, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 10))

        ctk.CTkLabel(self, text="Item Name *", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.name_entry = ctk.CTkEntry(self, width=340)
        self.name_entry.pack(padx=20, pady=(0, 10))

        ctk.CTkLabel(self, text="Calculation Method", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.method_var = ctk.StringVar(value="Direct")
        ctk.CTkOptionMenu(self, values=CALCULATION_METHOD_OPTIONS, variable=self.method_var, width=340,
                          command=self._on_method_change).pack(padx=20, pady=(0, 10))

        # ---------------- Direct method fields ----------------
        self.direct_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(self.direct_frame, text="Quantity", font=theme.FONT_SMALL, text_color=theme.MUTED).grid(row=0, column=0, sticky="w")
        self.direct_qty_entry = ctk.CTkEntry(self.direct_frame, width=150)
        apply_decimal_only(self, self.direct_qty_entry)
        self.direct_qty_entry.grid(row=1, column=0, padx=(0, 10))
        ctk.CTkLabel(self.direct_frame, text="Unit", font=theme.FONT_SMALL, text_color=theme.MUTED).grid(row=0, column=1, sticky="w")
        self.unit_var = ctk.StringVar(value=ITEM_UNIT_OPTIONS[0])
        ctk.CTkOptionMenu(self.direct_frame, values=ITEM_UNIT_OPTIONS, variable=self.unit_var, width=150).grid(row=1, column=1)

        # ---------------- Board Calculation fields ----------------
        self.board_frame = ctk.CTkFrame(self, fg_color="transparent")

        # Quick presets -- real, confirmed board sizes for common items,
        # so the person doesn't have to retype the same dimensions every
        # time. "Custom" (the default) leaves everything exactly as
        # before -- this is purely additive, not a change to how Board
        # Calculation itself works, and does NOT touch the 8'x4' example
        # already confirmed and documented in BUSINESS_RULES.md for a
        # different item. Only Gypsum Board's real, confirmed size (6'x4')
        # is added here; other materials stay manual until their own real
        # size is confirmed, rather than guessed at.
        ctk.CTkLabel(self.board_frame, text="Quick Preset", font=theme.FONT_SMALL, text_color=theme.MUTED).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 2))
        self.board_preset_var = ctk.StringVar(value="Custom")
        ctk.CTkOptionMenu(self.board_frame, values=list(BOARD_PRESETS.keys()), variable=self.board_preset_var,
                         width=340, command=self._on_board_preset_change).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 8))

        for i, label in enumerate(["Board Length (ft)", "Board Width (ft)", "No. of Boards"]):
            ctk.CTkLabel(self.board_frame, text=label, font=theme.FONT_SMALL, text_color=theme.MUTED).grid(
                row=2, column=i, sticky="w", padx=(0 if i == 0 else 8, 0))
        self.board_length_entry = ctk.CTkEntry(self.board_frame, width=105)
        self.board_width_entry = ctk.CTkEntry(self.board_frame, width=105)
        self.board_qty_entry = ctk.CTkEntry(self.board_frame, width=105)
        for e in (self.board_length_entry, self.board_width_entry, self.board_qty_entry):
            apply_decimal_only(self, e)
        self.board_length_entry.grid(row=3, column=0)
        self.board_width_entry.grid(row=3, column=1, padx=8)
        self.board_qty_entry.grid(row=3, column=2)
        for e in (self.board_length_entry, self.board_width_entry, self.board_qty_entry):
            e.bind("<KeyRelease>", self._recalc_board_area)
        self.board_area_label = ctk.CTkLabel(self.board_frame, text="Computed: 0.0 Sq.ft", font=theme.FONT_SMALL,
                                             text_color=theme.BRASS)
        self.board_area_label.grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))

        self.fields_container = ctk.CTkFrame(self, fg_color="transparent")
        self.fields_container.pack(fill="x", padx=20, pady=(0, 10))
        self.direct_frame.pack(in_=self.fields_container, fill="x")

        ctk.CTkLabel(self, text="Rate (₹) *", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.rate_entry = ctk.CTkEntry(self, width=340)
        apply_decimal_only(self, self.rate_entry)
        self.rate_entry.pack(padx=20, pady=(0, 15))

        ctk.CTkButton(self, text="Add Item", command=self.save, fg_color=theme.BRASS,
                     hover_color=theme.INK, font=theme.FONT_BODY_BOLD).pack(pady=10)

    def _on_board_preset_change(self, choice):
        length, width = BOARD_PRESETS[choice]
        if length is not None:
            self.board_length_entry.delete(0, "end")
            self.board_length_entry.insert(0, str(length))
            self.board_width_entry.delete(0, "end")
            self.board_width_entry.insert(0, str(width))
            self._recalc_board_area()
            # Only fills the item name if the person hasn't typed one yet
            # -- never overwrites something they've already entered.
            if not self.name_entry.get().strip() and choice != "Custom":
                preset_name = choice.split(" (")[0]
                self.name_entry.insert(0, f"False Ceiling - {preset_name}" if "Gypsum" in preset_name else preset_name)

    def _on_method_change(self, choice):
        self.direct_frame.pack_forget()
        self.board_frame.pack_forget()
        if choice == "Board Calculation":
            self.board_frame.pack(in_=self.fields_container, fill="x")
        else:
            self.direct_frame.pack(in_=self.fields_container, fill="x")

    def _recalc_board_area(self, _event=None):
        try:
            length = float(self.board_length_entry.get().strip() or 0)
            width = float(self.board_width_entry.get().strip() or 0)
            qty = float(self.board_qty_entry.get().strip() or 0)
            area = calculate_board_area(length, width, qty)
            self.board_area_label.configure(text=f"Computed: {area:,.2f} Sq.ft")
        except ValueError:
            self.board_area_label.configure(text="Computed: 0.0 Sq.ft")

    def save(self):
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showerror("Missing name", "Item Name is required.", parent=self)
            return
        try:
            rate = float(self.rate_entry.get().strip() or 0)
        except ValueError:
            messagebox.showerror("Invalid number", "Rate must be a number.", parent=self)
            return

        method = self.method_var.get()
        if method == "Board Calculation":
            try:
                length = float(self.board_length_entry.get().strip() or 0)
                width = float(self.board_width_entry.get().strip() or 0)
                board_qty = float(self.board_qty_entry.get().strip() or 0)
            except ValueError:
                messagebox.showerror("Invalid number", "Board Length, Width, and Quantity must be numbers.", parent=self)
                return
            if length <= 0 or width <= 0 or board_qty <= 0:
                messagebox.showerror("Missing dimensions", "Board Length, Width, and Quantity must all be greater than zero.", parent=self)
                return
            quantity = calculate_board_area(length, width, board_qty)
            unit = "Sq.ft"  # Board is never the unit itself (BR-006) -- always derives Sq.ft
            amount = quantity * rate
            db.execute("""INSERT INTO trxContractItem (ContractID, ItemName, Unit, Rate, CalculationMethod,
                          BoardLength, BoardWidth, BoardQty, Quantity, Amount) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                      (self.contract_id, name, unit, rate, method, length, width, board_qty, quantity, amount))
        else:
            try:
                quantity = float(self.direct_qty_entry.get().strip() or 0)
            except ValueError:
                messagebox.showerror("Invalid number", "Quantity must be a number.", parent=self)
                return
            unit = self.unit_var.get()
            amount = quantity * rate
            db.execute("""INSERT INTO trxContractItem (ContractID, ItemName, Unit, Rate, CalculationMethod,
                          Quantity, Amount) VALUES (?,?,?,?,?,?,?)""",
                      (self.contract_id, name, unit, rate, method, quantity, amount))

        self.on_save()
        self.destroy()

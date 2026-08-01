"""
ADS OS Desktop -- Invoice Center (Commercial module, fifth of six)
Invoices can link to a saved Fee Calculation (module #1) to prefill the
amount, or be entered manually. Paid Amount and Status are always computed
live from actual trxInvoicePayment records -- an invoice is never manually marked
"Paid"; it becomes Paid because payments summing to its Amount were actually
recorded. Overdue is computed at display time from DueDate, not stored, so
it's always accurate without a background job.
"""
import customtkinter as ctk
from tkcalendar import DateEntry
from tkinter import ttk, messagebox
import datetime
import db
import theme
import ui_components as ui
from constants import apply_decimal_only

INVOICE_TYPE_OPTIONS = ["Advance", "Milestone", "Final", "Running"]
PAYMENT_MODE_OPTIONS = ["NEFT", "RTGS", "Cheque", "UPI", "Cash", "Other"]
STATUS_COLORS = {"Draft": "#6B6B6B", "Sent": "#1E5FA8", "Partial": "#B68100",
                  "Paid": "#2E8B57", "Overdue": "#8B2E2E", "Cancelled": "#6B6B6B",
                  "Running": "#6B4E9E"}


def get_invoice_status(invoice, paid_amount):
    if invoice["Status"] in ("Draft", "Cancelled"):
        return invoice["Status"]
    # Running invoices deliberately never resolve to "Paid" -- this type
    # exists specifically for Turnkey projects whose total value grows
    # incrementally as scope is added, not invoiced all at once. Its
    # whole point is to stay open, with Amount increased directly via
    # Edit Invoice as scope grows, rather than being closed out and
    # replaced by a new invoice number the way Milestone/Advance/Final
    # naturally are.
    if invoice["InvoiceType"] == "Running":
        return "Running"
    balance = invoice["Amount"] - paid_amount
    if balance <= 0.01:
        return "Paid"
    if invoice["DueDate"] and invoice["DueDate"] < datetime.date.today().isoformat() and balance > 0.01:
        return "Overdue"
    if paid_amount > 0:
        return "Partial"
    return "Sent"


def get_paid_amount(invoice_id):
    return db.fetch_one("SELECT COALESCE(SUM(Amount), 0) AS total FROM trxInvoicePayment WHERE InvoiceID=?",
                        (invoice_id,))["total"]


def get_active_running_invoice(project_id):
    """
    Real, current Running invoice for this project, if one exists -- the
    single ongoing invoice a Turnkey project's payments accumulate
    against as scope grows. Returns None if this project has no Running
    invoice yet; one is never silently created with a fabricated starting
    amount -- the person is asked for the real current total value the
    first time (see ClientRecordPaymentDialog in client_screen.py).
    """
    return db.fetch_one(
        "SELECT * FROM trxInvoice WHERE ProjectID=? AND InvoiceType='Running' AND Status != 'Cancelled' "
        "ORDER BY InvoiceID DESC LIMIT 1", (project_id,))


class InvoiceCenterPanel(ctk.CTkFrame):
    def __init__(self, master, project_id):
        super().__init__(master, fg_color="transparent")
        self.project_id = project_id
        self.selected_invoice_id = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        ctk.CTkLabel(self, text="Invoice Center", font=theme.FONT_HEADING, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 5))
        ctk.CTkLabel(self, text="Create, manage, and track all invoices for this project.",
                     font=theme.FONT_SMALL, text_color=theme.MUTED).pack(anchor="w", padx=20, pady=(0, 10))

        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=20, pady=(0, 10))

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkButton(toolbar, text="+ New Invoice", command=self.open_add_invoice,
                      fg_color=theme.BRASS, hover_color=theme.INK, font=theme.FONT_SMALL, height=28).pack(side="right")
        self.status_filter_var = ctk.StringVar(value="All Status")
        ctk.CTkOptionMenu(toolbar, values=["All Status", "Draft", "Sent", "Partial", "Paid", "Overdue",
                                          "Cancelled", "Running"],
                          variable=self.status_filter_var, width=140,
                          command=lambda c: self.refresh()).pack(side="right", padx=(0, 10))
        self.search_entry = ctk.CTkEntry(toolbar, placeholder_text="Search invoice number...", width=250)
        self.search_entry.pack(side="left")
        self.search_entry.bind("<KeyRelease>", lambda e: self.refresh())

        columns = ctk.CTkFrame(self, fg_color="transparent")
        columns.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        self.table_frame = ctk.CTkFrame(columns, fg_color=theme.WHITE)
        self.table_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        cols = ("no", "date", "type", "amount", "paid", "balance", "due", "status")
        self.tree = ttk.Treeview(self.table_frame, columns=cols, show="headings", height=16)
        headings = {"no": "Invoice No.", "date": "Date", "type": "Type", "amount": "Amount (₹)",
                    "paid": "Paid (₹)", "balance": "Balance (₹)", "due": "Due Date", "status": "Status"}
        widths = {"no": 100, "date": 90, "type": 80, "amount": 100, "paid": 90, "balance": 90, "due": 90, "status": 80}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c])
        for status, color in STATUS_COLORS.items():
            self.tree.tag_configure(f"status_{status}", foreground=color)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_select())
        self.tree.bind("<Double-1>", lambda e: self.open_edit_invoice())

        hscrollbar = ttk.Scrollbar(self.table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscroll=hscrollbar.set)
        hscrollbar.pack(side="bottom", fill="x")

        scrollbar = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self.tree.pack(fill="both", expand=True, side="left")

        details_panel = ctk.CTkFrame(columns, fg_color=theme.WHITE, corner_radius=8, width=260)
        details_panel.pack(side="left", fill="y")
        details_panel.pack_propagate(False)
        ctk.CTkLabel(details_panel, text="Invoice Details", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=15, pady=(15, 10))
        self.details_label = ctk.CTkLabel(details_panel, text="Select an invoice to see details and payments.",
                                          font=theme.FONT_BODY, text_color=theme.MUTED, justify="left", wraplength=230)
        self.details_label.pack(anchor="w", padx=15, pady=(0, 10))
        ctk.CTkButton(details_panel, text="Record Payment", command=self.open_record_payment,
                      fg_color=theme.BRASS, hover_color=theme.INK, font=theme.FONT_SMALL, height=26).pack(
            padx=15, pady=(0, 10), fill="x")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 15))
        ctk.CTkButton(footer, text="Edit Invoice", command=self.open_edit_invoice,
                      fg_color=theme.INK, font=theme.FONT_SMALL, height=26).pack(side="left", padx=(0, 8))
        ctk.CTkButton(footer, text="Mark as Sent", command=self.mark_as_sent,
                      fg_color="#1E5FA8", hover_color=theme.INK, font=theme.FONT_SMALL, height=26).pack(side="left", padx=(0, 8))
        ctk.CTkButton(footer, text="Cancel Invoice", command=self.cancel_invoice,
                      fg_color="#8B2E2E", hover_color="#5E1F1F", font=theme.FONT_SMALL, height=26).pack(side="left")

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        if hasattr(self, "_empty_state_frame"):
            self._empty_state_frame.destroy()
            del self._empty_state_frame

        search = self.search_entry.get().strip().lower()
        status_filter = self.status_filter_var.get()

        invoices = db.fetch_all("SELECT * FROM trxInvoice WHERE ProjectID=? ORDER BY InvoiceDate DESC, InvoiceID DESC",
                                (self.project_id,))
        if search:
            invoices = [i for i in invoices if search in i["InvoiceNo"].lower()]

        # Status is computed, not stored -- resolve it once up front so both
        # the empty-state check and the status filter use the same value.
        rows = []
        for inv in invoices:
            paid = get_paid_amount(inv["InvoiceID"])
            status = get_invoice_status(inv, paid)
            if status_filter != "All Status" and status != status_filter:
                continue
            rows.append((inv, paid, status))

        total_invoiced = 0
        total_paid = 0
        total_overdue = 0
        draft_count = 0

        if not rows:
            self.tree.pack_forget()
            self._empty_state_frame = ui.empty_state(
                self.table_frame, "No invoices yet.", "+ New Invoice", self.open_add_invoice)
            self._render_stats(len(invoices), 0, 0, 0, 0)
            return
        self.tree.pack(fill="both", expand=True, side="left")

        for inv, paid, status in rows:
            balance = inv["Amount"] - paid
            self.tree.insert("", "end", iid=inv["InvoiceID"],
                             values=(inv["InvoiceNo"], inv["InvoiceDate"], inv["InvoiceType"],
                                    f"{inv['Amount']:,.2f}", f"{paid:,.2f}", f"{balance:,.2f}",
                                    inv["DueDate"] or "-", status),
                             tags=(f"status_{status}",))

            total_invoiced += inv["Amount"]
            total_paid += paid
            if status == "Overdue":
                total_overdue += balance
            if status == "Draft":
                draft_count += 1

        self._render_stats(len(invoices), total_invoiced, total_paid, total_overdue, draft_count)

    def _render_stats(self, count, invoiced, paid, overdue, draft_count):
        for w in self.stats_frame.winfo_children():
            w.destroy()
        outstanding = invoiced - paid
        stats = [
            ("Total Invoices", str(count)), ("Total Invoiced", f"₹{invoiced:,.2f}"),
            ("Paid Amount", f"₹{paid:,.2f}"), ("Outstanding", f"₹{outstanding:,.2f}"),
            ("Overdue", f"₹{overdue:,.2f}"), ("Draft", str(draft_count)),
        ]
        for label, value in stats:
            card = ctk.CTkFrame(self.stats_frame, fg_color=theme.WHITE, corner_radius=8, width=150, height=70)
            card.pack(side="left", padx=(0, 10))
            card.pack_propagate(False)
            ctk.CTkLabel(card, text=value, font=theme.FONT_BODY_BOLD, text_color=theme.BRASS).pack(pady=(10, 0))
            ctk.CTkLabel(card, text=label, font=theme.FONT_SMALL, text_color=theme.MUTED).pack()

    def _on_select(self):
        sel = self.tree.selection()
        if not sel:
            return
        invoice_id = int(sel[0])
        self.selected_invoice_id = invoice_id
        inv = db.fetch_one("SELECT * FROM trxInvoice WHERE InvoiceID=?", (invoice_id,))
        paid = get_paid_amount(invoice_id)
        status = get_invoice_status(inv, paid)
        payments = db.fetch_all("SELECT * FROM trxInvoicePayment WHERE InvoiceID=? ORDER BY PaymentDate DESC", (invoice_id,))

        lines = [f"{inv['InvoiceNo']}", f"Type: {inv['InvoiceType']}", f"Status: {status}",
                 f"Amount: ₹{inv['Amount']:,.2f}", f"Paid: ₹{paid:,.2f}",
                 f"Balance: ₹{inv['Amount'] - paid:,.2f}", ""]
        if payments:
            lines.append(f"Payments ({len(payments)}):")
            for p in payments[:5]:
                lines.append(f"  {p['PaymentDate']}: ₹{p['Amount']:,.2f} ({p['PaymentMode'] or '-'})")
        else:
            lines.append("No payments recorded yet.")
        if inv["Notes"]:
            lines.append(f"\nNotes: {inv['Notes']}")
        self.details_label.configure(text="\n".join(lines))

    def _selected_invoice_or_warn(self):
        if self.selected_invoice_id is None:
            messagebox.showinfo("Select an invoice", "Please select an invoice from the list first.", parent=self)
            return None
        return self.selected_invoice_id

    def open_add_invoice(self):
        InvoiceForm(self, self.project_id, on_save=self.refresh)

    def open_edit_invoice(self):
        invoice_id = self._selected_invoice_or_warn()
        if invoice_id is None:
            return
        invoice = db.fetch_one("SELECT * FROM trxInvoice WHERE InvoiceID=?", (invoice_id,))
        InvoiceForm(self, self.project_id, on_save=self.refresh, existing=invoice)

    def open_record_payment(self):
        invoice_id = self._selected_invoice_or_warn()
        if invoice_id is None:
            return
        invoice = db.fetch_one("SELECT * FROM trxInvoice WHERE InvoiceID=?", (invoice_id,))
        RecordPaymentDialog(self, invoice, on_save=self.refresh, project_id=self.project_id)

    def mark_as_sent(self):
        invoice_id = self._selected_invoice_or_warn()
        if invoice_id is None:
            return
        db.execute("UPDATE trxInvoice SET Status='Sent', ModifiedOn=datetime('now') WHERE InvoiceID=? AND Status='Draft'",
                   (invoice_id,))
        db.log_activity("Project", self.project_id, "Invoice Marked Sent", str(invoice_id))
        self.refresh()

    def cancel_invoice(self):
        invoice_id = self._selected_invoice_or_warn()
        if invoice_id is None:
            return
        paid = get_paid_amount(invoice_id)
        if paid > 0:
            messagebox.showerror("Cannot cancel", "This invoice has payments recorded against it and cannot be cancelled.", parent=self)
            return
        if messagebox.askyesno("Confirm cancel", "Cancel this invoice? It will be kept for record-keeping but marked Cancelled.", parent=self):
            db.execute("UPDATE trxInvoice SET Status='Cancelled', ModifiedOn=datetime('now') WHERE InvoiceID=?", (invoice_id,))
            db.log_activity("Project", self.project_id, "Invoice Cancelled", str(invoice_id))
            self.refresh()


class InvoiceForm(ctk.CTkToplevel):
    def __init__(self, master, project_id, on_save, existing=None):
        super().__init__(master)
        self.project_id = project_id
        self.on_save = on_save
        self.existing = existing
        self.title("Edit Invoice" if existing else "New Invoice")
        self.geometry("460x560")
        self.configure(fg_color=theme.PARCHMENT)
        self.transient(self.master.winfo_toplevel())  # anchor to the real top-level window -- these dialogs are opened many levels deep inside ProjectWorkspace/CTkTabview, unlike ClientForm/ProjectForm which are shallow
        self.grab_set()

        self.fee_calcs = db.fetch_all(
            "SELECT CalculationID, CalculationName, TotalFee FROM trxFeeCalculation WHERE ProjectID=? ORDER BY CalculationID DESC",
            (project_id,))

        row = 0
        ctk.CTkLabel(self, text=self.title(), font=theme.FONT_SUBHEADING, text_color=theme.INK).grid(
            row=row, column=0, columnspan=2, padx=15, pady=(15, 10), sticky="w")
        row += 1

        ctk.CTkLabel(self, text="Invoice Type", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.type_var = ctk.StringVar(value=(existing["InvoiceType"] if existing else "Milestone"))
        ctk.CTkOptionMenu(self, values=INVOICE_TYPE_OPTIONS, variable=self.type_var, width=250).grid(
            row=row, column=1, padx=15, pady=8)
        row += 1

        self.selected_fee_calc_id = None
        if self.fee_calcs and not existing:
            ctk.CTkLabel(self, text="Base on Fee Calculation", font=theme.FONT_BODY, text_color=theme.INK).grid(
                row=row, column=0, sticky="w", padx=15, pady=8)
            calc_names = ["-- Enter Manually --"] + [f"{c['CalculationName']} (₹{c['TotalFee']:,.2f})" for c in self.fee_calcs]
            self.fee_calc_var = ctk.StringVar(value=calc_names[0])
            ctk.CTkOptionMenu(self, values=calc_names, variable=self.fee_calc_var, width=250,
                              command=self._on_fee_calc_change).grid(row=row, column=1, padx=15, pady=8)
            row += 1
        else:
            self.fee_calc_var = None

        ctk.CTkLabel(self, text="Amount (₹) *", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.amount_entry = ctk.CTkEntry(self, width=250)
        apply_decimal_only(self, self.amount_entry)
        self.amount_entry.insert(0, str(existing["Amount"]) if existing else "0")
        self.amount_entry.grid(row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self, text="Invoice Date", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.date_entry = DateEntry(self, width=20, date_pattern="yyyy-mm-dd", background=theme.BRASS,
                                    foreground="white", borderwidth=1, headersbackground=theme.INK,
                                    headersforeground="white", selectbackground=theme.BRASS)
        if existing and existing["InvoiceDate"]:
            try:
                self.date_entry.set_date(existing["InvoiceDate"])
            except Exception:
                pass  # malformed legacy date string -- fall back to today rather than crash
        self.date_entry.grid(row=row, column=1, padx=15, pady=8, sticky="w")
        row += 1

        ctk.CTkLabel(self, text="Due Date", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.due_entry = ctk.CTkEntry(self, width=250, placeholder_text="YYYY-MM-DD")
        if existing and existing["DueDate"]:
            self.due_entry.insert(0, existing["DueDate"])
        self.due_entry.grid(row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self, text="Notes", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.notes_entry = ctk.CTkEntry(self, width=250)
        if existing and existing["Notes"]:
            self.notes_entry.insert(0, existing["Notes"])
        self.notes_entry.grid(row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkButton(self, text="Save", command=self.save, fg_color=theme.BRASS,
                      hover_color=theme.INK, font=theme.FONT_BODY_BOLD).grid(
            row=row, column=0, columnspan=2, pady=20)

    def _on_fee_calc_change(self, choice):
        if choice == "-- Enter Manually --":
            self.selected_fee_calc_id = None
            return
        idx = [f"{c['CalculationName']} (₹{c['TotalFee']:,.2f})" for c in self.fee_calcs].index(choice)
        calc = self.fee_calcs[idx]
        self.selected_fee_calc_id = calc["CalculationID"]
        self.amount_entry.delete(0, "end")
        self.amount_entry.insert(0, str(calc["TotalFee"]))

    def save(self):
        try:
            amount = float(self.amount_entry.get().strip() or 0)
        except ValueError:
            messagebox.showerror("Invalid number", "Amount must be a number.", parent=self)
            return
        if amount <= 0:
            messagebox.showerror("Invalid amount", "Amount must be greater than zero.", parent=self)
            return

        invoice_date = self.date_entry.get_date().isoformat()
        due_date = self.due_entry.get().strip() or None
        notes = self.notes_entry.get().strip()

        if self.existing:
            db.execute(
                """UPDATE trxInvoice SET InvoiceType=?, Amount=?, InvoiceDate=?, DueDate=?, Notes=?,
                   ModifiedOn=datetime('now') WHERE InvoiceID=?""",
                (self.type_var.get(), amount, invoice_date, due_date, notes, self.existing["InvoiceID"])
            )
            db.log_activity("Project", self.project_id, "Invoice Updated", self.existing["InvoiceNo"])
        else:
            invoice_no = db.next_code("INV", "trxInvoice", "InvoiceNo")
            # Real bug fix (found via direct testing): every new invoice
            # previously fell through to the schema's default Status
            # ('Draft') since this INSERT never set one explicitly. For
            # Milestone/Advance/Final that's the intended starting state
            # (not yet sent to the client) -- but for Running, "Draft"
            # is a dead end: get_invoice_status()'s Draft/Cancelled
            # short-circuit correctly takes priority over the
            # InvoiceType=='Running' check (a genuinely Draft invoice
            # SHOULD show as Draft, Running or not), so a Running
            # invoice stuck at Draft never resolves to "Running" no
            # matter how much gets paid against it, until someone
            # manually clicks "Mark as Sent." ClientRecordPaymentDialog
            # (client_screen.py) already avoided this trap by setting
            # Status='Sent' when it creates a Running invoice -- this
            # brings the normal Invoice Center creation path in line
            # with that already-correct, already-verified behavior.
            starting_status = "Sent" if self.type_var.get() == "Running" else "Draft"
            db.execute(
                """INSERT INTO trxInvoice (ProjectID, InvoiceNo, InvoiceDate, DueDate, InvoiceType, Amount,
                   FeeCalculationID, Notes, Status) VALUES (?,?,?,?,?,?,?,?,?)""",
                (self.project_id, invoice_no, invoice_date, due_date, self.type_var.get(), amount,
                 self.selected_fee_calc_id, notes, starting_status)
            )
            db.log_activity("Project", self.project_id, "Invoice Created", invoice_no)

        self.on_save()
        self.destroy()


class RecordPaymentDialog(ctk.CTkToplevel):
    def __init__(self, master, invoice, on_save, project_id=None):
        super().__init__(master)
        self.invoice = invoice
        self.on_save = on_save
        self.project_id = project_id
        paid_so_far = get_paid_amount(invoice["InvoiceID"])
        balance = invoice["Amount"] - paid_so_far
        fully_paid = balance <= 0.01

        self.title(f"Record Payment — {invoice['InvoiceNo']}")
        self.geometry("380x420" if fully_paid else "380x340")
        self.configure(fg_color=theme.PARCHMENT)
        self.transient(self.master.winfo_toplevel())  # anchor to the real top-level window -- these dialogs are opened many levels deep inside ProjectWorkspace/CTkTabview, unlike ClientForm/ProjectForm which are shallow
        self.grab_set()

        ctk.CTkLabel(self, text="Record Payment", font=theme.FONT_SUBHEADING, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 5))
        ctk.CTkLabel(self, text=f"{invoice['InvoiceNo']} -- Balance due: ₹{balance:,.2f}",
                     font=theme.FONT_SMALL, text_color=theme.MUTED).pack(anchor="w", padx=20, pady=(0, 5 if fully_paid else 15))

        # Real fix for a real gap: previously, once an invoice was fully
        # paid, this dialog pre-filled "0.00" with no other explanation --
        # it looked like a dead end, even though the code never actually
        # blocked entering a bigger number. If a client is paying MORE
        # because the contract's scope/value has genuinely grown, that's
        # supported, but it's worth being explicit about it here rather
        # than leaving the person to guess, and worth pointing at the
        # better-aligned option: a new invoice for the extra scope makes
        # the increased total contract value show up correctly in every
        # report that sums invoices, instead of sitting as an unexplained
        # overpayment against a project that already looked "done."
        if fully_paid:
            note = ctk.CTkFrame(self, fg_color=theme.WHITE, corner_radius=8)
            note.pack(fill="x", padx=20, pady=(0, 12))
            if invoice["InvoiceType"] == "Running":
                # Running invoices exist precisely for this case -- scope
                # keeps growing, so "fully paid" just means paid up to the
                # CURRENT amount, not that the project is done. The right
                # move is to grow this same invoice's Amount, not spin up
                # a new invoice number the way Milestone/Final would.
                ctk.CTkLabel(note, text="This Running invoice is fully paid against its current amount.",
                            font=theme.FONT_SMALL, text_color=theme.INK).pack(anchor="w", padx=12, pady=(10, 2))
                ctk.CTkLabel(note, text="As more scope is added and the total value grows, increase the Amount "
                                        "on this same invoice via Edit Invoice, then continue recording payments "
                                        "here as they come in.",
                            font=("Segoe UI", 9), text_color=theme.MUTED, wraplength=320, justify="left").pack(
                    anchor="w", padx=12, pady=(0, 8))
                ctk.CTkButton(note, text="Edit Invoice", command=self._open_edit_invoice,
                             fg_color=theme.BRASS, hover_color=theme.INK, font=theme.FONT_SMALL, height=26).pack(
                    fill="x", padx=12, pady=(0, 10))
            else:
                ctk.CTkLabel(note, text="This invoice is already fully paid.", font=theme.FONT_SMALL,
                            text_color=theme.INK).pack(anchor="w", padx=12, pady=(10, 2))
                ctk.CTkLabel(note, text="If the client paid extra because the contract's scope or value has "
                                        "grown, you can still enter that amount below as an overpayment against "
                                        "this invoice -- or, better for reporting, raise a new invoice for the "
                                        "additional scope so the total contract value shows correctly everywhere.",
                            font=("Segoe UI", 9), text_color=theme.MUTED, wraplength=320, justify="left").pack(
                    anchor="w", padx=12, pady=(0, 8))
                if self.project_id:
                    ctk.CTkButton(note, text="Raise New Invoice Instead", command=self._open_new_invoice,
                                 fg_color=theme.BRASS, hover_color=theme.INK, font=theme.FONT_SMALL, height=26).pack(
                        fill="x", padx=12, pady=(0, 10))

        ctk.CTkLabel(self, text="Amount Received (₹) *", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.amount_entry = ctk.CTkEntry(self, width=250,
                                         placeholder_text="Enter the extra amount received" if fully_paid else None)
        apply_decimal_only(self, self.amount_entry)
        # Only pre-fills the exact balance for the normal, not-yet-fully-
        # paid case -- pre-filling "0.00" here was itself part of the
        # confusion, implying there was nothing left to type.
        if not fully_paid:
            self.amount_entry.insert(0, f"{balance:.2f}")
        self.amount_entry.pack(padx=20, pady=(0, 10))

        ctk.CTkLabel(self, text="Payment Date", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.date_entry = DateEntry(self, width=20, date_pattern="yyyy-mm-dd", background=theme.BRASS,
                                    foreground="white", borderwidth=1, headersbackground=theme.INK,
                                    headersforeground="white", selectbackground=theme.BRASS)
        self.date_entry.pack(anchor="w", padx=20, pady=(0, 10))

        ctk.CTkLabel(self, text="Payment Mode", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.mode_var = ctk.StringVar(value="NEFT")
        ctk.CTkOptionMenu(self, values=PAYMENT_MODE_OPTIONS, variable=self.mode_var, width=250).pack(padx=20, pady=(0, 15))

        ctk.CTkButton(self, text="Save Payment", command=self.save, fg_color=theme.BRASS,
                      hover_color=theme.INK, font=theme.FONT_BODY_BOLD).pack(pady=10)

    def _open_new_invoice(self):
        self.destroy()
        InvoiceForm(self.master, self.project_id, on_save=self.on_save)

    def _open_edit_invoice(self):
        self.destroy()
        InvoiceForm(self.master, self.project_id, on_save=self.on_save, existing=self.invoice)

    def save(self):
        try:
            amount = float(self.amount_entry.get().strip() or 0)
        except ValueError:
            messagebox.showerror("Invalid number", "Amount must be a number.", parent=self)
            return
        if amount <= 0:
            messagebox.showerror("Invalid amount", "Amount must be greater than zero.", parent=self)
            return

        db.execute(
            "INSERT INTO trxInvoicePayment (InvoiceID, PaymentDate, Amount, PaymentMode) VALUES (?,?,?,?)",
            (self.invoice["InvoiceID"], self.date_entry.get_date().isoformat(), amount, self.mode_var.get())
        )
        db.log_activity("Project", self.invoice["ProjectID"], "Payment Recorded",
                        f"{self.invoice['InvoiceNo']}: ₹{amount:,.2f}")
        messagebox.showinfo("Payment recorded", f"₹{amount:,.2f} recorded against {self.invoice['InvoiceNo']}.", parent=self)
        self.on_save()
        self.destroy()

"""
ADS OS Desktop -- Site Expense Management (Commercial module, new).

Real gap closed, flagged as a known deferred item since v4.9.7 (Landed
Cost's own changelog explicitly deferred this: "Site Expense Management
is treated as a genuinely separate, later milestone... mixing two
different financial concepts (material landed cost vs. non-material
site costs) into a single pass would blur both").

Covers real, non-material site costs that don't belong in Materials
(stocked, purchasable items) or Vendor/Contractor payments (a specific
business partner's invoiced work): labour wages, site transport, tea/
refreshments, tools & consumables, site security, and general
miscellaneous site spend. Project-scoped -- every real expense here is
tied to the project it was actually incurred on.
"""
import customtkinter as ctk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
import db
import theme
import ui_components as ui
from constants import apply_decimal_only

EXPENSE_CATEGORY_OPTIONS = ["Labour Wages", "Site Transport", "Tea & Refreshments",
                            "Tools & Consumables", "Site Security", "Miscellaneous"]
PAYMENT_MODE_OPTIONS = ["Cash", "UPI", "Bank Transfer", "Cheque", "Other"]


def get_site_expenses_total(project_id):
    return db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxSiteExpense WHERE ProjectID=?",
                        (project_id,))["t"]


class SiteExpensePanel(ctk.CTkFrame):
    def __init__(self, master, project_id):
        super().__init__(master, fg_color="transparent")
        self.project_id = project_id
        self.selected_expense_id = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(15, 5))
        ctk.CTkLabel(header, text="Site Expenses", font=theme.FONT_HEADING, text_color=theme.INK).pack(side="left")
        ctk.CTkButton(header, text="+ Add Expense", command=self.open_add_expense, fg_color=theme.BRASS,
                     hover_color=theme.INK, font=theme.FONT_BODY_BOLD, height=28).pack(side="right")
        ctk.CTkLabel(self, text="Real, non-material site costs for this project -- labour wages, site "
                                "transport, refreshments, tools, security, and other miscellaneous spend.",
                     font=theme.FONT_SMALL, text_color=theme.MUTED).pack(anchor="w", padx=20, pady=(0, 10))

        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=20, pady=(0, 10))

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=20, pady=(0, 10))
        self.category_filter_var = ctk.StringVar(value="All Categories")
        ctk.CTkOptionMenu(toolbar, values=["All Categories"] + EXPENSE_CATEGORY_OPTIONS,
                          variable=self.category_filter_var, width=170,
                          command=lambda c: self.refresh()).pack(side="left")

        columns = ctk.CTkFrame(self, fg_color="transparent")
        columns.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        self.table_frame = ctk.CTkFrame(columns, fg_color=theme.WHITE)
        self.table_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        cols = ("date", "category", "amount", "paid_to", "mode")
        self.tree = ttk.Treeview(self.table_frame, columns=cols, show="headings", height=16)
        headings = {"date": "Date", "category": "Category", "amount": "Amount (₹)",
                    "paid_to": "Paid To", "mode": "Mode"}
        widths = {"date": 90, "category": 140, "amount": 100, "paid_to": 140, "mode": 90}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c])
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda e: self.open_edit_expense() if self.selected_expense_id else None)

        scrollbar = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True, side="left")

        details_panel = ctk.CTkFrame(columns, fg_color=theme.WHITE, corner_radius=8, width=260)
        details_panel.pack(side="left", fill="y")
        details_panel.pack_propagate(False)
        ctk.CTkLabel(details_panel, text="Expense Details", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=15, pady=(15, 10))
        self.details_label = ctk.CTkLabel(details_panel, text="Select an expense to see details.",
                                          font=theme.FONT_BODY, text_color=theme.MUTED, justify="left",
                                          wraplength=230)
        self.details_label.pack(anchor="w", padx=15, pady=(0, 10))
        ctk.CTkButton(details_panel, text="Edit Expense", command=self.open_edit_expense,
                      fg_color=theme.INK, hover_color=theme.BRASS, font=theme.FONT_SMALL, height=26).pack(
            fill="x", padx=15, pady=(0, 8))
        ctk.CTkButton(details_panel, text="Delete Expense", command=self.delete_expense,
                      fg_color="#8B2E2E", hover_color="#5E1F1F", font=theme.FONT_SMALL, height=26).pack(
            fill="x", padx=15, pady=(0, 15))

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        if hasattr(self, "_empty_state_frame"):
            self._empty_state_frame.destroy()
            del self._empty_state_frame

        category_filter = self.category_filter_var.get()
        expenses = db.fetch_all(
            "SELECT * FROM trxSiteExpense WHERE ProjectID=? ORDER BY ExpenseDate DESC, ExpenseID DESC",
            (self.project_id,))
        if category_filter != "All Categories":
            expenses = [e for e in expenses if e["Category"] == category_filter]

        self._render_stats(expenses)

        if not expenses:
            self.tree.pack_forget()
            self._empty_state_frame = ui.empty_state(
                self.table_frame, "No site expenses recorded yet.", "+ Add Expense", self.open_add_expense)
            return
        self.tree.pack(fill="both", expand=True, side="left")

        for e in expenses:
            self.tree.insert("", "end", iid=e["ExpenseID"],
                             values=(e["ExpenseDate"], e["Category"], f"{e['Amount']:,.2f}",
                                    e["PaidTo"] or "-", e["PaymentMode"] or "-"))

    def _render_stats(self, expenses):
        for w in self.stats_frame.winfo_children():
            w.destroy()
        total = sum(e["Amount"] for e in expenses)
        count = len(expenses)
        # Real top category by spend -- only shown when there's at least
        # one real expense to summarize, not a fabricated "-" placeholder.
        by_category = {}
        for e in expenses:
            by_category[e["Category"]] = by_category.get(e["Category"], 0) + e["Amount"]
        top_category = max(by_category, key=by_category.get) if by_category else None

        stats = [
            (f"₹{total:,.0f}", "Total Site Expense", None),
            (str(count), "Entries", None),
            (top_category or "-", "Top Category", f"₹{by_category[top_category]:,.0f}" if top_category else None),
        ]
        for value, label, sublabel in stats:
            ui.stat_card(self.stats_frame, value, label, sublabel).pack(side="left", padx=(0, 12))

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        expense_id = int(sel[0])
        self.selected_expense_id = expense_id
        e = db.fetch_one("SELECT * FROM trxSiteExpense WHERE ExpenseID=?", (expense_id,))
        lines = [f"Category: {e['Category']}", f"Amount: ₹{e['Amount']:,.2f}", f"Date: {e['ExpenseDate']}",
                 f"Paid To: {e['PaidTo'] or '-'}", f"Mode: {e['PaymentMode'] or '-'}"]
        if e["Notes"]:
            lines.append(f"\nNotes: {e['Notes']}")
        self.details_label.configure(text="\n".join(lines))

    def _selected_or_warn(self):
        if self.selected_expense_id is None:
            messagebox.showinfo("Select an expense", "Please select an expense from the list first.", parent=self)
            return None
        return self.selected_expense_id

    def open_add_expense(self):
        SiteExpenseForm(self, self.project_id, on_save=self.refresh)

    def open_edit_expense(self):
        expense_id = self._selected_or_warn()
        if expense_id is None:
            return
        existing = db.fetch_one("SELECT * FROM trxSiteExpense WHERE ExpenseID=?", (expense_id,))
        SiteExpenseForm(self, self.project_id, on_save=self.refresh, existing=existing)

    def delete_expense(self):
        expense_id = self._selected_or_warn()
        if expense_id is None:
            return
        if messagebox.askyesno("Delete expense?", "Delete this site expense entry? This cannot be undone.",
                               parent=self):
            db.execute("DELETE FROM trxSiteExpense WHERE ExpenseID=?", (expense_id,))
            db.log_activity("Project", self.project_id, "Site Expense Deleted", str(expense_id))
            self.selected_expense_id = None
            self.refresh()


class SiteExpenseForm(ctk.CTkToplevel):
    def __init__(self, master, project_id, on_save, existing=None):
        super().__init__(master)
        self.transient(self.master.winfo_toplevel())
        self.project_id = project_id
        self.on_save = on_save
        self.existing = existing
        self.title("Edit Site Expense" if existing else "Add Site Expense")
        self.geometry("420x480")
        self.configure(fg_color=theme.PARCHMENT)
        self.grab_set()

        ctk.CTkLabel(self, text=self.title(), font=theme.FONT_SUBHEADING, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 10))

        ctk.CTkLabel(self, text="Category", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.category_var = ctk.StringVar(value=(existing["Category"] if existing else EXPENSE_CATEGORY_OPTIONS[0]))
        ctk.CTkOptionMenu(self, values=EXPENSE_CATEGORY_OPTIONS, variable=self.category_var, width=340).pack(
            padx=20, pady=(0, 10))

        ctk.CTkLabel(self, text="Amount (₹) *", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.amount_entry = ctk.CTkEntry(self, width=340)
        apply_decimal_only(self, self.amount_entry)
        if existing:
            self.amount_entry.insert(0, str(existing["Amount"]))
        self.amount_entry.pack(padx=20, pady=(0, 10))

        ctk.CTkLabel(self, text="Expense Date", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.date_entry = DateEntry(self, width=20, date_pattern="yyyy-mm-dd", background=theme.BRASS,
                                    foreground="white", borderwidth=1, headersbackground=theme.INK,
                                    headersforeground="white", selectbackground=theme.BRASS)
        if existing and existing["ExpenseDate"]:
            try:
                self.date_entry.set_date(existing["ExpenseDate"])
            except Exception:
                pass  # malformed legacy date string -- fall back to today rather than crash
        self.date_entry.pack(anchor="w", padx=20, pady=(0, 10))

        ctk.CTkLabel(self, text="Paid To", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.paid_to_entry = ctk.CTkEntry(self, width=340, placeholder_text="e.g. site labourer name, shop, etc.")
        if existing and existing["PaidTo"]:
            self.paid_to_entry.insert(0, existing["PaidTo"])
        self.paid_to_entry.pack(padx=20, pady=(0, 10))

        ctk.CTkLabel(self, text="Payment Mode", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.mode_var = ctk.StringVar(value=(existing["PaymentMode"] if existing and existing["PaymentMode"]
                                              else PAYMENT_MODE_OPTIONS[0]))
        ctk.CTkOptionMenu(self, values=PAYMENT_MODE_OPTIONS, variable=self.mode_var, width=340).pack(
            padx=20, pady=(0, 10))

        ctk.CTkLabel(self, text="Notes", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.notes_entry = ctk.CTkEntry(self, width=340)
        if existing and existing["Notes"]:
            self.notes_entry.insert(0, existing["Notes"])
        self.notes_entry.pack(padx=20, pady=(0, 15))

        ctk.CTkButton(self, text="Save", command=self.save, fg_color=theme.BRASS,
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

        expense_date = self.date_entry.get_date().isoformat()
        paid_to = self.paid_to_entry.get().strip()
        notes = self.notes_entry.get().strip()

        if self.existing:
            db.execute(
                """UPDATE trxSiteExpense SET Category=?, Amount=?, ExpenseDate=?, PaidTo=?, PaymentMode=?,
                   Notes=?, ModifiedOn=datetime('now') WHERE ExpenseID=?""",
                (self.category_var.get(), amount, expense_date, paid_to, self.mode_var.get(), notes,
                 self.existing["ExpenseID"]))
            db.log_activity("Project", self.project_id, "Site Expense Updated", self.category_var.get())
        else:
            db.execute(
                """INSERT INTO trxSiteExpense (ProjectID, ExpenseDate, Category, Amount, PaidTo, PaymentMode, Notes)
                   VALUES (?,?,?,?,?,?,?)""",
                (self.project_id, expense_date, self.category_var.get(), amount, paid_to, self.mode_var.get(),
                 notes))
            db.log_activity("Project", self.project_id, "Site Expense Recorded",
                            f"{self.category_var.get()}: ₹{amount:,.2f}")

        self.on_save()
        self.destroy()

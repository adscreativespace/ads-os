"""
ADS OS Desktop -- BOQ / Bill of Quantities (Commercial module, second of six)
Line items grouped by Category with section subtotals, a live summary
(Total Items/Quantity/Amount, Status breakdown), and Add/Edit/Delete.

Vendor is a minimal lookup (VendorID + VendorName only) for now -- the full
Vendor module (module #4) will extend mstVendor with more fields via an
additive migration; BOQ items referencing a VendorID keep working unchanged
when that happens.
"""
import customtkinter as ctk
from tkinter import ttk, messagebox
import db
import theme
import ui_components as ui
from constants import apply_decimal_only

BOQ_STATUS_OPTIONS = ["Not Started", "Pending", "In Progress", "Completed"]
STATUS_COLORS = {
    "Not Started": "#6B6B6B", "Pending": "#B68100",
    "In Progress": "#1E5FA8", "Completed": "#2E8B57",
}


class BOQPanel(ctk.CTkFrame):
    def __init__(self, master, project_id):
        super().__init__(master, fg_color="transparent")
        self.project_id = project_id
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        ctk.CTkLabel(self, text="BOQ (Bill of Quantities)", font=theme.FONT_HEADING, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 5))
        ctk.CTkLabel(self, text="Create, manage, and track the bill of quantities for this project.",
                     font=theme.FONT_SMALL, text_color=theme.MUTED).pack(anchor="w", padx=20, pady=(0, 10))

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkButton(toolbar, text="+ Add Item", command=self.open_add_item,
                      fg_color=theme.BRASS, hover_color=theme.INK, font=theme.FONT_SMALL, height=28).pack(side="right")
        self.search_entry = ctk.CTkEntry(toolbar, placeholder_text="Search item code or description...", width=280)
        self.search_entry.pack(side="left")
        self.search_entry.bind("<KeyRelease>", lambda e: self.refresh())

        self.status_filter_var = ctk.StringVar(value="All Status")
        self.status_filter_menu = ctk.CTkOptionMenu(toolbar, values=["All Status"] + BOQ_STATUS_OPTIONS,
                                                     variable=self.status_filter_var, width=140,
                                                     command=lambda c: self.refresh())
        self.status_filter_menu.pack(side="left", padx=(10, 0))

        columns = ctk.CTkFrame(self, fg_color="transparent")
        columns.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        self.table_frame = ctk.CTkFrame(columns, fg_color=theme.WHITE)
        self.table_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        cols = ("code", "desc", "unit", "qty", "rate", "amount", "vendor", "status")
        self.tree = ttk.Treeview(self.table_frame, columns=cols, show="tree headings", height=20)
        self.tree.heading("#0", text="Category / Item")
        self.tree.column("#0", width=90)
        headings = {"code": "Item Code", "desc": "Description", "unit": "Unit", "qty": "Qty",
                    "rate": "Rate (₹)", "amount": "Amount (₹)", "vendor": "Vendor", "status": "Status"}
        widths = {"code": 80, "desc": 200, "unit": 60, "qty": 70, "rate": 80, "amount": 100, "vendor": 110, "status": 90}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c])
        self.tree.tag_configure("section", background=theme.PARCHMENT, font=theme.FONT_BODY_BOLD)
        for status, color in STATUS_COLORS.items():
            self.tree.tag_configure(f"status_{status}", foreground=color)
        self.tree.bind("<Double-1>", lambda e: self.open_edit_item())

        # Horizontal scrollbar packed BEFORE the tree claims fill="both" --
        # otherwise the tree greedily takes all remaining space (including
        # the bottom strip) and there's nothing left for a horizontal
        # scrollbar to occupy. 8 columns is genuinely wide enough to
        # overflow a non-maximized window; this was previously unreachable
        # without resizing the window itself.
        hscrollbar = ttk.Scrollbar(self.table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscroll=hscrollbar.set)
        hscrollbar.pack(side="bottom", fill="x")

        scrollbar = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self.tree.pack(fill="both", expand=True, side="left")

        # ---------------- Right: BOQ Summary ----------------
        summary_panel = ctk.CTkFrame(columns, fg_color=theme.WHITE, corner_radius=8, width=260)
        summary_panel.pack(side="left", fill="y")
        summary_panel.pack_propagate(False)

        ctk.CTkLabel(summary_panel, text="BOQ Summary", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=15, pady=(15, 10))
        self.summary_label = ctk.CTkLabel(summary_panel, text="", font=theme.FONT_BODY, text_color=theme.INK,
                                          justify="left")
        self.summary_label.pack(anchor="w", padx=15, pady=(0, 15))

        ctk.CTkLabel(summary_panel, text="Status Overview", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=15, pady=(0, 10))
        self.status_label = ctk.CTkLabel(summary_panel, text="", font=theme.FONT_SMALL, text_color=theme.INK,
                                         justify="left")
        self.status_label.pack(anchor="w", padx=15, pady=(0, 15))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 15))
        ctk.CTkButton(footer, text="Edit Item", command=self.open_edit_item,
                      fg_color=theme.INK, font=theme.FONT_SMALL, height=26).pack(side="left", padx=(0, 8))
        ctk.CTkButton(footer, text="Delete Item", command=self.delete_item,
                      fg_color="#8B2E2E", hover_color="#5E1F1F", font=theme.FONT_SMALL, height=26).pack(side="left")

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        if hasattr(self, "_empty_state_frame"):
            self._empty_state_frame.destroy()
            del self._empty_state_frame

        search = self.search_entry.get().strip().lower()
        status_filter = self.status_filter_var.get()

        items = db.fetch_all("""
            SELECT b.*, v.VendorName FROM trxBOQItem b
            LEFT JOIN mstVendor v ON b.VendorID = v.VendorID
            WHERE b.ProjectID=? ORDER BY b.Category, b.ItemOrder, b.BOQItemID
        """, (self.project_id,))

        if search:
            items = [i for i in items if search in (i["ItemCode"] or "").lower()
                    or search in i["Description"].lower()]
        if status_filter != "All Status":
            items = [i for i in items if i["Status"] == status_filter]

        if not items:
            self.tree.pack_forget()
            self._empty_state_frame = ui.empty_state(
                self.table_frame, "No BOQ items yet.", "+ Add Item", self.open_add_item)
        else:
            self.tree.pack(fill="both", expand=True, side="left")

        categories = []
        by_category = {}
        for item in items:
            cat = item["Category"] or "Uncategorized"
            if cat not in by_category:
                by_category[cat] = []
                categories.append(cat)
            by_category[cat].append(item)

        total_amount = 0
        total_qty = 0
        status_counts = {s: 0 for s in BOQ_STATUS_OPTIONS}

        for cat in categories:
            cat_items = by_category[cat]
            cat_total = sum(i["Amount"] for i in cat_items)
            section_id = self.tree.insert("", "end", text=cat, values=("", "", "", "", "", f"{cat_total:,.2f}", "", ""),
                                          tags=("section",), open=True)
            for item in cat_items:
                vendor_name = item["VendorName"] or "-"
                self.tree.insert(section_id, "end", iid=item["BOQItemID"],
                                 values=(item["ItemCode"] or "-", item["Description"], item["Unit"] or "-",
                                        f"{item['Quantity']:.2f}", f"{item['Rate']:,.2f}", f"{item['Amount']:,.2f}",
                                        vendor_name, item["Status"]),
                                 tags=(f"status_{item['Status']}",))
                total_amount += item["Amount"]
                total_qty += item["Quantity"]
                status_counts[item["Status"]] = status_counts.get(item["Status"], 0) + 1

        total_items = len(items)
        self.summary_label.configure(
            text=f"Total Items: {total_items}\nTotal Quantity: {total_qty:,.2f}\nTotal Amount: ₹{total_amount:,.2f}"
        )
        status_lines = []
        for status in BOQ_STATUS_OPTIONS:
            count = status_counts.get(status, 0)
            pct = int(round(count / total_items * 100)) if total_items else 0
            status_lines.append(f"{status}: {count} ({pct}%)")
        self.status_label.configure(text="\n".join(status_lines))

    def _selected_item_id(self):
        sel = self.tree.selection()
        if not sel or not str(sel[0]).isdigit():
            messagebox.showinfo("Select an item", "Please select a BOQ line item (not a category header).", parent=self)
            return None
        return int(sel[0])

    def open_add_item(self):
        BOQItemForm(self, self.project_id, on_save=self.refresh)

    def open_edit_item(self):
        item_id = self._selected_item_id()
        if item_id is None:
            return
        item = db.fetch_one("SELECT * FROM trxBOQItem WHERE BOQItemID=?", (item_id,))
        BOQItemForm(self, self.project_id, on_save=self.refresh, existing=item)

    def delete_item(self):
        item_id = self._selected_item_id()
        if item_id is None:
            return
        if messagebox.askyesno("Confirm delete", "Delete this BOQ item permanently?", parent=self):
            db.execute("DELETE FROM trxBOQItem WHERE BOQItemID=?", (item_id,))
            db.log_activity("Project", self.project_id, "BOQ Item Deleted", str(item_id))
            self.refresh()


class BOQItemForm(ctk.CTkToplevel):
    def __init__(self, master, project_id, on_save, existing=None):
        super().__init__(master)
        self.project_id = project_id
        self.on_save = on_save
        self.existing = existing
        self.title("Edit BOQ Item" if existing else "Add BOQ Item")
        self.geometry("460x560")
        self.configure(fg_color=theme.PARCHMENT)
        self.transient(self.master.winfo_toplevel())  # anchor to the real top-level window -- these dialogs are opened many levels deep inside ProjectWorkspace/CTkTabview, unlike ClientForm/ProjectForm which are shallow
        self.grab_set()

        self.vendors = db.fetch_all("SELECT VendorID, VendorName FROM mstVendor WHERE Active=1 ORDER BY VendorName")
        existing_categories = db.fetch_all(
            "SELECT DISTINCT Category FROM trxBOQItem WHERE ProjectID=? ORDER BY Category", (project_id,))
        category_values = [c["Category"] for c in existing_categories] or ["Uncategorized"]
        self.materials = db.fetch_all(
            "SELECT * FROM mstMaterial WHERE ProjectID=? AND Active=1 ORDER BY MaterialName", (project_id,))

        row = 0
        ctk.CTkLabel(self, text=self.title(), font=theme.FONT_SUBHEADING, text_color=theme.INK).grid(
            row=row, column=0, columnspan=2, padx=15, pady=(15, 10), sticky="w")
        row += 1

        # Real fix for real user feedback: link to an existing Material
        # instead of retyping Item Code/Description/Vendor/Rate -- this was
        # a genuine duplication problem (Material Code and Item Code were
        # two separate, disconnected pieces of data for the same thing).
        if self.materials:
            ctk.CTkLabel(self, text="Link to Material (optional)", font=theme.FONT_BODY, text_color=theme.INK).grid(
                row=row, column=0, sticky="w", padx=15, pady=8)
            material_names = ["-- Enter Manually --"] + [m["MaterialName"] for m in self.materials]
            default_material = "-- Enter Manually --"
            if existing and existing["MaterialID"]:
                match = next((m["MaterialName"] for m in self.materials if m["MaterialID"] == existing["MaterialID"]), None)
                if match:
                    default_material = match
            self.material_var = ctk.StringVar(value=default_material)
            ctk.CTkOptionMenu(self, values=material_names, variable=self.material_var, width=250,
                              command=self._on_material_link).grid(row=row, column=1, padx=15, pady=8)
            row += 1
        else:
            self.material_var = None

        ctk.CTkLabel(self, text="Item Code", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.code_entry = ctk.CTkEntry(self, width=250)
        if existing and existing["ItemCode"]:
            self.code_entry.insert(0, existing["ItemCode"])
        self.code_entry.grid(row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self, text="Description *", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.desc_entry = ctk.CTkEntry(self, width=250)
        if existing:
            self.desc_entry.insert(0, existing["Description"])
        self.desc_entry.grid(row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self, text="Category *", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.category_var = ctk.StringVar(value=(existing["Category"] if existing else category_values[0]))
        self.category_combo = ctk.CTkComboBox(self, values=category_values, variable=self.category_var, width=250)
        self.category_combo.grid(row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self, text="Unit", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.unit_entry = ctk.CTkEntry(self, width=250, placeholder_text="e.g. Sq.ft, Cum, Nos")
        if existing and existing["Unit"]:
            self.unit_entry.insert(0, existing["Unit"])
        self.unit_entry.grid(row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self, text="Quantity *", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.qty_entry = ctk.CTkEntry(self, width=250)
        apply_decimal_only(self, self.qty_entry)
        self.qty_entry.insert(0, str(existing["Quantity"]) if existing else "0")
        self.qty_entry.grid(row=row, column=1, padx=15, pady=8)
        self.qty_entry.bind("<KeyRelease>", self._recalc_amount)
        row += 1

        ctk.CTkLabel(self, text="Rate (₹) *", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.rate_entry = ctk.CTkEntry(self, width=250)
        apply_decimal_only(self, self.rate_entry)
        self.rate_entry.insert(0, str(existing["Rate"]) if existing else "0")
        self.rate_entry.grid(row=row, column=1, padx=15, pady=8)
        self.rate_entry.bind("<KeyRelease>", self._recalc_amount)
        row += 1

        ctk.CTkLabel(self, text="Amount (₹)", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.amount_label = ctk.CTkLabel(self, text="₹0.00", font=theme.FONT_BODY_BOLD, text_color=theme.BRASS)
        self.amount_label.grid(row=row, column=1, sticky="w", padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self, text="Vendor", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        vendor_names = ["-- None --"] + [v["VendorName"] for v in self.vendors]
        default_vendor = "-- None --"
        if existing and existing["VendorID"]:
            match = next((v["VendorName"] for v in self.vendors if v["VendorID"] == existing["VendorID"]), None)
            if match:
                default_vendor = match
        self.vendor_var = ctk.StringVar(value=default_vendor)
        self.vendor_combo = ctk.CTkComboBox(self, values=vendor_names, variable=self.vendor_var, width=250)
        self.vendor_combo.grid(row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self, text="Status", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.status_var = ctk.StringVar(value=(existing["Status"] if existing else "Not Started"))
        ctk.CTkOptionMenu(self, values=BOQ_STATUS_OPTIONS, variable=self.status_var, width=250).grid(
            row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkButton(self, text="Save", command=self.save, fg_color=theme.BRASS,
                      hover_color=theme.INK, font=theme.FONT_BODY_BOLD).grid(
            row=row, column=0, columnspan=2, pady=20)

        self._recalc_amount()

    def _on_material_link(self, choice):
        if choice == "-- Enter Manually --":
            return
        material = next((m for m in self.materials if m["MaterialName"] == choice), None)
        if not material:
            return
        # Auto-fills from the Material -- fields stay editable afterward,
        # since a BOQ rate sometimes differs from raw material cost (labor,
        # markup), this is a convenience, not a lock.
        self.desc_entry.delete(0, "end")
        self.desc_entry.insert(0, material["MaterialName"])
        if material["Category"]:
            self.category_var.set(material["Category"])
        if material["Unit"]:
            self.unit_entry.delete(0, "end")
            self.unit_entry.insert(0, material["Unit"])
        self.rate_entry.delete(0, "end")
        self.rate_entry.insert(0, str(material["UnitCost"]))
        if material["VendorID"]:
            vendor_match = next((v["VendorName"] for v in self.vendors if v["VendorID"] == material["VendorID"]), None)
            if vendor_match:
                self.vendor_var.set(vendor_match)
        self._recalc_amount()

    def _recalc_amount(self, _event=None):
        try:
            qty = float(self.qty_entry.get().strip() or 0)
            rate = float(self.rate_entry.get().strip() or 0)
            self.amount_label.configure(text=f"₹{qty * rate:,.2f}")
        except ValueError:
            self.amount_label.configure(text="₹0.00")

    def save(self):
        description = self.desc_entry.get().strip()
        category = self.category_var.get().strip()
        if not description or not category:
            messagebox.showerror("Missing fields", "Description and Category are required.", parent=self)
            return
        try:
            qty = float(self.qty_entry.get().strip() or 0)
            rate = float(self.rate_entry.get().strip() or 0)
        except ValueError:
            messagebox.showerror("Invalid number", "Quantity and Rate must be numbers.", parent=self)
            return
        amount = qty * rate

        vendor_name = self.vendor_var.get()
        vendor_id = None
        if vendor_name != "-- None --":
            existing_vendor = next((v for v in self.vendors if v["VendorName"] == vendor_name), None)
            if existing_vendor:
                vendor_id = existing_vendor["VendorID"]
            else:
                vendor_id = db.execute("INSERT INTO mstVendor (VendorName) VALUES (?)", (vendor_name,))

        item_code = self.code_entry.get().strip()
        unit = self.unit_entry.get().strip()

        material_id = None
        if self.material_var and self.material_var.get() != "-- Enter Manually --":
            match = next((m for m in self.materials if m["MaterialName"] == self.material_var.get()), None)
            material_id = match["MaterialID"] if match else None

        if self.existing:
            db.execute(
                """UPDATE trxBOQItem SET ItemCode=?, Description=?, Category=?, Unit=?, Quantity=?, Rate=?,
                   Amount=?, VendorID=?, Status=?, MaterialID=?, ModifiedOn=datetime('now') WHERE BOQItemID=?""",
                (item_code, description, category, unit, qty, rate, amount, vendor_id,
                 self.status_var.get(), material_id, self.existing["BOQItemID"])
            )
            db.log_activity("Project", self.project_id, "BOQ Item Updated", description)
        else:
            new_id = db.execute(
                """INSERT INTO trxBOQItem (ProjectID, ItemCode, Description, Category, Unit, Quantity, Rate,
                   Amount, VendorID, Status, MaterialID) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (self.project_id, item_code, description, category, unit, qty, rate, amount, vendor_id,
                 self.status_var.get(), material_id)
            )
            db.log_activity("Project", self.project_id, "BOQ Item Added", description)

        self.on_save()
        self.destroy()

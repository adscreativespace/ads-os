"""
ADS OS Desktop -- Materials (Commercial module, third of six)
Materials master list with stock tracking, unit cost, and auto-derived
stock status (In Stock / Low Stock / Out of Stock based on Reorder Level).
'Add Purchase' logs a simple stock-in transaction and bumps CurrentStock --
this is intentionally NOT the full Purchase Order -> Goods Receipt pipeline
from the reference mockup; that's a separate, larger procurement workflow.
"""
import customtkinter as ctk
from tkinter import ttk, messagebox
import datetime
import db
import theme
import ui_components as ui
from constants import apply_decimal_only
import landed_cost

STOCK_STATUS_COLORS = {"In Stock": "#2E8B57", "Low Stock": "#B68100", "Out of Stock": "#8B2E2E"}
# Deliberately a separate list from Vendor's PRODUCT_CATEGORY_OPTIONS
# (vendors_panel.py) -- what a Vendor supplies and what a Material actually
# IS are different classifications, even though some names overlap.
MATERIAL_CATEGORY_OPTIONS = ["Cement", "Steel", "Sand", "Aggregate", "Brick", "AAC Block", "Electrical",
                             "Plumbing", "Hardware", "Chemical", "Paint", "Wood", "Plywood", "Laminate",
                             "PVC", "Glass", "Miscellaneous"]


def stock_status(current_stock, reorder_level):
    if current_stock <= 0:
        return "Out of Stock"
    if current_stock <= reorder_level:
        return "Low Stock"
    return "In Stock"


class MaterialsPanel(ctk.CTkFrame):
    def __init__(self, master, project_id):
        super().__init__(master, fg_color="transparent")
        self.project_id = project_id
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        ctk.CTkLabel(self, text="Materials", font=theme.FONT_HEADING, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 5))
        ctk.CTkLabel(self, text="Track, manage, and monitor material purchases and inventory for this project.",
                     font=theme.FONT_SMALL, text_color=theme.MUTED).pack(anchor="w", padx=20, pady=(0, 10))

        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=20, pady=(0, 10))

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkButton(toolbar, text="+ New Material", command=self.open_add_material,
                      fg_color=theme.BRASS, hover_color=theme.INK, font=theme.FONT_SMALL, height=28).pack(side="right")
        ctk.CTkButton(toolbar, text="+ New Purchase", command=self.open_new_purchase,
                      fg_color=theme.INK, hover_color=theme.BRASS, font=theme.FONT_SMALL, height=28).pack(side="right", padx=(0, 8))
        self.search_entry = ctk.CTkEntry(toolbar, placeholder_text="Search material name, code, brand...", width=280)
        self.search_entry.pack(side="left")
        self.search_entry.bind("<KeyRelease>", lambda e: self.refresh())

        self.status_filter_var = ctk.StringVar(value="All Status")
        ctk.CTkOptionMenu(toolbar, values=["All Status", "In Stock", "Low Stock", "Out of Stock"],
                          variable=self.status_filter_var, width=140,
                          command=lambda c: self.refresh()).pack(side="left", padx=(10, 0))

        self.table_frame = ctk.CTkFrame(self, fg_color=theme.WHITE)
        self.table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        cols = ("code", "name", "category", "brand", "vendor", "unit", "stock", "cost", "value", "location", "status")
        self.tree = ttk.Treeview(self.table_frame, columns=cols, show="headings", height=14)
        headings = {"code": "Material Code", "name": "Material Name", "category": "Category", "brand": "Brand",
                    "vendor": "Vendor", "unit": "Unit", "stock": "In Stock", "cost": "Unit Cost (₹)",
                    "value": "Stock Value (₹)", "location": "Storage Location", "status": "Status"}
        widths = {"code": 90, "name": 150, "category": 85, "brand": 80, "vendor": 110, "unit": 55, "stock": 70,
                  "cost": 85, "value": 95, "location": 100, "status": 85}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c])
        for status, color in STOCK_STATUS_COLORS.items():
            self.tree.tag_configure(f"status_{status}", foreground=color)
        self.tree.bind("<Double-1>", lambda e: self.open_edit_material())

        # Horizontal scrollbar packed BEFORE the tree claims fill="both" --
        # 11 columns is genuinely wide enough to overflow a non-maximized
        # window.
        hscrollbar = ttk.Scrollbar(self.table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscroll=hscrollbar.set)
        hscrollbar.pack(side="bottom", fill="x")

        scrollbar = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self.tree.pack(fill="both", expand=True, side="left")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 15))
        ctk.CTkButton(footer, text="Edit Material", command=self.open_edit_material,
                      fg_color=theme.INK, font=theme.FONT_SMALL, height=26).pack(side="left", padx=(0, 8))
        ctk.CTkButton(footer, text="Quick Restock Selected", command=self.open_quick_restock,
                      fg_color=theme.BRASS, hover_color=theme.INK, font=theme.FONT_SMALL, height=26).pack(
            side="left", padx=(0, 8))
        ctk.CTkButton(footer, text="Delete Material", command=self.delete_material,
                      fg_color="#8B2E2E", hover_color="#5E1F1F", font=theme.FONT_SMALL, height=26).pack(side="left")

    def open_quick_restock(self):
        material_id = self._selected_material_id()
        if material_id is None:
            return
        material = db.fetch_one("SELECT * FROM mstMaterial WHERE MaterialID=?", (material_id,))
        AddPurchaseDialog(self, material, on_save=self.refresh)

    def refresh(self):
        self._render_stats()
        for row in self.tree.get_children():
            self.tree.delete(row)
        if hasattr(self, "_empty_state_frame"):
            self._empty_state_frame.destroy()
            del self._empty_state_frame

        search = self.search_entry.get().strip().lower()
        status_filter = self.status_filter_var.get()

        materials = db.fetch_all("""
            SELECT m.*, v.VendorName FROM mstMaterial m
            LEFT JOIN mstVendor v ON m.VendorID = v.VendorID
            WHERE m.ProjectID=? AND m.Active=1 ORDER BY m.MaterialName
        """, (self.project_id,))

        if search:
            materials = [m for m in materials if search in m["MaterialName"].lower()
                        or search in (m["MaterialCode"] or "").lower()
                        or search in (m["Brand"] or "").lower()]
        if status_filter != "All Status":
            materials = [m for m in materials if stock_status(m["CurrentStock"], m["ReorderLevel"]) == status_filter]

        if not materials:
            self.tree.pack_forget()
            self._empty_state_frame = ui.empty_state(
                self.table_frame, "No materials yet.", "+ Add Material", self.open_add_material)
            return
        self.tree.pack(fill="both", expand=True, side="left")

        for m in materials:
            status = stock_status(m["CurrentStock"], m["ReorderLevel"])
            stock_value = m["CurrentStock"] * m["UnitCost"]
            self.tree.insert("", "end", iid=m["MaterialID"],
                             values=(m["MaterialCode"] or "-", m["MaterialName"], m["Category"], m["Brand"] or "-",
                                    m["VendorName"] or "-", m["Unit"] or "-", f"{m['CurrentStock']:.2f}",
                                    f"{m['UnitCost']:,.2f}", f"{stock_value:,.2f}", m["Location"] or "-", status),
                             tags=(f"status_{status}",))

    def _render_stats(self):
        for w in self.stats_frame.winfo_children():
            w.destroy()
        all_materials = db.fetch_all("SELECT * FROM mstMaterial WHERE ProjectID=? AND Active=1", (self.project_id,))
        total_materials = len(all_materials)
        total_value = sum(m["CurrentStock"] * m["UnitCost"] for m in all_materials)
        low_stock_count = sum(1 for m in all_materials if stock_status(m["CurrentStock"], m["ReorderLevel"]) == "Low Stock")
        out_of_stock_count = sum(1 for m in all_materials if stock_status(m["CurrentStock"], m["ReorderLevel"]) == "Out of Stock")

        stats = [
            ("Total Materials", str(total_materials)),
            ("Total Stock Value", f"₹{total_value:,.2f}"),
            ("Low Stock Items", str(low_stock_count)),
            ("Out of Stock", str(out_of_stock_count)),
        ]
        for label, value in stats:
            card = ctk.CTkFrame(self.stats_frame, fg_color=theme.WHITE, corner_radius=8, width=170, height=70)
            card.pack(side="left", padx=(0, 12))
            card.pack_propagate(False)
            ctk.CTkLabel(card, text=value, font=theme.FONT_SUBHEADING, text_color=theme.BRASS).pack(pady=(10, 0))
            ctk.CTkLabel(card, text=label, font=theme.FONT_SMALL, text_color=theme.MUTED).pack()

    def _selected_material_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select a material", "Please select a material from the list first.", parent=self)
            return None
        return int(sel[0])

    def open_add_material(self):
        MaterialForm(self, self.project_id, on_save=self.refresh)

    def open_edit_material(self):
        material_id = self._selected_material_id()
        if material_id is None:
            return
        material = db.fetch_one("SELECT * FROM mstMaterial WHERE MaterialID=?", (material_id,))
        MaterialForm(self, self.project_id, on_save=self.refresh, existing=material)

    def open_new_purchase(self):
        NewPurchaseDialog(self, self.project_id, on_save=self.refresh)

    def delete_material(self):
        material_id = self._selected_material_id()
        if material_id is None:
            return
        if messagebox.askyesno("Confirm delete", "Delete this material permanently?", parent=self):
            db.execute("DELETE FROM mstMaterial WHERE MaterialID=?", (material_id,))
            db.log_activity("Project", self.project_id, "Material Deleted", str(material_id))
            self.refresh()


class MaterialForm(ctk.CTkToplevel):
    def __init__(self, master, project_id, on_save, existing=None):
        super().__init__(master)
        self.project_id = project_id
        self.on_save = on_save
        self.existing = existing
        self.title("Edit Material" if existing else "New Material")
        self.geometry("460x620")
        self.configure(fg_color=theme.PARCHMENT)
        self.transient(self.master.winfo_toplevel())  # anchor to the real top-level window -- these dialogs are opened many levels deep inside ProjectWorkspace/CTkTabview, unlike ClientForm/ProjectForm which are shallow
        self.grab_set()

        self.vendors = db.fetch_all("SELECT VendorID, VendorName FROM mstVendor WHERE Active=1 ORDER BY VendorName")
        existing_categories = [c["Category"] for c in db.fetch_all(
            "SELECT DISTINCT Category FROM mstMaterial WHERE ProjectID=? AND Category IS NOT NULL ORDER BY Category",
            (project_id,)) if c["Category"] not in MATERIAL_CATEGORY_OPTIONS]
        # Real project-entered categories not already in the seed list, then
        # the seed list -- avoids duplicates while giving a first-time user a
        # genuinely useful list instead of only "Uncategorized".
        category_values = existing_categories + MATERIAL_CATEGORY_OPTIONS

        row = 0
        ctk.CTkLabel(self, text=self.title(), font=theme.FONT_SUBHEADING, text_color=theme.INK).grid(
            row=row, column=0, columnspan=2, padx=15, pady=(15, 10), sticky="w")
        row += 1

        fields = [
            ("Material Name *", "name_entry", existing["MaterialName"] if existing else "", None),
            ("Material Code", "code_entry", existing["MaterialCode"] if existing and existing["MaterialCode"] else "", "auto-generated if left blank"),
            ("Brand", "brand_entry", existing["Brand"] if existing and existing["Brand"] else "", None),
            ("Unit", "unit_entry", existing["Unit"] if existing and existing["Unit"] else "", "e.g. Bag, Kg, Pcs, Sheet"),
            ("Storage Location", "location_entry", existing["Location"] if existing and existing["Location"] else "",
             "e.g. Site Store, Warehouse, First Floor"),
        ]
        self.entries = {}
        for label, key, default, placeholder in fields:
            ctk.CTkLabel(self, text=label, font=theme.FONT_BODY, text_color=theme.INK).grid(
                row=row, column=0, sticky="w", padx=15, pady=8)
            entry = ctk.CTkEntry(self, width=250, placeholder_text=placeholder)
            entry.insert(0, default)
            entry.grid(row=row, column=1, padx=15, pady=8)
            self.entries[key] = entry
            row += 1

        ctk.CTkLabel(self, text="Material Category *", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.category_var = ctk.StringVar(value=(existing["Category"] if existing else category_values[0]))
        ctk.CTkComboBox(self, values=category_values, variable=self.category_var, width=250).grid(
            row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self, text="Unit Cost (₹) *", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.cost_entry = ctk.CTkEntry(self, width=250)
        apply_decimal_only(self, self.cost_entry)
        self.cost_entry.insert(0, str(existing["UnitCost"]) if existing else "0")
        self.cost_entry.grid(row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self, text="Current Stock", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.stock_entry = ctk.CTkEntry(self, width=250)
        apply_decimal_only(self, self.stock_entry)
        self.stock_entry.insert(0, str(existing["CurrentStock"]) if existing else "0")
        self.stock_entry.grid(row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkLabel(self, text="Reorder Level", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=8)
        self.reorder_entry = ctk.CTkEntry(self, width=250)
        apply_decimal_only(self, self.reorder_entry)
        self.reorder_entry.insert(0, str(existing["ReorderLevel"]) if existing else "0")
        self.reorder_entry.grid(row=row, column=1, padx=15, pady=8)
        row += 1
        ctk.CTkLabel(self, text="Below this stock level, the material shows as 'Low Stock'.",
                     font=theme.FONT_SMALL, text_color=theme.MUTED, wraplength=380, justify="left").grid(
            row=row, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 6))
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
        ctk.CTkComboBox(self, values=vendor_names, variable=self.vendor_var, width=250).grid(
            row=row, column=1, padx=15, pady=8)
        row += 1

        ctk.CTkButton(self, text="Save", command=self.save, fg_color=theme.BRASS,
                      hover_color=theme.INK, font=theme.FONT_BODY_BOLD).grid(
            row=row, column=0, columnspan=2, pady=20)

    def save(self):
        name = self.entries["name_entry"].get().strip()
        category = self.category_var.get().strip()
        if not name or not category:
            messagebox.showerror("Missing fields", "Material Name and Category are required.", parent=self)
            return
        try:
            unit_cost = float(self.cost_entry.get().strip() or 0)
            current_stock = float(self.stock_entry.get().strip() or 0)
            reorder_level = float(self.reorder_entry.get().strip() or 0)
        except ValueError:
            messagebox.showerror("Invalid number", "Unit Cost, Current Stock, and Reorder Level must be numbers.", parent=self)
            return

        vendor_name = self.vendor_var.get()
        vendor_id = None
        if vendor_name != "-- None --":
            existing_vendor = next((v for v in self.vendors if v["VendorName"] == vendor_name), None)
            vendor_id = existing_vendor["VendorID"] if existing_vendor else \
                db.execute("INSERT INTO mstVendor (VendorName) VALUES (?)", (vendor_name,))

        code = self.entries["code_entry"].get().strip() or None
        brand = self.entries["brand_entry"].get().strip()
        unit = self.entries["unit_entry"].get().strip()
        location = self.entries["location_entry"].get().strip()

        try:
            if self.existing:
                db.execute(
                    """UPDATE mstMaterial SET MaterialCode=?, MaterialName=?, Category=?, Brand=?, Unit=?,
                       UnitCost=?, CurrentStock=?, ReorderLevel=?, Location=?, VendorID=?, ModifiedOn=datetime('now')
                       WHERE MaterialID=?""",
                    (code, name, category, brand, unit, unit_cost, current_stock, reorder_level, location,
                     vendor_id, self.existing["MaterialID"])
                )
                db.log_activity("Project", self.project_id, "Material Updated", name)
            else:
                if not code:
                    code = db.next_code("MTL", "mstMaterial", "MaterialCode")
                new_id = db.execute(
                    """INSERT INTO mstMaterial (ProjectID, MaterialCode, MaterialName, Category, Brand, Unit,
                       UnitCost, CurrentStock, ReorderLevel, Location, VendorID)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (self.project_id, code, name, category, brand, unit, unit_cost, current_stock,
                     reorder_level, location, vendor_id)
                )
                db.log_activity("Project", self.project_id, "Material Added", name)
        except Exception as e:
            messagebox.showerror("Save failed", f"Could not save this material (code may already be in use):\n{e}", parent=self)
            return

        self.on_save()
        self.destroy()


class AddPurchaseDialog(ctk.CTkToplevel):
    """Simple stock-in: records a purchase and increases CurrentStock. Not the
    full Purchase Order -> Goods Receipt workflow -- that's a separate,
    larger feature for later."""
    def __init__(self, master, material, on_save):
        super().__init__(master)
        self.material = material
        self.on_save = on_save
        self.title(f"Add Purchase — {material['MaterialName']}")
        self.geometry("380x320")
        self.configure(fg_color=theme.PARCHMENT)
        self.transient(self.master.winfo_toplevel())  # anchor to the real top-level window -- these dialogs are opened many levels deep inside ProjectWorkspace/CTkTabview, unlike ClientForm/ProjectForm which are shallow
        self.grab_set()

        ctk.CTkLabel(self, text=f"Add Purchase", font=theme.FONT_SUBHEADING, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 5))
        ctk.CTkLabel(self, text=f"{material['MaterialName']} -- current stock: {material['CurrentStock']:.2f} {material['Unit'] or ''}",
                     font=theme.FONT_SMALL, text_color=theme.MUTED).pack(anchor="w", padx=20, pady=(0, 15))

        ctk.CTkLabel(self, text="Quantity Purchased *", font=theme.FONT_BODY, text_color=theme.INK).pack(
            anchor="w", padx=20)
        self.qty_entry = ctk.CTkEntry(self, width=250)
        apply_decimal_only(self, self.qty_entry)
        self.qty_entry.pack(padx=20, pady=(0, 10))

        ctk.CTkLabel(self, text="Unit Cost (₹)", font=theme.FONT_BODY, text_color=theme.INK).pack(
            anchor="w", padx=20)
        self.cost_entry = ctk.CTkEntry(self, width=250)
        apply_decimal_only(self, self.cost_entry)
        self.cost_entry.insert(0, str(material["UnitCost"]))
        self.cost_entry.pack(padx=20, pady=(0, 10))

        ctk.CTkLabel(self, text="Notes", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        self.notes_entry = ctk.CTkEntry(self, width=250)
        self.notes_entry.pack(padx=20, pady=(0, 15))

        ctk.CTkButton(self, text="Save Purchase", command=self.save, fg_color=theme.BRASS,
                      hover_color=theme.INK, font=theme.FONT_BODY_BOLD).pack(pady=10)

    def save(self):
        try:
            qty = float(self.qty_entry.get().strip() or 0)
            cost = float(self.cost_entry.get().strip() or 0)
        except ValueError:
            messagebox.showerror("Invalid number", "Quantity and Unit Cost must be numbers.", parent=self)
            return
        if qty <= 0:
            messagebox.showerror("Invalid quantity", "Quantity Purchased must be greater than zero.", parent=self)
            return

        total_cost = qty * cost
        db.execute(
            "INSERT INTO trxMaterialPurchase (MaterialID, Quantity, UnitCost, TotalCost, Notes) VALUES (?,?,?,?,?)",
            (self.material["MaterialID"], qty, cost, total_cost, self.notes_entry.get().strip())
        )
        db.execute(
            "UPDATE mstMaterial SET CurrentStock = CurrentStock + ?, UnitCost=?, ModifiedOn=datetime('now') WHERE MaterialID=?",
            (qty, cost, self.material["MaterialID"])
        )
        db.log_activity("Project", self.material["ProjectID"], "Material Purchase Recorded",
                        f"{self.material['MaterialName']}: +{qty}")
        messagebox.showinfo("Purchase recorded", f"Stock updated: +{qty} {self.material['Unit'] or ''}", parent=self)
        self.on_save()
        self.destroy()


class NewPurchaseDialog(ctk.CTkToplevel):
    """
    Real procurement workflow: start from a Vendor and a bill, add line
    items by NAME. For each item, if a material with that name already
    exists on this project, its stock is increased; if not, a new material
    is created automatically. No pre-existing Material selection required --
    this directly replaces the old "select a Material first" flow that
    didn't match how a real purchase bill actually works.
    """
    def __init__(self, master, project_id, on_save):
        super().__init__(master)
        self.transient(self.master.winfo_toplevel())
        self.project_id = project_id
        self.on_save = on_save
        self.line_items = []  # list of dicts: {name, quantity, unit_cost, unit}

        self.title("New Purchase")
        self.geometry("560x800")
        self.configure(fg_color=theme.PARCHMENT)
        self.grab_set()

        self.vendors = db.fetch_all("SELECT VendorID, VendorName FROM mstVendor WHERE Active=1 ORDER BY VendorName")
        self.existing_materials = db.fetch_all(
            "SELECT MaterialName, Unit FROM mstMaterial WHERE ProjectID=? ORDER BY MaterialName", (project_id,))
        material_names = [m["MaterialName"] for m in self.existing_materials]

        ctk.CTkLabel(self, text="New Purchase", font=theme.FONT_SUBHEADING, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 10))

        header_row = ctk.CTkFrame(self, fg_color="transparent")
        header_row.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(header_row, text="Vendor *", font=theme.FONT_SMALL, text_color=theme.MUTED).grid(row=0, column=0, sticky="w")
        vendor_names = ["-- Select Vendor --"] + [v["VendorName"] for v in self.vendors]
        self.vendor_var = ctk.StringVar(value=vendor_names[0])
        ctk.CTkComboBox(header_row, values=vendor_names, variable=self.vendor_var, width=220).grid(
            row=1, column=0, sticky="w", pady=(0, 8))

        ctk.CTkLabel(header_row, text="Bill No.", font=theme.FONT_SMALL, text_color=theme.MUTED).grid(
            row=0, column=1, sticky="w", padx=(15, 0))
        self.bill_entry = ctk.CTkEntry(header_row, width=150)
        self.bill_entry.grid(row=1, column=1, sticky="w", padx=(15, 0), pady=(0, 8))

        # ---------------- Add item mini-form ----------------
        ctk.CTkLabel(self, text="Add Items", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(5, 5))
        item_row = ctk.CTkFrame(self, fg_color=theme.WHITE, corner_radius=8)
        item_row.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(item_row, text="Material Name", font=theme.FONT_SMALL, text_color=theme.MUTED).grid(
            row=0, column=0, sticky="w", padx=10, pady=(8, 0))
        self.item_name_var = ctk.StringVar(value="")
        self.item_name_combo = ctk.CTkComboBox(item_row, values=material_names, variable=self.item_name_var, width=180)
        self.item_name_combo.grid(row=1, column=0, padx=10, pady=(0, 8))

        ctk.CTkLabel(item_row, text="Quantity", font=theme.FONT_SMALL, text_color=theme.MUTED).grid(
            row=0, column=1, sticky="w", padx=10, pady=(8, 0))
        self.item_qty_entry = ctk.CTkEntry(item_row, width=80)
        apply_decimal_only(self, self.item_qty_entry)
        self.item_qty_entry.grid(row=1, column=1, padx=10, pady=(0, 8))

        ctk.CTkLabel(item_row, text="Unit Cost (₹)", font=theme.FONT_SMALL, text_color=theme.MUTED).grid(
            row=0, column=2, sticky="w", padx=10, pady=(8, 0))
        self.item_cost_entry = ctk.CTkEntry(item_row, width=90)
        apply_decimal_only(self, self.item_cost_entry)
        self.item_cost_entry.grid(row=1, column=2, padx=10, pady=(0, 8))

        ctk.CTkButton(item_row, text="+ Add", command=self._add_line_item, fg_color=theme.BRASS,
                      hover_color=theme.INK, font=theme.FONT_SMALL, width=70).grid(row=1, column=3, padx=10, pady=(0, 8))

        # ---------------- Running list ----------------
        list_frame = ctk.CTkFrame(self, fg_color=theme.WHITE)
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        cols = ("name", "qty", "cost", "total", "new")
        self.items_tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=8)
        headings = {"name": "Material", "qty": "Qty", "cost": "Unit Cost (₹)", "total": "Total (₹)", "new": ""}
        widths = {"name": 180, "qty": 60, "cost": 90, "total": 100, "new": 70}
        for c in cols:
            self.items_tree.heading(c, text=headings[c])
            self.items_tree.column(c, width=widths[c])
        self.items_tree.pack(fill="both", expand=True)

        self.total_label = ctk.CTkLabel(self, text="Grand Total: ₹0.00", font=theme.FONT_BODY_BOLD, text_color=theme.BRASS)
        self.total_label.pack(anchor="e", padx=20, pady=(0, 10))

        # ---------------- Additional Charges (Landed Cost) ----------------
        # Real charges from the same invoice, allocated across the items
        # above -- this is what turns a purchase rate into a true landed
        # cost. Discount/GST deliberately excluded from this list: those
        # affect what's OWED to the vendor, not what a material actually
        # costs to land on site, so allocating them into material cost
        # would misrepresent inventory value.
        charges_frame = ctk.CTkFrame(self, fg_color=theme.WHITE, corner_radius=8)
        charges_frame.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkLabel(charges_frame, text="Additional Charges (optional)", font=theme.FONT_BODY_BOLD,
                    text_color=theme.INK).pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(charges_frame, text="Shared costs on this bill, spread across the items above into their "
                                        "true landed cost.", font=("Segoe UI", 9), text_color=theme.MUTED).pack(
            anchor="w", padx=12, pady=(0, 8))

        self.charge_entries = {}
        charge_types = ["Transportation", "Loading", "Unloading", "Packing", "Insurance", "Miscellaneous"]
        charges_grid = ctk.CTkFrame(charges_frame, fg_color="transparent")
        charges_grid.pack(fill="x", padx=12, pady=(0, 8))
        for i, charge_type in enumerate(charge_types):
            row, col = divmod(i, 3)
            block = ctk.CTkFrame(charges_grid, fg_color="transparent")
            block.grid(row=row, column=col, padx=(0, 10), pady=4, sticky="w")
            ctk.CTkLabel(block, text=charge_type, font=("Segoe UI", 9), text_color=theme.MUTED).pack(anchor="w")
            entry = ctk.CTkEntry(block, width=100, placeholder_text="₹0")
            apply_decimal_only(self, entry)
            entry.pack(anchor="w")
            self.charge_entries[charge_type] = entry

        alloc_row = ctk.CTkFrame(charges_frame, fg_color="transparent")
        alloc_row.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(alloc_row, text="Allocation Method:", font=("Segoe UI", 9), text_color=theme.MUTED).pack(
            side="left", padx=(0, 8))
        self.allocation_var = ctk.StringVar(value="By Value")
        ctk.CTkOptionMenu(alloc_row, values=["By Value", "By Quantity"], variable=self.allocation_var,
                        width=130).pack(side="left")
        ctk.CTkLabel(alloc_row, text="By Value: costlier items absorb more. By Quantity: split per unit.",
                    font=("Segoe UI", 8), text_color=theme.MUTED).pack(side="left", padx=(8, 0))

        ctk.CTkButton(self, text="Save Purchase", command=self.save, fg_color=theme.BRASS,
                      hover_color=theme.INK, font=theme.FONT_BODY_BOLD).pack(pady=(0, 20))

    def _add_line_item(self):
        name = self.item_name_var.get().strip()
        if not name:
            messagebox.showerror("Missing material name", "Enter or select a material name.", parent=self)
            return
        try:
            qty = float(self.item_qty_entry.get().strip() or 0)
            cost = float(self.item_cost_entry.get().strip() or 0)
        except ValueError:
            messagebox.showerror("Invalid number", "Quantity and Unit Cost must be numbers.", parent=self)
            return
        if qty <= 0:
            messagebox.showerror("Invalid quantity", "Quantity must be greater than zero.", parent=self)
            return

        is_new = name.lower() not in [m["MaterialName"].lower() for m in self.existing_materials]
        self.line_items.append({"name": name, "quantity": qty, "unit_cost": cost, "is_new": is_new})
        self.items_tree.insert("", "end", values=(name, f"{qty:.2f}", f"{cost:,.2f}", f"{qty*cost:,.2f}",
                                                   "New Material" if is_new else ""))

        self.item_name_var.set("")
        self.item_qty_entry.delete(0, "end")
        self.item_cost_entry.delete(0, "end")

        grand_total = sum(i["quantity"] * i["unit_cost"] for i in self.line_items)
        self.total_label.configure(text=f"Grand Total: ₹{grand_total:,.2f}")

    def save(self):
        if not self.line_items:
            messagebox.showinfo("No items", "Add at least one item before saving.", parent=self)
            return
        vendor_name = self.vendor_var.get()

        bill_no = self.bill_entry.get().strip()

        # Real additional charges entered, if any -- validated before
        # anything is saved, so a typo doesn't create a half-saved purchase.
        real_charges = []
        for charge_type, entry in self.charge_entries.items():
            raw = entry.get().strip()
            if not raw:
                continue
            try:
                amount = float(raw)
            except ValueError:
                messagebox.showerror("Invalid amount", f"{charge_type}: enter a valid number.", parent=self)
                return
            if amount > 0:
                real_charges.append((charge_type, amount))

        # Everything below is one real transaction -- vendor creation,
        # the invoice header, every additional charge, and every
        # material/purchase insert either all commit together or none
        # of them do. Previously each db.execute() call committed
        # independently, meaning a failure partway through (say, on the
        # third of five line items) would have left an orphaned,
        # partially-saved purchase silently in the database.
        try:
            with db.transaction() as txn:
                vendor_id = None
                if vendor_name != "-- Select Vendor --":
                    match = next((v for v in self.vendors if v["VendorName"] == vendor_name), None)
                    vendor_id = match["VendorID"] if match else txn.execute(
                        "INSERT INTO mstVendor (VendorName) VALUES (?)", (vendor_name,))

                # Only create a real invoice header when there's something
                # for it to actually group -- multiple items sharing
                # charges, or charges at all. A single item with no
                # additional charges doesn't need one; it stays exactly
                # as simple as before.
                invoice_id = None
                if real_charges or len(self.line_items) > 1:
                    invoice_id = landed_cost.create_purchase_invoice(
                        vendor_id, bill_no or None, datetime.date.today().isoformat(), db_conn=txn)
                    for charge_type, amount in real_charges:
                        landed_cost.add_purchase_charge(invoice_id, charge_type, amount,
                                                        self.allocation_var.get(), db_conn=txn)

                created, restocked = 0, 0
                purchase_ids = []

                for item in self.line_items:
                    existing = txn.fetch_one(
                        "SELECT * FROM mstMaterial WHERE ProjectID=? AND LOWER(MaterialName)=LOWER(?)",
                        (self.project_id, item["name"]))
                    if existing:
                        material_id = existing["MaterialID"]
                        txn.execute(
                            "UPDATE mstMaterial SET CurrentStock = CurrentStock + ?, UnitCost=?, "
                            "VendorID=COALESCE(?, VendorID), ModifiedOn=datetime('now') WHERE MaterialID=?",
                            (item["quantity"], item["unit_cost"], vendor_id, material_id))
                        restocked += 1
                    else:
                        code = db.next_code("MTL", "mstMaterial", "MaterialCode")
                        material_id = txn.execute(
                            "INSERT INTO mstMaterial (ProjectID, MaterialCode, MaterialName, Category, UnitCost, "
                            "CurrentStock, VendorID) VALUES (?,?,?,?,?,?,?)",
                            (self.project_id, code, item["name"], "Uncategorized", item["unit_cost"],
                             item["quantity"], vendor_id))
                        created += 1

                    purchase_id = txn.execute(
                        "INSERT INTO trxMaterialPurchase (MaterialID, Quantity, UnitCost, TotalCost, Notes, "
                        "PurchaseInvoiceID) VALUES (?,?,?,?,?,?)",
                        (material_id, item["quantity"], item["unit_cost"], item["quantity"] * item["unit_cost"],
                         f"Bill: {bill_no}" if bill_no else None, invoice_id))
                    purchase_ids.append((item["name"], purchase_id))
        except Exception as e:
            messagebox.showerror("Purchase not saved",
                                f"Nothing was saved -- the entire purchase was rolled back due to an error:\n{e}",
                                parent=self)
            return

        db.log_activity("Project", self.project_id, "Purchase Recorded",
                        f"{vendor_name if vendor_id else 'No vendor'}: {len(self.line_items)} item(s)"
                        f" ({created} new, {restocked} restocked)")

        summary = (f"{len(self.line_items)} item(s) recorded -- {created} new material(s) created, "
                  f"{restocked} restocked.")
        if invoice_id and real_charges:
            # Show the real landed cost per item -- the actual point of
            # this feature, confirmed at the moment it matters most.
            breakdown = landed_cost.get_invoice_landed_costs(invoice_id)
            lines = [summary, "", "Landed cost (purchase rate + allocated charges):"]
            for name, purchase_id in purchase_ids:
                match = next((b for b in breakdown if b["purchase_id"] == purchase_id), None)
                if match:
                    lines.append(f"  {name}: ₹{match['purchase_rate']:.2f} + ₹{match['allocated_charge_per_unit']:.2f} "
                                f"= ₹{match['landed_cost']:.2f}/unit")
            summary = "\n".join(lines)

        messagebox.showinfo("Purchase saved", summary, parent=self)
        self.on_save()
        self.destroy()

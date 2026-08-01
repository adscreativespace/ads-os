"""
ADS OS Desktop -- Fee Calculator (Commercial module, first of six)
Calculates professional fees from Built-up Area x Rate per Service Type x
Scope %, with Discount/GST adjustments, and saves calculations per project.
Embedded in the Project Workspace's Commercial tab, matching how Planning
(FloorRoomPanel) and other tabs already work -- not a separate popup window.

This is a functioning calculator, not a pixel-match of any visual mockup --
built against real data (mstService, mstPackage, tblProject) that already
exists, with the mockup's information hierarchy as a loose reference.
"""
import customtkinter as ctk
from tkinter import ttk, messagebox
import db
import theme
from constants import apply_decimal_only

GST_DEFAULT = 18.0


class FeeCalculatorPanel(ctk.CTkFrame):
    def __init__(self, master, project_id):
        super().__init__(master, fg_color="transparent")
        self.project_id = project_id
        self.project = db.fetch_one("SELECT * FROM tblProject WHERE ProjectID=?", (project_id,))
        self.services = db.fetch_all("SELECT ServiceID, ServiceName FROM mstService WHERE Active=1 ORDER BY ServiceName")
        self.service_rows = {}  # ServiceID -> {"check", "rate_entry", "scope_entry"}
        self._build_ui()
        self._refresh_history()

    def _build_ui(self):
        ctk.CTkLabel(self, text="Fee Calculator", font=theme.FONT_HEADING, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 5))
        ctk.CTkLabel(self, text="Calculate professional fees based on area, scope, and service type.",
                     font=theme.FONT_SMALL, text_color=theme.MUTED).pack(anchor="w", padx=20, pady=(0, 10))

        columns = ctk.CTkFrame(self, fg_color="transparent")
        columns.pack(fill="both", expand=True, padx=20)

        left = ctk.CTkFrame(columns, fg_color=theme.WHITE, corner_radius=8)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right = ctk.CTkFrame(columns, fg_color=theme.WHITE, corner_radius=8, width=340)
        right.pack(side="left", fill="y")
        right.pack_propagate(False)

        # ---------------- LEFT: Area details + service types ----------------
        ctk.CTkLabel(left, text="Project & Area Details", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=15, pady=(15, 8))

        area_row = ctk.CTkFrame(left, fg_color="transparent")
        area_row.pack(fill="x", padx=15, pady=(0, 5))
        ctk.CTkLabel(area_row, text="Calculation Name", font=theme.FONT_SMALL, text_color=theme.MUTED).grid(
            row=0, column=0, sticky="w")
        self.calc_name_entry = ctk.CTkEntry(area_row, width=250)
        self.calc_name_entry.insert(0, "Primary Fee Calculation")
        self.calc_name_entry.grid(row=1, column=0, sticky="w", pady=(0, 8))

        ctk.CTkLabel(area_row, text="Built-up Area (sq.ft.)", font=theme.FONT_SMALL, text_color=theme.MUTED).grid(
            row=0, column=1, sticky="w", padx=(20, 0))
        self.area_entry = ctk.CTkEntry(area_row, width=140)
        apply_decimal_only(self, self.area_entry)
        self.area_entry.insert(0, str(self.project["TotalBuiltUpArea"]))
        self.area_entry.grid(row=1, column=1, sticky="w", padx=(20, 0), pady=(0, 8))

        ctk.CTkLabel(area_row, text="Additional Area (sq.ft.)", font=theme.FONT_SMALL, text_color=theme.MUTED).grid(
            row=0, column=2, sticky="w", padx=(20, 0))
        self.additional_area_entry = ctk.CTkEntry(area_row, width=140)
        apply_decimal_only(self, self.additional_area_entry)
        self.additional_area_entry.insert(0, "0")
        self.additional_area_entry.grid(row=1, column=2, sticky="w", padx=(20, 0), pady=(0, 8))

        ctk.CTkFrame(left, fg_color=theme.PARCHMENT, height=1).pack(fill="x", padx=15, pady=8)

        ctk.CTkLabel(left, text="Apply Service Types", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=15, pady=(0, 5))
        ctk.CTkLabel(left, text="Check a service, then set its Rate/Sq.ft and Scope %.",
                     font=theme.FONT_SMALL, text_color=theme.MUTED).pack(anchor="w", padx=15, pady=(0, 8))

        header_row = ctk.CTkFrame(left, fg_color="transparent")
        header_row.pack(fill="x", padx=15)
        ctk.CTkLabel(header_row, text="Service", font=theme.FONT_SMALL, text_color=theme.MUTED, width=220).pack(side="left")
        ctk.CTkLabel(header_row, text="Rate/Sq.ft (₹)", font=theme.FONT_SMALL, text_color=theme.MUTED, width=100).pack(side="left")
        ctk.CTkLabel(header_row, text="Scope %", font=theme.FONT_SMALL, text_color=theme.MUTED, width=80).pack(side="left")

        service_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent", height=260)
        service_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        for svc in self.services:
            self._add_service_row(service_scroll, svc)

        # ---------------- RIGHT: Adjustments + summary ----------------
        ctk.CTkLabel(right, text="Adjustments", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=15, pady=(15, 8))

        adj_row = ctk.CTkFrame(right, fg_color="transparent")
        adj_row.pack(fill="x", padx=15)
        ctk.CTkLabel(adj_row, text="Discount (%)", font=theme.FONT_SMALL, text_color=theme.MUTED).grid(row=0, column=0, sticky="w")
        self.discount_pct_entry = ctk.CTkEntry(adj_row, width=100)
        apply_decimal_only(self, self.discount_pct_entry)
        self.discount_pct_entry.insert(0, "0")
        self.discount_pct_entry.grid(row=1, column=0, sticky="w", pady=(0, 8))

        ctk.CTkLabel(adj_row, text="Additional Discount (₹)", font=theme.FONT_SMALL, text_color=theme.MUTED).grid(row=2, column=0, sticky="w")
        self.additional_discount_entry = ctk.CTkEntry(adj_row, width=100)
        apply_decimal_only(self, self.additional_discount_entry)
        self.additional_discount_entry.insert(0, "0")
        self.additional_discount_entry.grid(row=3, column=0, sticky="w", pady=(0, 8))

        ctk.CTkLabel(adj_row, text="GST (%)", font=theme.FONT_SMALL, text_color=theme.MUTED).grid(row=4, column=0, sticky="w")
        self.gst_entry = ctk.CTkEntry(adj_row, width=100)
        apply_decimal_only(self, self.gst_entry)
        self.gst_entry.insert(0, str(GST_DEFAULT))
        self.gst_entry.grid(row=5, column=0, sticky="w", pady=(0, 8))

        ctk.CTkButton(right, text="Calculate", command=self._calculate,
                      fg_color=theme.INK, hover_color=theme.BRASS, font=theme.FONT_BODY_BOLD).pack(
            fill="x", padx=15, pady=(5, 10))

        ctk.CTkFrame(right, fg_color=theme.PARCHMENT, height=1).pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(right, text="Selected Services", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=15, pady=(5, 5))
        self.selected_services_label = ctk.CTkLabel(right, text="Check services on the left, then Calculate.",
                                                     font=theme.FONT_SMALL, text_color=theme.MUTED,
                                                     justify="left", wraplength=300)
        self.selected_services_label.pack(anchor="w", padx=15, pady=(0, 10))

        ctk.CTkLabel(right, text="Fee Summary", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=15, pady=(5, 8))
        self.summary_label = ctk.CTkLabel(right, text="Click Calculate to see the fee breakdown.",
                                          font=theme.FONT_BODY, text_color=theme.MUTED,
                                          justify="left", wraplength=300)
        self.summary_label.pack(anchor="w", padx=15, pady=(0, 10))

        self.total_fee_label = ctk.CTkLabel(right, text="", font=("Georgia", 20, "bold"), text_color=theme.BRASS)
        self.total_fee_label.pack(anchor="w", padx=15, pady=(0, 15))

        ctk.CTkButton(right, text="Save Calculation", command=self._save_calculation,
                      fg_color=theme.BRASS, hover_color=theme.INK, font=theme.FONT_BODY_BOLD).pack(
            fill="x", padx=15, pady=(0, 15))

        # ---------------- History ----------------
        ctk.CTkLabel(self, text="Saved Calculations", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 5))
        history_frame = ctk.CTkFrame(self, fg_color=theme.WHITE)
        history_frame.pack(fill="x", padx=20, pady=(0, 20))
        cols = ("name", "area", "total", "date")
        self.history_tree = ttk.Treeview(history_frame, columns=cols, show="headings", height=5)
        headings = {"name": "Calculation Name", "area": "Area (sq.ft.)", "total": "Total Fee (₹)", "date": "Saved On"}
        widths = {"name": 220, "area": 120, "total": 150, "date": 160}
        for c in cols:
            self.history_tree.heading(c, text=headings[c])
            self.history_tree.column(c, width=widths[c])
        self.history_tree.pack(fill="x", padx=5, pady=5)

        self._last_calculation = None  # populated by _calculate(), used by _save_calculation()

    def _add_service_row(self, parent, svc):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)
        check_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(row, text=svc["ServiceName"], variable=check_var, font=theme.FONT_SMALL,
                        text_color=theme.INK, width=200).pack(side="left")
        rate_entry = ctk.CTkEntry(row, width=90)
        apply_decimal_only(self, rate_entry)
        rate_entry.insert(0, "0")
        rate_entry.pack(side="left", padx=(10, 5))
        scope_entry = ctk.CTkEntry(row, width=70)
        apply_decimal_only(self, scope_entry)
        scope_entry.insert(0, "100")
        scope_entry.pack(side="left")
        self.service_rows[svc["ServiceID"]] = {
            "name": svc["ServiceName"], "check": check_var, "rate_entry": rate_entry, "scope_entry": scope_entry
        }

    def _calculate(self):
        try:
            built_up = float(self.area_entry.get().strip() or 0)
            additional = float(self.additional_area_entry.get().strip() or 0)
            total_area = built_up + additional
            discount_pct = float(self.discount_pct_entry.get().strip() or 0)
            additional_discount = float(self.additional_discount_entry.get().strip() or 0)
            gst_pct = float(self.gst_entry.get().strip() or 0)
        except ValueError:
            messagebox.showerror("Invalid number", "Area, discount, and GST fields must be numbers.", parent=self)
            return

        line_items = []
        sub_total = 0.0
        for service_id, row in self.service_rows.items():
            if not row["check"].get():
                continue
            try:
                rate = float(row["rate_entry"].get().strip() or 0)
                scope = float(row["scope_entry"].get().strip() or 0)
            except ValueError:
                messagebox.showerror("Invalid number", f"Rate/Scope for '{row['name']}' must be numbers.", parent=self)
                return
            amount = total_area * rate * (scope / 100.0)
            line_items.append({"service_id": service_id, "name": row["name"], "rate": rate,
                               "scope": scope, "amount": amount})
            sub_total += amount

        if not line_items:
            messagebox.showinfo("No services selected", "Check at least one Service Type before calculating.", parent=self)
            return

        discount_amount = sub_total * (discount_pct / 100.0)
        after_discount = sub_total - discount_amount - additional_discount
        gst_amount = after_discount * (gst_pct / 100.0)
        total_fee = after_discount + gst_amount

        self._last_calculation = {
            "built_up_area": built_up, "additional_area": additional, "total_area": total_area,
            "line_items": line_items, "sub_total": sub_total, "discount_pct": discount_pct,
            "discount_amount": discount_amount, "additional_discount": additional_discount,
            "gst_pct": gst_pct, "gst_amount": gst_amount, "total_fee": total_fee,
        }

        # No need to scan dozens of checkboxes to know what's included --
        # show it plainly, updated on every real calculation.
        services_text = "\n".join(f"✔ {item['name']}" for item in line_items)
        self.selected_services_label.configure(text=services_text)

        summary_lines = [f"Total Area: {total_area:.2f} sq.ft.", f"Sub Total: ₹{sub_total:,.2f}"]
        if discount_amount:
            summary_lines.append(f"Discount ({discount_pct:.1f}%): -₹{discount_amount:,.2f}")
        if additional_discount:
            summary_lines.append(f"Additional Discount: -₹{additional_discount:,.2f}")
        summary_lines.append(f"GST ({gst_pct:.1f}%): +₹{gst_amount:,.2f}")
        self.summary_label.configure(text="\n".join(summary_lines))
        self.total_fee_label.configure(text=f"₹{total_fee:,.2f}")

    def _save_calculation(self):
        if not self._last_calculation:
            messagebox.showinfo("Nothing to save", "Click Calculate first.", parent=self)
            return
        calc_name = self.calc_name_entry.get().strip()
        if not calc_name:
            messagebox.showerror("Missing field", "Calculation Name is required.", parent=self)
            return

        c = self._last_calculation
        calc_id = db.execute(
            """INSERT INTO trxFeeCalculation (ProjectID, CalculationName, BuiltUpArea, AdditionalArea,
               DiscountPercent, AdditionalDiscount, GSTPercent, TotalFee)
               VALUES (?,?,?,?,?,?,?,?)""",
            (self.project_id, calc_name, c["built_up_area"], c["additional_area"],
             c["discount_pct"], c["additional_discount"], c["gst_pct"], c["total_fee"])
        )
        for item in c["line_items"]:
            db.execute(
                "INSERT INTO trxFeeCalculationItem (CalculationID, ServiceID, RatePerSqft, ScopePercent, Amount) VALUES (?,?,?,?,?)",
                (calc_id, item["service_id"], item["rate"], item["scope"], item["amount"])
            )
        db.log_activity("Project", self.project_id, "Fee Calculation Saved", calc_name)
        messagebox.showinfo("Saved", f"'{calc_name}' saved -- Total Fee: ₹{c['total_fee']:,.2f}", parent=self)
        self._refresh_history()

    def _refresh_history(self):
        for row in self.history_tree.get_children():
            self.history_tree.delete(row)
        calcs = db.fetch_all(
            "SELECT * FROM trxFeeCalculation WHERE ProjectID=? ORDER BY CalculationID DESC", (self.project_id,))
        for c in calcs:
            total_area = c["BuiltUpArea"] + c["AdditionalArea"]
            self.history_tree.insert("", "end", iid=c["CalculationID"],
                                     values=(c["CalculationName"], f"{total_area:.2f}",
                                             f"{c['TotalFee']:,.2f}", c["CreatedOn"]))

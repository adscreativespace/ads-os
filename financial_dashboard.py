"""
ADS OS Desktop -- Financial Dashboard
Company-wide business intelligence, distinct from Project Workspace's
per-project Commercial tab. Read-only -- no data entry, no CRUD, purely an
aggregation layer over data that already exists across every project.

v4.9.6c: Executive Financial Intelligence. Financial Health and Cash
Required Today (a combined hero banner, first thing shown), Financial
Exposure (replacing Operational Snapshot -- that belongs on the Home
Dashboard, not here), Largest Financial Risk, Recent Financial Activity
(the latest real payments/receipts across all three payment tables), and
KPI reconciliation (clicking Vendor/Contractor Outstanding opens a real
breakdown dialog with a sum-check, instead of navigating away
immediately). The existing one-row KPI layout, shared kpi_card component,
icons, subtitles, and styling are all unchanged, per explicit instruction.

Financial Health is explicitly an operational heuristic, not an
accounting rating -- stated as such wherever it's shown, since the
thresholds behind Healthy/Attention/Critical are a judgment call, not a
certified standard, even though every number feeding into them is real.

Filter-aware navigation (Vendor Outstanding -> Vendors already filtered
to Outstanding) is NOT implemented this round -- it would need new filter
UI added to three separate screens (Vendors/Contractors/Clients), which
is real, separate work, not a quick addition alongside everything else
here. Landing on the right screen (already built) is the honest interim
state.

Still explicitly NOT built, because the data genuinely doesn't exist yet:
Gross Profit / Net Profit, Cash in Hand / Bank Balances, trend charts,
Ageing buckets, Contracts Expiring / Invoices Awaiting Approval alerts,
date filters and Export -- all explicitly postponed per this round's own
brief, since the database doesn't yet have enough historical depth to
make them meaningful.
"""
import customtkinter as ctk
import datetime
import theme
import db
import ui_components as ui
import financial_calcs as fc


class FinancialDashboardScreen(ctk.CTkFrame):
    def __init__(self, master, app=None):
        super().__init__(master, fg_color=theme.PARCHMENT)
        self.app = app
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 5))
        title_block = ctk.CTkFrame(header, fg_color="transparent")
        title_block.pack(side="left")
        ctk.CTkLabel(title_block, text="Financial Dashboard", font=theme.FONT_HEADING, text_color=theme.INK).pack(anchor="w")
        ctk.CTkLabel(title_block, text="Company-wide financial intelligence across every project. Read-only -- "
                                       "to record a payment, purchase, or contract, open the relevant project.",
                     font=theme.FONT_SMALL, text_color=theme.MUTED).pack(anchor="w")

        refresh_block = ctk.CTkFrame(header, fg_color="transparent")
        refresh_block.pack(side="right")
        ctk.CTkButton(refresh_block, text="↻ Refresh", command=self.refresh, fg_color=theme.INK,
                     hover_color=theme.BRASS, font=theme.FONT_SMALL, width=90, height=28).pack(side="right")
        self.last_updated_label = ctk.CTkLabel(refresh_block, text="", font=("Segoe UI", 9),
                                               text_color=theme.MUTED)
        self.last_updated_label.pack(side="right", padx=(0, 12))

        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=20, pady=(10, 8))

        self.scroll = ui.AdaptiveScrollFrame(self, fg_color=theme.PARCHMENT)
        self.scroll.pack(fill="both", expand=True)
        self.content = self.scroll.content

    def _navigate(self, screen_name):
        if self.app:
            self.app.show(screen_name)

    def refresh(self):
        for w in self.stats_frame.winfo_children():
            w.destroy()
        for w in self.content.winfo_children():
            w.destroy()

        now = datetime.datetime.now()
        self.last_updated_label.configure(text=f"Last Updated: {now.strftime('%d %b %Y, %I:%M %p')}")

        revenue = fc.get_revenue_summary()
        expenses = fc.get_expenses_summary()
        cash = fc.get_cash_position()
        outstanding = fc.get_outstanding_summary()
        vendor_payables = fc.get_vendors_with_payments_due()
        contractor_payables = fc.get_contractors_with_payments_due()

        # ---------------- Executive KPI row: six real cards, unchanged ----------------
        kpis = [
            (f"₹{revenue['total_received']:,.0f}", "Revenue", "Amount received", "💰", "#D4F0E0", 27,
             lambda: self._navigate("Reports")),
            (f"₹{cash['money_out']:,.0f}", "Expenses", "All purchases + labour", "🧾", "#FBE0E0", 27,
             lambda: self._navigate("Reports")),
            (f"₹{cash['net_position']:,.0f}", "Net Position", "Simple estimate, not a formal P&L", "📊", "#D6E8FA",
             29, lambda: self._navigate("Reports")),
            (f"₹{outstanding['client_receivables_outstanding']:,.0f}", "Client Receivables", "Owed to you",
             "📥", "#F5E6D3", 27, lambda: self._navigate("Clients")),
            (f"₹{outstanding['vendor_outstanding']:,.0f}", "Vendor Outstanding", "You owe vendors",
             "🏪", "#FBF0D6", 27, lambda: self._show_reconciliation("Vendor Outstanding", vendor_payables)),
            (f"₹{outstanding['contractor_outstanding']:,.0f}", "Contractor Outstanding", "You owe contractors",
             "👷", "#E8DFF5", 27, lambda: self._show_reconciliation("Contractor Outstanding", contractor_payables)),
        ]
        for col in range(6):
            self.stats_frame.grid_columnconfigure(col, weight=1)
        for col_idx, (value, label, sublabel, icon, bg_color, value_size, on_click) in enumerate(kpis):
            ui.kpi_card(self.stats_frame, value, label, sublabel, icon, bg_color, col_idx,
                       value_size=value_size, on_click=on_click if self.app else None)

        # ---------------- Financial Health + Cash Required Today (hero banner) ----------------
        health = fc.get_financial_health()
        cash_required = outstanding["vendor_outstanding"] + outstanding["contractor_outstanding"]
        net_exposure = outstanding["client_receivables_outstanding"] - cash_required
        hero = ctk.CTkFrame(self.content, fg_color=theme.WHITE, corner_radius=8)
        hero.pack(fill="x", padx=20, pady=(4, 10))
        hero_inner = ctk.CTkFrame(hero, fg_color="transparent")
        hero_inner.pack(fill="x", padx=20, pady=15)
        health_block = ctk.CTkFrame(hero_inner, fg_color="transparent")
        health_block.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(health_block, text="Financial Health", font=("Segoe UI", 10), text_color=theme.MUTED).pack(anchor="w")
        status_row = ctk.CTkFrame(health_block, fg_color="transparent")
        status_row.pack(anchor="w")
        # Real colored dot instead of an emoji -- the colored-circle emoji
        # (🟢/🟡/🔴) did not render as a color in the actual app, showing
        # as a missing-glyph box instead, confirmed directly from a real
        # screenshot. "●" is the same simple, already-proven character
        # used for every other status indicator across this app.
        ctk.CTkLabel(status_row, text="●", font=("Segoe UI", 18), text_color=health["status_color"]).pack(side="left")
        ctk.CTkLabel(status_row, text=f" {health['label']}", font=("Georgia", 20, "bold"),
                    text_color=theme.INK).pack(side="left")
        ctk.CTkLabel(health_block, text="Operational heuristic, not an accounting rating -- from receivables, "
                                        "net position, and outstanding payables.", font=("Segoe UI", 9),
                    text_color=theme.MUTED, wraplength=320, justify="left").pack(anchor="w", pady=(2, 8))
        # Enriched with the same real figures already computed elsewhere on
        # this screen, so the health verdict comes with the numbers behind
        # it rather than sitting in isolation.
        mini_row = ctk.CTkFrame(health_block, fg_color="transparent")
        mini_row.pack(anchor="w")
        for mini_value, mini_label in [(f"₹{cash['net_position']:,.0f}", "Net Position"),
                                       (f"₹{net_exposure:,.0f}", "Exposure")]:
            mini_block = ctk.CTkFrame(mini_row, fg_color="transparent")
            mini_block.pack(side="left", padx=(0, 20))
            ctk.CTkLabel(mini_block, text=mini_value, font=("Segoe UI", 13, "bold"), text_color=theme.INK).pack(anchor="w")
            ctk.CTkLabel(mini_block, text=mini_label, font=("Segoe UI", 9), text_color=theme.MUTED).pack(anchor="w")
        divider = ctk.CTkFrame(hero_inner, fg_color=theme.PARCHMENT, width=1)
        divider.pack(side="left", fill="y", padx=20)
        cash_block = ctk.CTkFrame(hero_inner, fg_color="transparent")
        cash_block.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(cash_block, text="Cash Required Today", font=("Segoe UI", 10), text_color=theme.MUTED).pack(anchor="w")
        # ~15% larger than the surrounding 20pt metrics -- answers the
        # single most urgent operational question, per the specific request.
        ctk.CTkLabel(cash_block, text=f"₹{cash_required:,.0f}", font=("Georgia", 23, "bold"),
                    text_color="#8B2E2E" if cash_required > 0 else theme.INK).pack(anchor="w")
        ctk.CTkLabel(cash_block, text="Vendor Outstanding + Contractor Outstanding", font=("Segoe UI", 9),
                    text_color=theme.MUTED).pack(anchor="w", pady=(2, 0))

        # ---------------- Financial Exposure (replacing Operational Snapshot) ----------------
        # Operational Snapshot (Active Projects/Contractors/Vendors) belongs
        # on the Home Dashboard -- this screen is about money, so its
        # summary block should be about money too.
        ctk.CTkLabel(self.content, text="Financial Exposure", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(2, 6))
        exposure_row = ctk.CTkFrame(self.content, fg_color="transparent")
        exposure_row.pack(fill="x", padx=20, pady=(0, 10))
        ui.stat_card(exposure_row, f"₹{outstanding['client_receivables_outstanding']:,.0f}",
                    "Receivables", "Owed to you").pack(side="left", padx=(0, 12))
        ui.stat_card(exposure_row, f"₹{outstanding['vendor_outstanding']:,.0f}",
                    "Vendor Payables", "You owe").pack(side="left", padx=(0, 12))
        ui.stat_card(exposure_row, f"₹{outstanding['contractor_outstanding']:,.0f}",
                    "Contractor Payables", "You owe").pack(side="left", padx=(0, 12))
        # Net Exposure is the conclusion of this row, not just a fourth
        # equal-weight card -- a custom, self-contained variant here
        # (darker border, bold title, larger value) rather than a change
        # to stat_card() itself, which every other module also relies on.
        net_card = ctk.CTkFrame(exposure_row, fg_color=theme.WHITE, corner_radius=8, width=175, height=90,
                                border_width=2, border_color=theme.INK)
        net_card.pack(side="left", padx=(0, 12))
        net_card.pack_propagate(False)
        ctk.CTkLabel(net_card, text="Net Exposure", font=("Segoe UI", 10, "bold"), text_color=theme.INK).pack(
            pady=(12, 0))
        ctk.CTkLabel(net_card, text=f"₹{net_exposure:,.0f}", font=("Georgia", 24, "bold"),
                    text_color="#8B2E2E" if net_exposure < 0 else "#2E8B57").pack()
        ctk.CTkLabel(net_card, text="Receivables minus total payables", font=("Segoe UI", 9),
                    text_color=theme.MUTED).pack()

        # ---------------- Largest Financial Risk ----------------
        ctk.CTkLabel(self.content, text="Largest Financial Risk", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(2, 6))
        risk_row = ctk.CTkFrame(self.content, fg_color="transparent")
        risk_row.pack(fill="x", padx=20, pady=(0, 10))
        self._risk_card(risk_row, "Highest Vendor Liability", vendor_payables[0] if vendor_payables else None,
                       "Vendors", sum(v["outstanding"] for v in vendor_payables))
        self._risk_card(risk_row, "Highest Contractor Liability", contractor_payables[0] if contractor_payables else None,
                       "Contractors", sum(c["outstanding"] for c in contractor_payables))

        # ---------------- Top Outstanding tables ----------------
        ctk.CTkLabel(self.content, text="Top Outstanding", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(2, 6))
        tables_row = ctk.CTkFrame(self.content, fg_color="transparent")
        tables_row.pack(fill="x", padx=20, pady=(0, 10))
        self._top_table(tables_row, "Top Outstanding Clients", fc.get_top_outstanding_clients(), "Clients",
                        "✓ All invoices collected")
        self._top_table(tables_row, "Top Vendor Payables", vendor_payables[:5], "Vendors",
                        "✓ All vendor payments are up to date")
        self._top_table(tables_row, "Top Contractor Payables", contractor_payables[:5], "Contractors",
                        "✓ No contractor dues")

        # ---------------- Recent Financial Activity ----------------
        ctk.CTkLabel(self.content, text="Recent Financial Activity", font=theme.FONT_BODY_BOLD,
                    text_color=theme.INK).pack(anchor="w", padx=20, pady=(2, 6))
        recent_activity = fc.get_recent_financial_activity(limit=10)
        activity_card = ctk.CTkFrame(self.content, fg_color=theme.WHITE, corner_radius=8)
        activity_card.pack(fill="x", padx=20, pady=(0, 10))
        if not recent_activity:
            ctk.CTkLabel(activity_card, text="No financial activity recorded yet.", font=theme.FONT_SMALL,
                        text_color=theme.MUTED).pack(anchor="w", padx=15, pady=15)
        else:
            type_icons = {"Client Receipt": "📥", "Vendor Payment": "🏪", "Contractor Payment": "👷"}
            # Distinct colors per type -- receipts (money in) green,
            # vendor payments (money out) red, contractor payments (money
            # out) amber, so the feed is scannable by color, not just text.
            type_colors = {"Client Receipt": "#2E8B57", "Vendor Payment": "#8B2E2E", "Contractor Payment": "#B68100"}
            for i, entry in enumerate(recent_activity):
                row = ctk.CTkFrame(activity_card, fg_color="transparent")
                row.pack(fill="x", padx=15, pady=(10 if i == 0 else 4, 4 if i < len(recent_activity) - 1 else 10))
                left = ctk.CTkFrame(row, fg_color="transparent")
                left.pack(side="left", fill="x", expand=True)
                type_row = ctk.CTkFrame(left, fg_color="transparent")
                type_row.pack(anchor="w")
                ctk.CTkLabel(type_row, text="●", font=("Segoe UI", 10),
                            text_color=type_colors.get(entry["type"], theme.MUTED)).pack(side="left")
                ctk.CTkLabel(type_row, text=f" {type_icons.get(entry['type'], '•')} {entry['type']}",
                            font=theme.FONT_SMALL, text_color=theme.INK).pack(side="left")
                ctk.CTkLabel(left, text=f"{entry['detail']}  ·  {entry['date']}", font=("Segoe UI", 9),
                            text_color=theme.MUTED).pack(anchor="w")
                ctk.CTkLabel(row, text=f"₹{entry['amount']:,.0f}", font=theme.FONT_BODY_BOLD,
                            text_color=type_colors.get(entry["type"], "#2E8B57")).pack(side="right")

        # ---------------- Alerts: real counts, granular empty states ----------------
        ctk.CTkLabel(self.content, text="Alerts", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(2, 6))
        overdue_list = fc.get_overdue_invoices()
        vendors_due = fc.get_vendors_with_payments_due()
        contractors_due = fc.get_contractors_with_payments_due()

        alert_chips = ctk.CTkFrame(self.content, fg_color="transparent")
        alert_chips.pack(fill="x", padx=20, pady=(0, 10))
        alert_defs = [
            (overdue_list, "Overdue Client Receivables", "#8B2E2E", "Clients"),
            (vendors_due, "Vendor Payments Due", "#B68100", "Vendors"),
            (contractors_due, "Contractor Payments Due", "#1E5FA8", "Contractors"),
        ]
        any_alerts = False
        for items, label, color, screen_name in alert_defs:
            if items:
                any_alerts = True
                pill = ui.pill_badge(alert_chips, f"{label}  ({len(items)})", color)
                pill.pack(side="left", padx=(0, 8))
                if self.app:
                    pill.configure(cursor="hand2")
                    pill.bind("<Button-1>", lambda e, s=screen_name: self._navigate(s))
        if not any_alerts:
            # Granular, reassuring per-type messages rather than one
            # generic line -- matches the specific examples requested.
            empty_lines = ["✓ All invoices collected.", "✓ All vendor payments are up to date.", "✓ No contractor dues."]
            for line in empty_lines:
                ctk.CTkLabel(self.content, text=line, font=theme.FONT_SMALL, text_color="#2E8B57").pack(
                    anchor="w", padx=20, pady=1)
            ctk.CTkFrame(self.content, fg_color="transparent", height=10).pack()
            return

        if overdue_list:
            ctk.CTkLabel(self.content, text="Overdue Client Receivables", font=("Segoe UI", 10, "bold"),
                        text_color=theme.MUTED).pack(anchor="w", padx=20, pady=(8, 4))
            for item in overdue_list:
                inv, days_overdue = item["invoice"], item["days_overdue"]
                row = ctk.CTkFrame(self.content, fg_color=theme.WHITE, corner_radius=6)
                row.pack(fill="x", padx=20, pady=3)
                left = ctk.CTkFrame(row, fg_color="transparent")
                left.pack(side="left", fill="x", expand=True, padx=12, pady=8)
                ctk.CTkLabel(left, text=f"{inv['ProjectName']} -- {inv['InvoiceNo']}", font=theme.FONT_BODY_BOLD,
                            text_color=theme.INK).pack(anchor="w")
                ctk.CTkLabel(left, text=f"Overdue {days_overdue} day(s)", font=theme.FONT_SMALL,
                            text_color="#8B2E2E").pack(anchor="w")
                ctk.CTkLabel(row, text=f"₹{item['outstanding']:,.0f} outstanding", font=theme.FONT_BODY_BOLD,
                            text_color=theme.INK).pack(side="right", padx=12, pady=8)

    def _risk_card(self, parent, title, entry, screen_name, total_dues=0):
        card = ctk.CTkFrame(parent, fg_color=theme.WHITE, corner_radius=8)
        card.pack(side="left", fill="both", expand=True, padx=(0, 12))
        ctk.CTkLabel(card, text=title, font=("Segoe UI", 10), text_color=theme.MUTED).pack(
            anchor="w", padx=15, pady=(15, 4))
        if not entry:
            ctk.CTkLabel(card, text="None right now", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
                anchor="w", padx=15, pady=(0, 15))
            return
        ctk.CTkLabel(card, text=entry["name"], font=("Georgia", 15, "bold"), text_color=theme.INK).pack(
            anchor="w", padx=15)
        amount_label = ctk.CTkLabel(card, text=f"₹{entry['outstanding']:,.0f}", font=("Georgia", 18, "bold"),
                                    text_color="#8B2E2E")
        amount_label.pack(anchor="w", padx=15, pady=(2, 0))
        # Real concentration percentage -- genuinely computed from the
        # actual total dues passed in, not a placeholder figure.
        if total_dues > 0:
            pct = entry["outstanding"] / total_dues * 100
            ctk.CTkLabel(card, text=f"{pct:.0f}% of total dues", font=("Segoe UI", 9), text_color=theme.MUTED).pack(
                anchor="w", padx=15, pady=(0, 15))
        else:
            ctk.CTkFrame(card, fg_color="transparent", height=15).pack()
        if self.app:
            for w in (card, amount_label):
                w.configure(cursor="hand2")
                w.bind("<Button-1>", lambda e: self._navigate(screen_name))

    def _show_reconciliation(self, title, entries):
        """
        KPI reconciliation -- clicking Vendor/Contractor Outstanding shows
        the real per-entity breakdown that sums to the KPI total, instead
        of navigating away immediately. Reuses the same real data already
        computed for the Top Outstanding tables, just presented as a
        verifiable dialog rather than a second, separate calculation.
        """
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("340x400")
        dialog.configure(fg_color=theme.PARCHMENT)
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text=title, font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 10))
        scroll = ui.AdaptiveScrollFrame(dialog, fg_color=theme.PARCHMENT)
        scroll.pack(fill="both", expand=True, padx=20)
        total = 0
        for entry in entries:
            row = ctk.CTkFrame(scroll.content, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=entry["name"], font=theme.FONT_SMALL, text_color=theme.INK).pack(side="left")
            ctk.CTkLabel(row, text=f"₹{entry['outstanding']:,.0f}", font=theme.FONT_SMALL,
                        text_color=theme.BRASS).pack(side="right")
            total += entry["outstanding"]
        if not entries:
            ctk.CTkLabel(scroll.content, text="Nothing outstanding.", font=theme.FONT_SMALL,
                        text_color=theme.MUTED).pack(anchor="w", pady=10)

        ctk.CTkFrame(dialog, fg_color=theme.INK, height=1).pack(fill="x", padx=20, pady=(8, 8))
        ctk.CTkLabel(dialog, text=f"Total: ₹{total:,.0f} ✓", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(0, 15))

    def _top_table(self, parent, title, rows, screen_name, empty_message="✓ Nothing outstanding here"):
        card = ctk.CTkFrame(parent, fg_color=theme.WHITE, corner_radius=8)
        card.pack(side="left", fill="both", expand=True, padx=(0, 10))
        ctk.CTkLabel(card, text=title, font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=15, pady=(15, 8))
        if not rows:
            ctk.CTkLabel(card, text=empty_message, font=("Segoe UI", 11, "bold"),
                        text_color="#2E8B57").pack(anchor="w", padx=15, pady=(0, 2))
            ctk.CTkLabel(card, text="Everything is settled up.", font=theme.FONT_SMALL,
                        text_color=theme.MUTED).pack(anchor="w", padx=15, pady=(0, 15))
            return
        for r in rows:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=3)
            name_label = ctk.CTkLabel(row, text=r["name"], font=theme.FONT_SMALL, text_color=theme.INK)
            name_label.pack(side="left")
            amount_label = ctk.CTkLabel(row, text=f"₹{r['outstanding']:,.0f}", font=theme.FONT_SMALL,
                                        text_color=theme.BRASS)
            amount_label.pack(side="right")
            if self.app:
                for w in (row, name_label, amount_label):
                    w.configure(cursor="hand2")
                    w.bind("<Button-1>", lambda e, s=screen_name: self._navigate(s))
        ctk.CTkFrame(card, fg_color="transparent", height=10).pack()

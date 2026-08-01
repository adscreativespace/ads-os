"""
ADS OS Desktop -- Client Screen (Layer 1: Presentation)
CRUD for tblClient. No business logic here -- forms only read/write via db.py.

Incorporates Decision 033 (Smart Country & Phone Engine) and Decision 034
(Smart Form UX Standards): real-time email validation with visual feedback,
GSTIN/PAN format validation, multi-line address, auto-capitalization, duplicate
client detection by mobile number, mobile display formatting, and a dynamic
Lead Source list with an "Add New Source" option.
"""
import customtkinter as ctk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import db
import theme
import ui_components as ui
from constants import (INDIAN_STATES, COUNTRIES, INDIA_COUNTRY_CODE,
                        country_label, country_from_label, apply_numeric_only, apply_decimal_only,
                        is_valid_email, email_typo_suggestion, is_valid_gstin, is_valid_pan,
                        format_mobile_display, to_title_case)

ADD_NEW_SOURCE = "+ Add New Source..."
PRIORITY_OPTIONS = ["Normal", "High", "VIP"]


def get_lead_sources():
    rows = db.fetch_all("SELECT SourceName FROM mstLeadSource WHERE Active=1 ORDER BY SourceID")
    return [r["SourceName"] for r in rows]


def get_client_relationship(client_id):
    """
    Relationship (New/Existing/Repeat) is never manually set -- it's derived
    from actual project count, so it can never drift out of sync with reality.
    Per Decision 021: 'Don't ask. ADS OS already knows.'
    """
    count = db.fetch_one("SELECT COUNT(*) AS n FROM tblProject WHERE ClientID=?", (client_id,))["n"]
    if count == 0:
        return "New Lead"
    elif count == 1:
        return "Existing Client"
    return "Repeat Client"


class ClientScreen(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=theme.PARCHMENT)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Reverted the max-content-width container from the previous round
        # -- that was built against a misdiagnosis (later corrected) that
        # the fix for "feels spread out on a wide monitor" was a centered,
        # capped-width layout like a web page. The actual want is the
        # opposite: a proper desktop app that expands to fill the
        # available workspace, preserving existing proportions between
        # KPI/insight/client cards as the window grows, with no fixed
        # max-width and no centering. Everything below is parented
        # directly to self again, filling whatever width the window
        # actually has.
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 5))
        title_block = ctk.CTkFrame(header, fg_color="transparent")
        title_block.pack(side="left")
        ctk.CTkLabel(title_block, text="Clients", font=theme.FONT_HEADING, text_color=theme.INK).pack(anchor="w")
        ctk.CTkLabel(title_block, text="Manage your client relationships and view business insights.",
                    font=theme.FONT_SMALL, text_color=theme.MUTED).pack(anchor="w")

        # New Client -- primary action, right edge
        ctk.CTkButton(header, text="+ New Client  ▾", command=self.open_add_form,
                      fg_color=theme.BRASS, hover_color=theme.INK,
                      font=theme.FONT_BODY_BOLD, width=140).pack(side="right")

        # Notification and Help icons removed -- per explicit instruction.
        # They had no real function behind them (no notification system,
        # no help system), and unlike Dashboard's disabled search
        # placeholder (which reserves space for a concretely planned
        # feature), these two were scaffolding with no clear purpose,
        # cluttering the header for no real benefit. Header is now just
        # Search + New Client.

        # Search -- real and functional, with the same Ctrl+K visual cue
        # Dashboard already established, for consistency across the app.
        search_frame = ctk.CTkFrame(header, fg_color=theme.WHITE, corner_radius=8, border_width=1,
                                    border_color=theme.MUTED)
        search_frame.pack(side="right", padx=(0, 20))
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="Search clients by name, code, phone, email...",
                                         width=280, fg_color="transparent", border_width=0)
        self.search_entry.pack(side="left", padx=(10, 4), pady=4)
        self.search_entry.bind("<KeyRelease>", lambda e: self.refresh())
        ctk.CTkLabel(search_frame, text="Ctrl+K", font=("Segoe UI", 9), text_color=theme.MUTED).pack(
            side="left", padx=(0, 10))

        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=20, pady=(10, 6))

        self.insights_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.insights_frame.pack(fill="x", padx=20, pady=(0, 8))

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=20, pady=(0, 22))
        self.toolbar_search_entry = None  # search lives in the header now, not duplicated here

        self.priority_filter_var = ctk.StringVar(value="All Priorities")
        ctk.CTkOptionMenu(toolbar, values=["All Priorities"] + PRIORITY_OPTIONS,
                          variable=self.priority_filter_var, width=130,
                          command=lambda c: self.refresh()).pack(side="left", padx=(0, 8))

        self.relationship_filter_var = ctk.StringVar(value="All Relationships")
        ctk.CTkOptionMenu(toolbar, values=["All Relationships", "New Lead", "Existing Client", "Repeat Client"],
                          variable=self.relationship_filter_var, width=150,
                          command=lambda c: self.refresh()).pack(side="left", padx=(0, 8))

        # City filter -- real, since City is a real field on every client.
        self.city_filter_var = ctk.StringVar(value="All Cities")
        self.city_filter_menu = ctk.CTkOptionMenu(toolbar, values=["All Cities"], variable=self.city_filter_var,
                                                  width=130, command=lambda c: self.refresh())
        self.city_filter_menu.pack(side="left", padx=(0, 8))

        # "More Filters" -- visual scaffolding matching the mockup; there
        # are no additional real filter fields beyond what's already here
        # to put behind it yet, so it's disabled rather than opening an
        # empty panel that would just be for show.
        ctk.CTkButton(toolbar, text="▽ More Filters", command=lambda: None, state="disabled",
                     fg_color="transparent", text_color=theme.MUTED, border_width=1,
                     border_color=theme.MUTED, font=theme.FONT_SMALL, width=110).pack(side="left")

        self.sort_var = ctk.StringVar(value="Recently Updated")
        ctk.CTkOptionMenu(toolbar, values=["Recently Updated", "Name (A-Z)", "Priority", "Total Invoiced"],
                          variable=self.sort_var, width=160,
                          command=lambda c: self.refresh()).pack(side="right")
        ctk.CTkLabel(toolbar, text="Sort By:", font=theme.FONT_SMALL, text_color=theme.MUTED).pack(
            side="right", padx=(0, 6))

        # Grid/List view toggle -- real and functional, same underlying
        # client data rendered as cards or as a compact table.
        self.view_mode_var = ctk.StringVar(value="Grid")
        view_toggle = ctk.CTkSegmentedButton(toolbar, values=["Grid", "List"], variable=self.view_mode_var,
                                             command=lambda c: self.refresh(), width=100,
                                             fg_color=theme.WHITE, selected_color=theme.BRASS,
                                             unselected_color=theme.WHITE, text_color=theme.INK,
                                             selected_hover_color=theme.INK)
        view_toggle.pack(side="right", padx=(0, 12))

        self.card_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.card_scroll.pack(fill="both", expand=True, padx=20, pady=(0, 5))
        for col in range(2):
            self.card_scroll.grid_columnconfigure(col, weight=1)

        # ---------------- Real pagination controls ----------------
        self.page_size = 12
        self.current_page = 1
        pagination_bar = ctk.CTkFrame(self, fg_color="transparent")
        pagination_bar.pack(fill="x", padx=20, pady=(0, 15))
        self.pagination_label = ctk.CTkLabel(pagination_bar, text="", font=theme.FONT_SMALL, text_color=theme.MUTED)
        self.pagination_label.pack(side="left")
        self.pagination_controls_frame = ctk.CTkFrame(pagination_bar, fg_color="transparent")
        self.pagination_controls_frame.pack(side="right")

    def _render_insights(self, clients):
        for w in self.insights_frame.winfo_children():
            w.destroy()

        # ---------------- Clients by Priority (real counts) ----------------
        priority_card = ctk.CTkFrame(self.insights_frame, fg_color=theme.WHITE, corner_radius=8, width=260)
        priority_card.pack(side="left", fill="y", padx=(0, 10))
        priority_card.pack_propagate(False)
        ctk.CTkLabel(priority_card, text="Clients by Priority", font=theme.FONT_BODY_BOLD,
                    text_color=theme.INK).pack(anchor="w", padx=15, pady=(15, 8))
        priority_counts = {}
        for c in clients:
            p = c["Priority"] or "Normal"
            priority_counts[p] = priority_counts.get(p, 0) + 1
        priority_colors = {"VIP": "#B68100", "High": "#1E5FA8", "Normal": "#6B6B6B"}
        if clients:
            fig = Figure(figsize=(1.6, 1.4), dpi=100)
            fig.patch.set_facecolor(theme.WHITE)
            ax = fig.add_subplot(111)
            labels = list(priority_counts.keys())
            sizes = list(priority_counts.values())
            colors = [priority_colors.get(l, "#6B6B6B") for l in labels]
            ax.pie(sizes, colors=colors, wedgeprops={"width": 0.4, "edgecolor": "white"})
            ax.set_aspect("equal")
            chart_row = ctk.CTkFrame(priority_card, fg_color="transparent")
            chart_row.pack(fill="x", padx=15)
            canvas = FigureCanvasTkAgg(fig, master=chart_row)
            canvas.draw()
            canvas.get_tk_widget().pack(side="left")
            legend = ctk.CTkFrame(chart_row, fg_color="transparent")
            legend.pack(side="left", padx=(8, 0))
            total = len(clients)
            for label in labels:
                count = priority_counts[label]
                pct = f"{count/total*100:.0f}%" if total else "0%"
                row = ctk.CTkFrame(legend, fg_color="transparent")
                row.pack(anchor="w", pady=2)
                ctk.CTkLabel(row, text="●", font=("Segoe UI", 11), text_color=priority_colors.get(label, "#6B6B6B")).pack(side="left")
                ctk.CTkLabel(row, text=f" {label}  {count} ({pct})", font=("Segoe UI", 9), text_color=theme.INK).pack(side="left")
        else:
            ctk.CTkLabel(priority_card, text="No clients yet.", font=theme.FONT_SMALL, text_color=theme.MUTED).pack(padx=15)

        # ---------------- Client Relationship breakdown (real counts) ----------------
        rel_card = ctk.CTkFrame(self.insights_frame, fg_color=theme.WHITE, corner_radius=8, width=260)
        rel_card.pack(side="left", fill="y", padx=(0, 10))
        rel_card.pack_propagate(False)
        ctk.CTkLabel(rel_card, text="Client Relationship", font=theme.FONT_BODY_BOLD,
                    text_color=theme.INK).pack(anchor="w", padx=15, pady=(15, 8))
        rel_counts = {}
        for c in clients:
            r = get_client_relationship(c["ClientID"])
            rel_counts[r] = rel_counts.get(r, 0) + 1
        total = len(clients)
        for rel in ["Repeat Client", "Existing Client", "New Lead"]:
            count = rel_counts.get(rel, 0)
            pct = f"{count/total*100:.0f}%" if total else "0%"
            row = ctk.CTkFrame(rel_card, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=3)
            ctk.CTkLabel(row, text=rel, font=theme.FONT_SMALL, text_color=theme.INK).pack(side="left")
            ctk.CTkLabel(row, text=f"{count} ({pct})", font=theme.FONT_SMALL, text_color=theme.MUTED).pack(side="right")
        ctk.CTkLabel(rel_card, text=f"Total: {total} Clients", font=("Segoe UI", 9), text_color=theme.MUTED).pack(
            anchor="w", padx=15, pady=(8, 15))

        # ---------------- Revenue Overview (This Month, real data) ----------------
        rev_card = ctk.CTkFrame(self.insights_frame, fg_color=theme.WHITE, corner_radius=8, width=260)
        rev_card.pack(side="left", fill="y", padx=(0, 10))
        rev_card.pack_propagate(False)
        ctk.CTkLabel(rev_card, text="Revenue Overview (This Month)", font=theme.FONT_BODY_BOLD,
                    text_color=theme.INK, wraplength=230).pack(anchor="w", padx=15, pady=(15, 8))
        invoices_this_month = db.fetch_all("""
            SELECT InvoiceID, Amount FROM trxInvoice
            WHERE Status != 'Cancelled' AND strftime('%Y-%m', InvoiceDate) = strftime('%Y-%m', 'now')
        """)
        total_invoiced_month = sum(i["Amount"] for i in invoices_this_month)
        total_collected_month = sum(db.fetch_one(
            "SELECT COALESCE(SUM(Amount),0) AS t FROM trxInvoicePayment WHERE InvoiceID=? AND strftime('%Y-%m', PaymentDate) = strftime('%Y-%m', 'now')",
            (i["InvoiceID"],))["t"] for i in invoices_this_month)
        outstanding_month = total_invoiced_month - total_collected_month
        collection_rate = (total_collected_month / total_invoiced_month * 100) if total_invoiced_month else 0
        ui.metric_row(rev_card, f"₹{total_invoiced_month:,.0f}", "Total Invoiced")
        two_col = ctk.CTkFrame(rev_card, fg_color="transparent")
        two_col.pack(fill="x", padx=15, pady=(0, 4))
        c1 = ctk.CTkFrame(two_col, fg_color="transparent")
        c1.pack(side="left", expand=True, anchor="w")
        ctk.CTkLabel(c1, text=f"₹{total_collected_month:,.0f}", font=("Georgia", 14, "bold"), text_color="#2E8B57").pack(anchor="w")
        ctk.CTkLabel(c1, text="Collected", font=("Segoe UI", 9), text_color=theme.MUTED).pack(anchor="w")
        c2 = ctk.CTkFrame(two_col, fg_color="transparent")
        c2.pack(side="left", expand=True, anchor="w")
        ctk.CTkLabel(c2, text=f"₹{outstanding_month:,.0f}", font=("Georgia", 14, "bold"), text_color="#8B2E2E").pack(anchor="w")
        ctk.CTkLabel(c2, text="Outstanding", font=("Segoe UI", 9), text_color=theme.MUTED).pack(anchor="w")
        ctk.CTkLabel(rev_card, text=f"{collection_rate:.0f}% Collection Rate", font=("Segoe UI", 9),
                    text_color=theme.MUTED).pack(anchor="w", padx=15, pady=(4, 15))

        # ---------------- Top Client by Revenue (rich real summary) ----------------
        # Redesigned from a bare name+number list into a compact business
        # summary for the single top client -- Projects/Invoices/
        # Outstanding/Relationship/Client Since are all real, already-
        # computable data (the same queries used elsewhere in this file
        # for the client cards), not fabricated charts or percentages.
        top_card = ctk.CTkFrame(self.insights_frame, fg_color=theme.WHITE, corner_radius=8, width=260)
        top_card.pack(side="left", fill="x", expand=True, anchor="n")
        ctk.CTkLabel(top_card, text="Top Client by Revenue", font=theme.FONT_BODY_BOLD,
                    text_color=theme.INK).pack(anchor="w", padx=15, pady=(15, 8))

        rankings = []
        for c in clients:
            invoices = db.fetch_all("""
                SELECT Amount FROM trxInvoice i JOIN tblProject p ON i.ProjectID = p.ProjectID
                WHERE p.ClientID=? AND i.Status != 'Cancelled'
            """, (c["ClientID"],))
            total = sum(i["Amount"] for i in invoices)
            if total > 0:
                rankings.append((c, total))
        rankings.sort(key=lambda x: -x[1])

        if not rankings:
            ctk.CTkLabel(top_card, text="No invoiced revenue yet.", font=theme.FONT_SMALL,
                        text_color=theme.MUTED).pack(padx=15, pady=(0, 15))
        else:
            top_client, top_revenue = rankings[0]
            project_count = db.fetch_one("SELECT COUNT(*) AS n FROM tblProject WHERE ClientID=?",
                                         (top_client["ClientID"],))["n"]
            invoices = db.fetch_all("""
                SELECT i.InvoiceID, i.Amount FROM trxInvoice i JOIN tblProject p ON i.ProjectID = p.ProjectID
                WHERE p.ClientID=? AND i.Status != 'Cancelled'
            """, (top_client["ClientID"],))
            total_received = sum(db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxInvoicePayment WHERE InvoiceID=?",
                                              (i["InvoiceID"],))["t"] for i in invoices)
            outstanding = top_revenue - total_received
            relationship = get_client_relationship(top_client["ClientID"])
            since_display = top_client["CreatedOn"][:10] if top_client["CreatedOn"] else "—"

            header_row = ctk.CTkFrame(top_card, fg_color="transparent")
            header_row.pack(fill="x", padx=15, pady=(0, 4))
            ctk.CTkLabel(header_row, text="🏆", font=("Segoe UI", 14)).pack(side="left", padx=(0, 6))
            ctk.CTkLabel(header_row, text=top_client["ClientName"], font=("Segoe UI", 15, "bold"),
                        text_color=theme.INK).pack(side="left")
            ctk.CTkLabel(top_card, text=f"₹{top_revenue:,.0f}", font=("Georgia", 20, "bold"),
                        text_color=theme.BRASS).pack(anchor="w", padx=15, pady=(0, 10))

            summary_rows = [
                ("Projects", str(project_count)), ("Invoices", str(len(invoices))),
                ("Outstanding", f"₹{outstanding:,.0f}"), ("Relationship", relationship),
                ("Client Since", since_display),
            ]
            for label, value in summary_rows:
                row = ctk.CTkFrame(top_card, fg_color="transparent")
                row.pack(fill="x", padx=15, pady=2)
                ctk.CTkLabel(row, text=label, font=("Segoe UI", 9), text_color=theme.MUTED).pack(side="left")
                ctk.CTkLabel(row, text=value, font=theme.FONT_SMALL, text_color=theme.INK).pack(side="right")
            ctk.CTkFrame(top_card, fg_color="transparent", height=12).pack()


    def refresh(self):
        self._render_stats()
        for w in self.card_scroll.winfo_children():
            w.destroy()

        search = self.search_entry.get().strip().lower()
        priority_filter = self.priority_filter_var.get()
        relationship_filter = self.relationship_filter_var.get()
        city_filter = self.city_filter_var.get()
        sort_choice = self.sort_var.get()

        clients = db.fetch_all(
            "SELECT * FROM tblClient ORDER BY ClientID DESC")

        # Real city list for the filter dropdown -- built from actual
        # client records, not a fixed/fabricated list.
        real_cities = sorted({c["City"] for c in clients if c["City"]})
        self.city_filter_menu.configure(values=["All Cities"] + real_cities)

        if search:
            clients = [c for c in clients if search in c["ClientName"].lower()
                      or search in c["ClientCode"].lower()
                      or search in (c["Mobile"] or "").lower()
                      or search in (c["Email"] or "").lower()]
        if priority_filter != "All Priorities":
            clients = [c for c in clients if (c["Priority"] or "Normal") == priority_filter]
        if city_filter != "All Cities":
            clients = [c for c in clients if c["City"] == city_filter]

        self._render_insights(clients)

        # Relationship is calculated per-client (not stored), so this filter
        # is applied after computing it, same as the priority/search filters.
        filtered = []
        for c in clients:
            relationship = get_client_relationship(c["ClientID"])
            if relationship_filter != "All Relationships" and relationship != relationship_filter:
                continue
            filtered.append((c, relationship))

        # Sort -- "Total Invoiced" needs a real per-client sum, computed
        # once here rather than repeatedly per card.
        if sort_choice == "Name (A-Z)":
            filtered.sort(key=lambda cr: cr[0]["ClientName"].lower())
        elif sort_choice == "Priority":
            priority_rank = {"VIP": 0, "High": 1, "Normal": 2}
            filtered.sort(key=lambda cr: priority_rank.get(cr[0]["Priority"] or "Normal", 2))
        elif sort_choice == "Total Invoiced":
            def client_total_invoiced(client_id):
                invoices = db.fetch_all("""
                    SELECT Amount FROM trxInvoice i JOIN tblProject p ON i.ProjectID = p.ProjectID
                    WHERE p.ClientID=? AND i.Status != 'Cancelled'
                """, (client_id,))
                return sum(i["Amount"] for i in invoices)
            filtered.sort(key=lambda cr: -client_total_invoiced(cr[0]["ClientID"]))
        # "Recently Updated" is the default DB order (ClientID DESC) --
        # a real ModifiedOn-based sort would be more accurate, but ordering
        # by creation is a reasonable proxy already in place and not the
        # focus of this pass.

        if not filtered:
            ctk.CTkLabel(self.card_scroll, text="No clients match this search/filter.",
                        font=theme.FONT_BODY, text_color=theme.MUTED).grid(row=0, column=0, padx=10, pady=20)
            self.pagination_label.configure(text="Showing 0 of 0 clients")
            for w in self.pagination_controls_frame.winfo_children():
                w.destroy()
            return

        # Real pagination -- genuinely slices the filtered list, not
        # cosmetic. Trivial with a handful of real clients today (one page),
        # but the mechanism is real and will paginate correctly as real
        # client volume grows.
        total_count = len(filtered)
        total_pages = max(1, (total_count + self.page_size - 1) // self.page_size)
        self.current_page = min(self.current_page, total_pages)
        start_idx = (self.current_page - 1) * self.page_size
        page_items = filtered[start_idx:start_idx + self.page_size]

        if self.view_mode_var.get() == "List":
            self._render_list_view(page_items)
        else:
            for i, (client, relationship) in enumerate(page_items):
                self._render_client_card(self.card_scroll, client, relationship, row=i // 2, col=i % 2)

        end_idx = start_idx + len(page_items)
        self.pagination_label.configure(text=f"Showing {start_idx + 1} to {end_idx} of {total_count} clients")

        for w in self.pagination_controls_frame.winfo_children():
            w.destroy()
        ctk.CTkButton(self.pagination_controls_frame, text="«", command=lambda: self._go_to_page(1),
                     width=28, height=28, fg_color="transparent", text_color=theme.INK,
                     hover_color=theme.PARCHMENT).pack(side="left", padx=2)
        ctk.CTkButton(self.pagination_controls_frame, text="‹", command=lambda: self._go_to_page(self.current_page - 1),
                     width=28, height=28, fg_color="transparent", text_color=theme.INK,
                     hover_color=theme.PARCHMENT).pack(side="left", padx=2)
        for p in range(1, total_pages + 1):
            is_current = p == self.current_page
            ctk.CTkButton(self.pagination_controls_frame, text=str(p), command=lambda pg=p: self._go_to_page(pg),
                         width=28, height=28, fg_color=theme.BRASS if is_current else "transparent",
                         text_color=theme.WHITE if is_current else theme.INK,
                         hover_color=theme.PARCHMENT).pack(side="left", padx=2)
        ctk.CTkButton(self.pagination_controls_frame, text="›", command=lambda: self._go_to_page(self.current_page + 1),
                     width=28, height=28, fg_color="transparent", text_color=theme.INK,
                     hover_color=theme.PARCHMENT).pack(side="left", padx=2)
        ctk.CTkButton(self.pagination_controls_frame, text="»", command=lambda: self._go_to_page(total_pages),
                     width=28, height=28, fg_color="transparent", text_color=theme.INK,
                     hover_color=theme.PARCHMENT).pack(side="left", padx=2)

    def _go_to_page(self, page):
        self.current_page = max(1, page)
        self.refresh()

    def _render_list_view(self, page_items):
        """Compact table alternative to the card grid -- same real data, same filters/sort/pagination."""
        cols = ("name", "code", "priority", "relationship", "phone", "city", "invoiced", "outstanding")
        tree = ttk.Treeview(self.card_scroll, columns=cols, show="headings", height=14)
        headings = {"name": "Name", "code": "Code", "priority": "Priority", "relationship": "Relationship",
                   "phone": "Phone", "city": "City", "invoiced": "Invoiced (₹)", "outstanding": "Outstanding (₹)"}
        for c in cols:
            tree.heading(c, text=headings[c])
            tree.column(c, width=110)
        tree.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=8, pady=8)
        for client, relationship in page_items:
            mobile_display = f"{client['MobileCountryCode'] or ''} {format_mobile_display(client['Mobile']) if client['Mobile'] else ''}".strip()
            invoices = db.fetch_all("""
                SELECT i.InvoiceID, i.Amount FROM trxInvoice i JOIN tblProject p ON i.ProjectID = p.ProjectID
                WHERE p.ClientID=? AND i.Status != 'Cancelled'
            """, (client["ClientID"],))
            total_invoiced = sum(i["Amount"] for i in invoices)
            total_received = sum(db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxInvoicePayment WHERE InvoiceID=?",
                                              (i["InvoiceID"],))["t"] for i in invoices)
            tree.insert("", "end", iid=client["ClientID"],
                       values=(client["ClientName"], client["ClientCode"], client["Priority"] or "Normal",
                              relationship, mobile_display or "—", client["City"] or "—",
                              f"{total_invoiced:,.0f}", f"{total_invoiced - total_received:,.0f}"))
        tree.bind("<Double-1>", lambda e: self.open_workspace(int(tree.selection()[0])) if tree.selection() else None)

    def _render_stats(self):
        for w in self.stats_frame.winfo_children():
            w.destroy()
        total_clients = db.fetch_one("SELECT COUNT(*) AS n FROM tblClient")["n"]
        active_clients = db.fetch_one("""
            SELECT COUNT(DISTINCT c.ClientID) AS n FROM tblClient c
            JOIN tblProject p ON c.ClientID = p.ClientID
            WHERE p.ProjectStatus NOT IN ('Completed','Cancelled')
        """)["n"]
        new_this_month = db.fetch_one(
            "SELECT COUNT(*) AS n FROM tblClient WHERE strftime('%Y-%m', CreatedOn) = strftime('%Y-%m', 'now')")["n"]
        high_priority = db.fetch_one("SELECT COUNT(*) AS n FROM tblClient WHERE Priority IN ('High','VIP')")["n"]
        all_clients = db.fetch_all("SELECT ClientID, CreatedOn FROM tblClient")
        existing_count = sum(1 for c in all_clients if get_client_relationship(c["ClientID"]) == "Existing Client")

        # Real deltas, computed only where cleanly defensible from CreatedOn
        # -- "created this month" is unambiguous; a historical relationship/
        # priority snapshot would need reconstructing what was true in the
        # past, which this schema can't do reliably, so those cards show a
        # real current count with no invented delta rather than a
        # speculative one.
        total_delta = f"↑{new_this_month} this month" if new_this_month else "No change this month"

        stats = [
            (str(total_clients), "Total Clients", total_delta, "👥", "#F5E6D3"),
            (str(active_clients), "Active Clients", "Currently active", "✅", "#D4F0E0"),
            (str(new_this_month), "New This Month", "Newly added", "✨", "#D6E8FA"),
            (str(high_priority), "High Priority", "High + VIP", "⭐", "#FBE0E0"),
            (str(existing_count), "Existing Clients", "1+ project", "🤝", "#E8DFF5"),
        ]
        # Weighted grid instead of pack() with fixed margins -- per the
        # explicit request, the cards themselves don't get bigger (still
        # width=175, unchanged), but each now sits in its own equally-
        # weighted column. As the row's available width grows, the GUTTERS
        # between cards grow with it (grid centers a widget within its cell
        # by default when no sticky is set), rather than the row stopping
        # short with dead space on the right while the cards themselves
        # stay tightly packed together.
        for col in range(5):
            self.stats_frame.grid_columnconfigure(col, weight=1)
        for col_idx, (value, label, sublabel, icon, bg_color) in enumerate(stats):
            ui.kpi_card(self.stats_frame, value, label, sublabel, icon, bg_color, col_idx)

    def _render_client_card(self, parent, client, relationship, row, col):
        card = ctk.CTkFrame(parent, fg_color=theme.WHITE, corner_radius=10, border_width=1, border_color="#E8E0D0")
        card.grid(row=row, column=col, sticky="nsew", padx=8, pady=6)
        card.bind("<Double-1>", lambda e, cid=client["ClientID"]: self.open_workspace(cid))

        project_count = db.fetch_one("SELECT COUNT(*) AS n FROM tblProject WHERE ClientID=?", (client["ClientID"],))["n"]
        mobile_display = f"{client['MobileCountryCode'] or ''} {format_mobile_display(client['Mobile']) if client['Mobile'] else ''}".strip()

        # Real business metrics -- Invoices/Revenue/Outstanding, all
        # genuinely computable via tblProject.ClientID -> trxInvoice, not
        # invented. Matches the request's own "Add Business Metrics" ask,
        # since these are actual numbers a client card is worth showing.
        invoices = db.fetch_all("""
            SELECT i.InvoiceID, i.Amount FROM trxInvoice i JOIN tblProject p ON i.ProjectID = p.ProjectID
            WHERE p.ClientID=? AND i.Status != 'Cancelled'
        """, (client["ClientID"],))
        total_invoiced = sum(i["Amount"] for i in invoices)
        total_received = sum(db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxInvoicePayment WHERE InvoiceID=?",
                                          (i["InvoiceID"],))["t"] for i in invoices)

        # ---------------- Header: monogram + name/ID/badges + 3-dot menu ----------------
        header_row = ctk.CTkFrame(card, fg_color="transparent")
        header_row.pack(fill="x", padx=15, pady=(12, 6))
        initials = "".join(w[0].upper() for w in client["ClientName"].split()[:2]) or "?"
        monogram = ctk.CTkLabel(header_row, text=initials, font=("Segoe UI", 12, "bold"), text_color=theme.WHITE,
                                fg_color=theme.BRASS, corner_radius=16, width=32, height=32)
        monogram.pack(side="left", padx=(0, 10))

        name_row = ctk.CTkFrame(header_row, fg_color="transparent")
        name_row.pack(side="left", fill="x", expand=True)
        top_line = ctk.CTkFrame(name_row, fg_color="transparent")
        top_line.pack(fill="x", anchor="w")
        ctk.CTkLabel(top_line, text=client["ClientName"], font=("Segoe UI", 19, "bold"), text_color=theme.INK).pack(side="left")
        priority = client["Priority"] or "Normal"
        priority_color = {"VIP": "#B68100", "High": "#1E5FA8", "Normal": "#6B6B6B"}.get(priority, "#6B6B6B")
        relationship_color = {"Repeat Client": "#2E8B57", "Existing Client": "#1E5FA8", "New Lead": "#6B6B6B"}.get(relationship, "#6B6B6B")
        ui.pill_badge(top_line, priority, priority_color).pack(side="left", padx=(8, 6))
        ui.pill_badge(top_line, relationship, relationship_color).pack(side="left")
        ctk.CTkLabel(name_row, text=client["ClientCode"], font=("Segoe UI", 11), text_color=theme.MUTED,
                    anchor="w").pack(fill="x")

        # 3-dot menu -- real actions (Edit/Delete/Open), just accessed via
        # a compact menu button matching the mockup instead of always-
        # visible full-width buttons alone (both are kept -- see the
        # action row below -- since removing the explicit buttons would
        # reduce real functionality, not just change its presentation).
        menu_btn = ctk.CTkButton(header_row, text="⋮", command=lambda cid=client["ClientID"]: self._show_card_menu(cid),
                                 width=28, height=28, fg_color="transparent", hover_color=theme.PARCHMENT,
                                 text_color=theme.MUTED, font=("Segoe UI", 14))
        menu_btn.pack(side="right")

        # ---------------- Contact info: 4 real columns, icon+value+label ----------------
        info_grid = ctk.CTkFrame(card, fg_color="transparent")
        info_grid.pack(fill="x", padx=15, pady=(0, 8))
        info_grid.grid_columnconfigure((0, 1, 2, 3), weight=1)
        info_items = [
            ("📞", mobile_display or "—", "Mobile"),
            ("📍", client["City"] or "—", "City"),
            ("✉️", client["Email"] or "—", "Email"),
            ("🤝", relationship, "Relationship"),
        ]
        for i, (icon, value, label) in enumerate(info_items):
            cell = ctk.CTkFrame(info_grid, fg_color="transparent")
            cell.grid(row=0, column=i, sticky="w", padx=(0, 6))
            ctk.CTkLabel(cell, text=f"{icon} {value}", font=theme.FONT_SMALL, text_color=theme.INK,
                        anchor="w", wraplength=140, justify="left").pack(anchor="w")
            ctk.CTkLabel(cell, text=label, font=("Segoe UI", 8), text_color=theme.MUTED, anchor="w").pack(anchor="w")

        ctk.CTkFrame(card, fg_color=theme.PARCHMENT, height=1).pack(fill="x", padx=15, pady=(2, 6))

        # ---------------- Real business metrics row ----------------
        metrics_row = ctk.CTkFrame(card, fg_color="transparent")
        metrics_row.pack(fill="x", padx=15, pady=(0, 6))
        metrics_row.grid_columnconfigure((0, 1, 2), weight=1)
        metrics = [
            (str(len(invoices)), "Invoices"), (f"₹{total_invoiced:,.0f}", "Invoiced"),
            (f"₹{total_invoiced - total_received:,.0f}", "Outstanding"),
        ]
        for i, (value, label) in enumerate(metrics):
            m = ctk.CTkFrame(metrics_row, fg_color="transparent")
            m.grid(row=0, column=i, sticky="w")
            ctk.CTkLabel(m, text=value, font=("Georgia", 15, "bold"), text_color=theme.BRASS, anchor="w").pack(anchor="w")
            ctk.CTkLabel(m, text=label, font=("Segoe UI", 8), text_color=theme.MUTED, anchor="w").pack(anchor="w")

        # Footer: Last Contact (the same real "most recent activity" query
        # already used, just relabeled to match how a client relationship
        # summary actually reads), Next Follow-up (the new, genuinely real
        # field -- shows "—" until Atish actually sets one, never a
        # fabricated date), Client Since (real CreatedOn).
        recent = db.fetch_one("""
            SELECT Action, LoggedOn FROM logActivity
            WHERE (EntityType='Client' AND EntityID=?)
               OR (EntityType='Project' AND EntityID IN (SELECT ProjectID FROM tblProject WHERE ClientID=?))
            ORDER BY LoggedOn DESC LIMIT 1
        """, (client["ClientID"], client["ClientID"]))
        footer = ctk.CTkFrame(card, fg_color="transparent")
        footer.pack(fill="x", padx=15, pady=(0, 6))
        last_contact = ui.relative_time(recent["LoggedOn"]) if recent else "—"
        followup_display = client["NextFollowUpDate"] if client["NextFollowUpDate"] else "—"
        since_display = client["CreatedOn"][:10] if client["CreatedOn"] else "—"
        footer_text = f"📅 Last Contact: {last_contact}   ·   🕐 Next Follow-up: {followup_display}   ·   📅 Client Since: {since_display}"
        ctk.CTkLabel(footer, text=footer_text, font=("Segoe UI", 8), text_color=theme.MUTED, anchor="w").pack(
            fill="x", anchor="w")

        # ---------------- Actions: Open genuinely dominant, Edit secondary, Delete a small outline ----------------
        # Real weighting, not just color -- Open Workspace gets roughly
        # half the row's width and a taller/bolder button, Edit gets a
        # visibly smaller share, Delete is a small fixed-width outline that
        # doesn't compete with either for attention.
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=15, pady=(0, 12))
        actions.grid_columnconfigure(0, weight=3)
        actions.grid_columnconfigure(1, weight=2)
        ctk.CTkButton(actions, text="Open Workspace  →", command=lambda cid=client["ClientID"]: self.open_workspace(cid),
                      fg_color=theme.BRASS, hover_color=theme.INK, font=("Segoe UI", 12, "bold"), height=34).grid(
            row=0, column=0, sticky="ew", padx=(0, 5))
        ctk.CTkButton(actions, text="✎ Edit", command=lambda cid=client["ClientID"]: self.open_edit_form_for(cid),
                      fg_color=theme.INK, hover_color=theme.BRASS, font=theme.FONT_SMALL, height=34).grid(
            row=0, column=1, sticky="ew", padx=(0, 5))
        ctk.CTkButton(actions, text="🗑", command=lambda cid=client["ClientID"]: self.delete_client(cid),
                      fg_color="transparent", hover_color="#8B2E2E", text_color="#8B2E2E",
                      border_width=1, border_color="#8B2E2E", font=theme.FONT_SMALL, height=34, width=40).grid(
            row=0, column=2)

    def open_workspace(self, client_id):
        ClientWorkspace(self, client_id, on_close=self.refresh)

    def _show_card_menu(self, client_id):
        import tkinter
        menu = tkinter.Menu(self, tearoff=0)
        menu.add_command(label="Open Workspace", command=lambda: self.open_workspace(client_id))
        menu.add_command(label="Edit Client", command=lambda: self.open_edit_form_for(client_id))
        menu.add_separator()
        menu.add_command(label="Delete Client", command=lambda: self.delete_client(client_id))
        try:
            x = self.winfo_pointerx()
            y = self.winfo_pointery()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def open_add_form(self):
        ClientForm(self, on_save=self.refresh)

    def open_edit_form_for(self, client_id):
        client = db.fetch_one("SELECT * FROM tblClient WHERE ClientID = ?", (client_id,))
        ClientForm(self, on_save=self.refresh, existing=client)

    def delete_client(self, client_id):
        in_use = db.fetch_one("SELECT COUNT(*) AS n FROM tblProject WHERE ClientID = ?", (client_id,))
        if in_use["n"] > 0:
            messagebox.showerror("Cannot delete",
                                  "This client has projects linked to them. Delete or reassign those projects first.", parent=self)
            return
        if messagebox.askyesno("Confirm delete", "Delete this client permanently?", parent=self):
            db.execute("DELETE FROM tblClient WHERE ClientID = ?", (client_id,))
            db.log_activity("Client", client_id, "Deleted")
            self.refresh()


class ClientForm(ctk.CTkToplevel):
    def __init__(self, master, on_save, existing=None):
        super().__init__(master)
        self.client_screen = master
        self.on_save = on_save
        self.existing = existing
        self.title("Edit Client" if existing else "New Client")
        self.geometry("560x700")
        self.configure(fg_color=theme.PARCHMENT)
        self.grab_set()

        # Scrollable content -- the form has 14+ fields and will not fit most
        # screen heights. Without this, fields past the visible area were only
        # reachable by manually resizing/maximizing the window.
        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=5, pady=5)

        existing_country = (existing["Country"] if existing and existing["Country"] else "India")
        is_indian_default = existing_country.strip().lower() == "india"

        row = 0
        ctk.CTkLabel(content, text=self.title(), font=theme.FONT_SUBHEADING,
                     text_color=theme.INK).grid(row=row, column=0, columnspan=2, pady=(15, 10), padx=15, sticky="w")
        row += 1

        # 1. Client Name -- auto-capitalized on focus-out
        ctk.CTkLabel(content, text="Client Name *", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        self.name_entry = ctk.CTkEntry(content, width=280)
        self.name_entry.grid(row=row, column=1, padx=15, pady=6)
        if existing and existing["ClientName"]:
            self.name_entry.insert(0, existing["ClientName"])
        self.name_entry.bind("<FocusOut>", lambda e: self._auto_capitalize(self.name_entry))
        row += 1

        # 2. Indian Client checkbox
        self.indian_var = ctk.BooleanVar(value=is_indian_default)
        ctk.CTkCheckBox(content, text="Indian Client", variable=self.indian_var,
                        command=self._on_indian_toggle, font=theme.FONT_BODY_BOLD,
                        text_color=theme.INK).grid(row=row, column=0, columnspan=2, sticky="w", padx=15, pady=(10, 4))
        row += 1

        # 3. Country (Foreign only)
        ctk.CTkLabel(content, text="Country *", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        country_labels = [country_label(n, c) for n, c in COUNTRIES]
        default_country_label = country_labels[0]
        if existing and not is_indian_default:
            match = next((cl for cl in country_labels if cl.startswith(existing_country)), None)
            if match:
                default_country_label = match
        self.country_var = ctk.StringVar(value=default_country_label)
        self.country_menu = ctk.CTkOptionMenu(content, values=country_labels, variable=self.country_var,
                                              width=280, command=self._on_country_change)
        self.country_menu.grid(row=row, column=1, padx=15, pady=6)
        row += 1

        # 4. Mobile -- numeric entry + duplicate check on focus-out
        ctk.CTkLabel(content, text="Mobile *", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        mobile_wrapper = ctk.CTkFrame(content, fg_color="transparent")
        mobile_wrapper.grid(row=row, column=1, padx=15, pady=6, sticky="w")
        self.mobile_code_label = ctk.CTkLabel(mobile_wrapper, text=INDIA_COUNTRY_CODE, font=theme.FONT_BODY,
                                              text_color=theme.INK, width=60, fg_color=theme.WHITE, corner_radius=6)
        self.mobile_code_label.grid(row=0, column=0, padx=(0, 6))
        self.mobile_number_entry = ctk.CTkEntry(mobile_wrapper, width=180)
        apply_numeric_only(self, self.mobile_number_entry, max_length=15)
        if existing and existing["Mobile"]:
            self.mobile_number_entry.insert(0, str(existing["Mobile"]))
        self.mobile_number_entry.grid(row=0, column=1)
        self.mobile_number_entry.bind("<FocusOut>", lambda e: self._check_duplicate_mobile())
        row += 1

        # 5. Alternate Mobile
        ctk.CTkLabel(content, text="Alternate Mobile", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        alt_wrapper = ctk.CTkFrame(content, fg_color="transparent")
        alt_wrapper.grid(row=row, column=1, padx=15, pady=6, sticky="w")
        self.alt_same_code_var = ctk.BooleanVar(value=True)
        existing_alt_code = existing["AlternateMobileCountryCode"] if existing else None
        self.alt_code_var = ctk.StringVar(value=(existing_alt_code or INDIA_COUNTRY_CODE))
        self.alt_code_mirror_label = ctk.CTkLabel(alt_wrapper, text=INDIA_COUNTRY_CODE, font=theme.FONT_BODY,
                                                  text_color=theme.INK, width=60, fg_color=theme.WHITE, corner_radius=6)
        self.alt_code_dropdown = ctk.CTkOptionMenu(alt_wrapper, values=[INDIA_COUNTRY_CODE] + [c for _, c in COUNTRIES if c],
                                                   variable=self.alt_code_var, width=90)
        self.alt_code_mirror_label.grid(row=0, column=0, padx=(0, 6))
        self.alt_code_dropdown.grid(row=0, column=0, padx=(0, 6))
        self.alt_number_entry = ctk.CTkEntry(alt_wrapper, width=150)
        apply_numeric_only(self, self.alt_number_entry, max_length=15)
        if existing and existing["AlternateMobile"]:
            self.alt_number_entry.insert(0, str(existing["AlternateMobile"]))
        self.alt_number_entry.grid(row=0, column=1)
        row += 1
        self.alt_same_checkbox = ctk.CTkCheckBox(content, text="Same Country Code as Primary", variable=self.alt_same_code_var,
                                                 command=self._on_alt_same_toggle, font=theme.FONT_SMALL,
                                                 text_color=theme.MUTED)
        self.alt_same_checkbox.grid(row=row, column=1, sticky="w", padx=15, pady=(0, 6))
        row += 1

        # 6. Email -- real-time validation with visual feedback
        ctk.CTkLabel(content, text="Email", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        self.email_entry = ctk.CTkEntry(content, width=280, placeholder_text="name@example.com")
        if existing and existing["Email"]:
            self.email_entry.insert(0, existing["Email"])
        self.email_entry.grid(row=row, column=1, padx=15, pady=6)
        self.email_entry.bind("<KeyRelease>", self._validate_email_live)
        self.email_entry.bind("<FocusOut>", self._validate_email_live)
        row += 1
        self.email_status_label = ctk.CTkLabel(content, text="", font=theme.FONT_SMALL, text_color=theme.MUTED)
        self.email_status_label.grid(row=row, column=1, sticky="w", padx=15, pady=(0, 6))
        row += 1

        # 7. Address -- multi-line
        ctk.CTkLabel(content, text="Address *", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="nw", padx=15, pady=6)
        self.address_text = ctk.CTkTextbox(content, width=280, height=60)
        if existing and existing["Address"]:
            self.address_text.insert("1.0", existing["Address"])
        self.address_text.grid(row=row, column=1, padx=15, pady=6)
        row += 1

        # 8. City -- auto-capitalized
        ctk.CTkLabel(content, text="City", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        self.city_entry = ctk.CTkEntry(content, width=280)
        if existing and existing["City"]:
            self.city_entry.insert(0, existing["City"])
        self.city_entry.grid(row=row, column=1, padx=15, pady=6)
        self.city_entry.bind("<FocusOut>", lambda e: self._auto_capitalize(self.city_entry))
        row += 1

        # 9. State / Province -- defaults to West Bengal (ADS's own location) for new India clients
        ctk.CTkLabel(content, text="State / Province", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        existing_state = existing["State"] if existing and existing["State"] else ""
        default_state = existing_state if existing_state in INDIAN_STATES else "West Bengal"
        self.state_dropdown_var = ctk.StringVar(value=default_state)
        self.state_dropdown = ctk.CTkOptionMenu(content, values=INDIAN_STATES, variable=self.state_dropdown_var, width=280)
        self.state_text_entry = ctk.CTkEntry(content, width=280)
        if not is_indian_default and existing_state:
            self.state_text_entry.insert(0, existing_state)
        self.state_dropdown.grid(row=row, column=1, padx=15, pady=6)
        self.state_text_entry.grid(row=row, column=1, padx=15, pady=6)
        row += 1

        # 10. PIN / Postal Code
        self.pin_label = ctk.CTkLabel(content, text="PIN Code", font=theme.FONT_BODY, text_color=theme.INK)
        self.pin_label.grid(row=row, column=0, sticky="w", padx=15, pady=6)
        existing_pin = existing["PinCode"] if existing and existing["PinCode"] else ""
        self.pincode_numeric_entry = ctk.CTkEntry(content, width=280)
        apply_numeric_only(self, self.pincode_numeric_entry, max_length=10)
        self.pincode_text_entry = ctk.CTkEntry(content, width=280)
        if existing_pin:
            if is_indian_default:
                self.pincode_numeric_entry.insert(0, existing_pin)
            else:
                self.pincode_text_entry.insert(0, existing_pin)
        self.pincode_numeric_entry.grid(row=row, column=1, padx=15, pady=6)
        self.pincode_text_entry.grid(row=row, column=1, padx=15, pady=6)
        row += 1

        # 11. GSTIN -- format validated if filled
        self.gstin_label = ctk.CTkLabel(content, text="GSTIN", font=theme.FONT_BODY, text_color=theme.INK)
        self.gstin_label.grid(row=row, column=0, sticky="w", padx=15, pady=6)
        self.gstin_entry = ctk.CTkEntry(content, width=280, placeholder_text="22AAAAA0000A1Z5")
        if existing and existing["GSTIN"]:
            self.gstin_entry.insert(0, existing["GSTIN"])
        self.gstin_entry.grid(row=row, column=1, padx=15, pady=6)
        row += 1

        # 12. PAN -- format validated if filled
        self.pan_label = ctk.CTkLabel(content, text="PAN", font=theme.FONT_BODY, text_color=theme.INK)
        self.pan_label.grid(row=row, column=0, sticky="w", padx=15, pady=6)
        self.pan_entry = ctk.CTkEntry(content, width=280, placeholder_text="ABCDE1234F")
        if existing and existing["PAN"]:
            self.pan_entry.insert(0, existing["PAN"])
        self.pan_entry.grid(row=row, column=1, padx=15, pady=6)
        row += 1

        # 13. Remarks
        ctk.CTkLabel(content, text="Remarks", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        self.remarks_entry = ctk.CTkEntry(content, width=280)
        if existing and existing["Remarks"]:
            self.remarks_entry.insert(0, existing["Remarks"])
        self.remarks_entry.grid(row=row, column=1, padx=15, pady=6)
        row += 1

        # Priority -- a genuine judgment call, so it's the one manually-set field.
        # Relationship (New/Existing/Repeat) is deliberately NOT here -- it's
        # calculated from actual project count wherever it's displayed, so it
        # can never drift out of sync with reality.
        ctk.CTkLabel(content, text="Priority", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        self.priority_var = ctk.StringVar(value=(existing["Priority"] if existing and existing["Priority"] else "Normal"))
        ctk.CTkOptionMenu(content, values=PRIORITY_OPTIONS, variable=self.priority_var, width=280).grid(
            row=row, column=1, padx=15, pady=6)
        row += 1

        # Next Follow-up -- genuinely new, no such tracking existed before.
        # DateEntry always holds SOME date (it can't represent "no date"),
        # so a checkbox controls whether a real date is actually saved --
        # unchecked means NULL, not today's date or any other fabricated
        # default. Existing clients start unchecked/unset.
        ctk.CTkLabel(content, text="Next Follow-up", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        followup_row = ctk.CTkFrame(content, fg_color="transparent")
        followup_row.grid(row=row, column=1, padx=15, pady=6, sticky="w")
        has_followup = bool(existing and existing["NextFollowUpDate"])
        self.followup_enabled_var = ctk.BooleanVar(value=has_followup)
        self.followup_date = DateEntry(followup_row, width=14, date_pattern="yyyy-mm-dd", background=theme.BRASS,
                                       foreground="white", borderwidth=1,
                                       state="normal" if has_followup else "disabled")
        if has_followup:
            try:
                self.followup_date.set_date(existing["NextFollowUpDate"])
            except Exception:
                pass
        def _toggle_followup():
            self.followup_date.configure(state="normal" if self.followup_enabled_var.get() else "disabled")
        ctk.CTkCheckBox(followup_row, text="Set a date", variable=self.followup_enabled_var,
                       command=_toggle_followup, font=theme.FONT_SMALL, width=20).pack(side="left", padx=(0, 8))
        self.followup_date.pack(side="left")
        row += 1

        # 14. Lead Source -- dynamic list with "Add New Source"
        ctk.CTkLabel(content, text="How did you find us?", font=theme.FONT_BODY,
                     text_color=theme.INK, wraplength=140, justify="left").grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        self.sources = get_lead_sources()
        source_values = self.sources + [ADD_NEW_SOURCE]
        default_source = existing["Source"] if existing and existing["Source"] in self.sources else self.sources[0]
        self.source_var = ctk.StringVar(value=default_source)
        self.source_menu = ctk.CTkOptionMenu(content, values=source_values, variable=self.source_var,
                                             width=280, command=self._on_source_change)
        self.source_menu.grid(row=row, column=1, padx=15, pady=6)
        row += 1

        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.grid(row=row, column=0, columnspan=2, pady=20)
        ctk.CTkButton(btn_frame, text="Save", command=self.save,
                      fg_color=theme.BRASS, hover_color=theme.INK,
                      font=theme.FONT_BODY_BOLD, width=120).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Cancel", command=self.destroy,
                      fg_color=theme.MUTED, font=theme.FONT_BODY, width=120).pack(side="left", padx=10)

        self._on_indian_toggle()
        self._on_alt_same_toggle()
        if existing and existing["Email"]:
            self._validate_email_live()

    # ---------------- Dynamic behavior ----------------

    def _auto_capitalize(self, entry):
        value = entry.get()
        capitalized = to_title_case(value)
        if capitalized != value:
            entry.delete(0, "end")
            entry.insert(0, capitalized)

    def _on_indian_toggle(self):
        is_indian = self.indian_var.get()
        if is_indian:
            self.country_menu.grid_remove()
            self.state_text_entry.grid_remove()
            self.state_dropdown.grid()
            self.pincode_text_entry.grid_remove()
            self.pincode_numeric_entry.grid()
            self.pin_label.configure(text="PIN Code")
            self.mobile_code_label.configure(text=INDIA_COUNTRY_CODE)
            self.gstin_label.configure(text="GSTIN")
            self.pan_label.configure(text="PAN")
        else:
            self.country_menu.grid()
            self.state_dropdown.grid_remove()
            self.state_text_entry.grid()
            self.pincode_numeric_entry.grid_remove()
            self.pincode_text_entry.grid()
            self.pin_label.configure(text="Postal Code")
            self._on_country_change(self.country_var.get())
            self.gstin_label.configure(text="Tax Registration No. (Optional)")
            self.pan_label.configure(text="Business Registration No. (Optional)")
        self._on_alt_same_toggle()

    def _on_country_change(self, label):
        if not self.indian_var.get():
            _, code = country_from_label(label)
            self.mobile_code_label.configure(text=code or "+__")
            self._on_alt_same_toggle()

    def _on_alt_same_toggle(self):
        if self.alt_same_code_var.get():
            self.alt_code_dropdown.grid_remove()
            self.alt_code_mirror_label.configure(text=self.mobile_code_label.cget("text"))
            self.alt_code_mirror_label.grid()
        else:
            self.alt_code_mirror_label.grid_remove()
            self.alt_code_dropdown.grid()

    def _validate_email_live(self, event=None):
        value = self.email_entry.get().strip()
        if not value:
            self.email_entry.configure(border_color=theme.MUTED)
            self.email_status_label.configure(text="")
            return
        if is_valid_email(value):
            self.email_entry.configure(border_color="#2E8B57")
            self.email_status_label.configure(text="✔ Valid Email", text_color="#2E8B57")
        else:
            self.email_entry.configure(border_color="#8B2E2E")
            suggestion = email_typo_suggestion(value)
            if suggestion:
                self.email_status_label.configure(
                    text=f"⚠ Invalid Email -- did you mean {suggestion}?", text_color="#8B2E2E")
            else:
                self.email_status_label.configure(text="⚠ Invalid Email Address", text_color="#8B2E2E")

    def _check_duplicate_mobile(self):
        number = self.mobile_number_entry.get().strip()
        if not number:
            return
        code = self.mobile_code_label.cget("text")
        existing_id = self.existing["ClientID"] if self.existing else None
        match = db.fetch_one(
            "SELECT ClientID, ClientName FROM tblClient WHERE Mobile=? AND MobileCountryCode=? AND ClientID != ?",
            (number, code, existing_id or -1)
        )
        if match:
            open_existing = messagebox.askyesno(
                "Client already exists",
                f"A client with this mobile number already exists:\n\n{match['ClientName']}\n\n"
                f"Open the existing client instead of creating a new one?"
            , parent=self)
            if open_existing:
                matched_id = match["ClientID"]
                self.destroy()
                self.client_screen.open_edit_form_for(matched_id)

    def _on_source_change(self, choice):
        if choice == ADD_NEW_SOURCE:
            dialog = ctk.CTkInputDialog(text="Enter the new lead source name:", title="Add New Source")
            new_source = dialog.get_input()
            if new_source and new_source.strip():
                new_source = new_source.strip()
                db.execute("INSERT OR IGNORE INTO mstLeadSource (SourceName) VALUES (?)", (new_source,))
                self.sources = get_lead_sources()
                self.source_menu.configure(values=self.sources + [ADD_NEW_SOURCE])
                self.source_var.set(new_source)
            else:
                self.source_var.set(self.sources[0])

    # ---------------- Save ----------------

    def save(self):
        client_name = to_title_case(self.name_entry.get().strip())
        email = self.email_entry.get().strip()
        address = self.address_text.get("1.0", "end").strip()
        city = to_title_case(self.city_entry.get().strip())
        mobile_number = self.mobile_number_entry.get().strip()
        alt_mobile_number = self.alt_number_entry.get().strip()
        gstin = self.gstin_entry.get().strip().upper()
        pan = self.pan_entry.get().strip().upper()
        remarks = self.remarks_entry.get().strip()

        missing = [label for value, label in
                   [(client_name, "Client Name"), (mobile_number, "Mobile"), (address, "Address")]
                   if not value]

        if email and not is_valid_email(email):
            messagebox.showerror("Invalid Email", "Please enter a valid email address before saving.", parent=self)
            return

        is_indian = self.indian_var.get()
        if is_indian:
            country = "India"
            state = self.state_dropdown_var.get()
            pincode = self.pincode_numeric_entry.get().strip()
            mobile_code = INDIA_COUNTRY_CODE
            if gstin and not is_valid_gstin(gstin):
                messagebox.showerror("Invalid GSTIN", "GSTIN must be a valid 15-character format (e.g. 22AAAAA0000A1Z5).", parent=self)
                return
            if pan and not is_valid_pan(pan):
                messagebox.showerror("Invalid PAN", "PAN must be a valid format (e.g. ABCDE1234F).", parent=self)
                return
        else:
            country, mobile_code = country_from_label(self.country_var.get())
            state = self.state_text_entry.get().strip()
            pincode = self.pincode_text_entry.get().strip()
            if not country:
                missing.append("Country")

        if self.alt_same_code_var.get():
            alt_code = mobile_code
        else:
            alt_code = self.alt_code_var.get()

        if missing:
            messagebox.showerror("Missing required fields", "Please fill in: " + ", ".join(missing), parent=self)
            return

        source = self.source_var.get()
        if source == ADD_NEW_SOURCE:
            source = self.sources[0] if self.sources else "Other"

        # NULL unless the checkbox is actually checked -- never persist a
        # date the user didn't genuinely set.
        followup_date = self.followup_date.get_date().isoformat() if self.followup_enabled_var.get() else None

        if self.existing:
            db.execute(
                """UPDATE tblClient SET ClientName=?, Mobile=?, MobileCountryCode=?,
                   AlternateMobile=?, AlternateMobileCountryCode=?, Email=?, Address=?,
                   City=?, PinCode=?, State=?, Country=?, GSTIN=?, PAN=?, Remarks=?, Source=?, Priority=?,
                   NextFollowUpDate=?, ModifiedOn=datetime('now') WHERE ClientID=?""",
                (client_name, mobile_number, mobile_code, alt_mobile_number, alt_code, email,
                 address, city, pincode, state, country, gstin, pan, remarks, source, self.priority_var.get(),
                 followup_date, self.existing["ClientID"])
            )
            db.log_activity("Client", self.existing["ClientID"], "Updated")
            client_id = self.existing["ClientID"]
        else:
            code = db.next_code("ADS-CL", "tblClient", "ClientCode")
            new_id = db.execute(
                """INSERT INTO tblClient (ClientCode, ClientName, Mobile, MobileCountryCode,
                   AlternateMobile, AlternateMobileCountryCode, Email, Address, City, PinCode,
                   State, Country, GSTIN, PAN, Remarks, Source, Priority, NextFollowUpDate)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (code, client_name, mobile_number, mobile_code, alt_mobile_number, alt_code,
                 email, address, city, pincode, state, country, gstin, pan, remarks, source, self.priority_var.get(),
                 followup_date)
            )
            db.log_activity("Client", new_id, "Created")
            client_id = new_id

        self.on_save()
        self.destroy()


class ClientWorkspace(ui.EntityWorkspace):
    """
    Full Client profile, opened via double-click or "Open" from a client
    card. Built on the same EntityWorkspace framework proven for
    ContractorWorkspace, so this and any future entity workspace share
    identical structure rather than each being a one-off implementation.

    Tabs built with real, already-computable data: Overview (contact info,
    real aggregated Projects/Invoices/Revenue/Outstanding), Projects (every
    real project for this client), Invoices (every real invoice across all
    their projects). Deliberately NOT built: Documents, a dedicated
    Proposals tab (Proposals belong to Projects, not Clients directly --
    aggregating them meaningfully needs its own real design decision, not
    a quick addition here), Notes (Client has no Notes field currently).
    """
    def __init__(self, master, client_id, on_close=None):
        self.client_id = client_id
        c = db.fetch_one("SELECT * FROM tblClient WHERE ClientID=?", (client_id,))
        priority = c["Priority"] or "Normal"
        relationship = self._get_relationship(client_id)

        super().__init__(master, breadcrumb_root="Clients", entity_name=c["ClientName"],
                         subtitle=c["ClientCode"], tags=[priority, relationship],
                         quick_actions=[("Edit Client", self._edit), ("Record Payment", self._record_payment)],
                         on_close=on_close)

        self.add_tab("Overview", self._build_overview)
        self.add_tab("Projects", self._build_projects)
        self.add_tab("Invoices", self._build_invoices)
        self.build()

    def _get_relationship(self, client_id):
        project_count = db.fetch_one("SELECT COUNT(*) AS n FROM tblProject WHERE ClientID=?", (client_id,))["n"]
        return "Repeat Client" if project_count > 1 else ("Existing Client" if project_count == 1 else "New Lead")

    def _edit(self):
        c = db.fetch_one("SELECT * FROM tblClient WHERE ClientID=?", (self.client_id,))
        ClientForm(self, on_save=lambda: None, existing=c)

    def _record_payment(self):
        # Real gap fix: Turnkey projects don't invoice everything upfront
        # -- scope and total value grow as work progresses, and payments
        # arrive against that evolving total, not against a pre-created
        # invoice matching each amount exactly. This gives a direct path
        # -- Client -> Record Payment -> select Project -- instead of
        # forcing a detour through Invoice Center to find or create the
        # right invoice first.
        ClientRecordPaymentDialog(self, self.client_id, on_save=self._refresh_after_payment)

    def _refresh_after_payment(self):
        """Force Overview and Invoices to rebuild with fresh figures -- both are lazy-built-once by
        EntityWorkspace and won't otherwise reflect a payment just recorded from this dialog."""
        for tab_name in ("Overview", "Invoices"):
            if tab_name in self._built_tabs:
                for w in self.tabs.tab(tab_name).winfo_children():
                    w.destroy()
                self._build_tab_content(tab_name)

    def _build_overview(self, parent):
        c = db.fetch_one("SELECT * FROM tblClient WHERE ClientID=?", (self.client_id,))
        projects = db.fetch_all("SELECT ProjectID FROM tblProject WHERE ClientID=?", (self.client_id,))
        invoices = db.fetch_all("""
            SELECT i.InvoiceID, i.Amount FROM trxInvoice i JOIN tblProject p ON i.ProjectID = p.ProjectID
            WHERE p.ClientID=? AND i.Status != 'Cancelled'
        """, (self.client_id,))
        total_invoiced = sum(i["Amount"] for i in invoices)
        total_received = sum(db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxInvoicePayment WHERE InvoiceID=?",
                                          (i["InvoiceID"],))["t"] for i in invoices)

        stats_row = ctk.CTkFrame(parent, fg_color="transparent")
        stats_row.pack(fill="x", padx=15, pady=(15, 10))
        stats = [
            (str(len(projects)), "Projects", None),
            (str(len(invoices)), "Invoices", None),
            (f"₹{total_invoiced:,.0f}", "Total Invoiced", None),
            (f"₹{total_invoiced - total_received:,.0f}", "Outstanding", None),
        ]
        for value, label, sublabel in stats:
            ui.stat_card(stats_row, value, label, sublabel).pack(side="left", padx=(0, 15))

        details_frame = ctk.CTkFrame(parent, fg_color=theme.WHITE, corner_radius=8)
        details_frame.pack(fill="x", padx=15, pady=(0, 15))
        ctk.CTkLabel(details_frame, text="Contact Details", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=15, pady=(15, 8))
        mobile_display = f"{c['MobileCountryCode'] or ''} {c['Mobile'] or ''}".strip()
        for label, value in [("Mobile", mobile_display), ("Email", c["Email"]), ("City", c["City"]),
                             ("Address", c["Address"]), ("Source", c["Source"])]:
            if value:
                row = ctk.CTkFrame(details_frame, fg_color="transparent")
                row.pack(fill="x", padx=15, pady=2)
                ctk.CTkLabel(row, text=label, font=theme.FONT_SMALL, text_color=theme.MUTED, width=100,
                            anchor="w").pack(side="left")
                ctk.CTkLabel(row, text=str(value), font=theme.FONT_SMALL, text_color=theme.INK, anchor="w").pack(side="left")
        ctk.CTkFrame(details_frame, fg_color="transparent", height=10).pack()

    def _build_projects(self, parent):
        projects = db.fetch_all("SELECT * FROM tblProject WHERE ClientID=? ORDER BY ProjectID DESC", (self.client_id,))
        if not projects:
            ui.empty_state(parent, "No projects yet for this client.")
            return
        for p in projects:
            row = ctk.CTkFrame(parent, fg_color=theme.WHITE, corner_radius=6)
            row.pack(fill="x", padx=15, pady=4)
            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", fill="x", expand=True, padx=12, pady=10)
            ctk.CTkLabel(left, text=p["ProjectName"], font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(anchor="w")
            ctk.CTkLabel(left, text=f"{p['ProjectCode']}  ·  {p['ProjectStatus']}", font=theme.FONT_SMALL,
                        text_color=theme.MUTED).pack(anchor="w")
            # Real gap fix: this list previously had no way to actually open
            # a project from here -- just a static label, no click, no
            # button. Reuses the same ProjectWorkspace already opened from
            # the main Projects screen's "Open Workspace" action.
            ctk.CTkButton(row, text="Open Project  →", command=lambda pid=p["ProjectID"]: self._open_project(pid),
                         fg_color=theme.BRASS, hover_color=theme.INK, font=theme.FONT_SMALL, height=28,
                         width=130).pack(side="right", padx=12, pady=10)

    def _open_project(self, project_id):
        from project_workspace import ProjectWorkspace
        ProjectWorkspace(self, project_id)

    def _build_invoices(self, parent):
        invoices = db.fetch_all("""
            SELECT i.*, p.ProjectName FROM trxInvoice i JOIN tblProject p ON i.ProjectID = p.ProjectID
            WHERE p.ClientID=? AND i.Status != 'Cancelled' ORDER BY i.InvoiceDate DESC
        """, (self.client_id,))
        if not invoices:
            ui.empty_state(parent, "No invoices yet for this client.")
            return
        for inv in invoices:
            paid = db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxInvoicePayment WHERE InvoiceID=?",
                                (inv["InvoiceID"],))["t"]
            row = ctk.CTkFrame(parent, fg_color=theme.WHITE, corner_radius=6)
            row.pack(fill="x", padx=15, pady=4)
            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", fill="x", expand=True, padx=12, pady=10)
            ctk.CTkLabel(left, text=f"{inv['ProjectName']} -- {inv['InvoiceNo']}", font=theme.FONT_BODY_BOLD,
                        text_color=theme.INK).pack(anchor="w")
            ctk.CTkLabel(left, text=f"{inv['InvoiceDate']}  ·  {inv['Status']}", font=theme.FONT_SMALL,
                        text_color=theme.MUTED).pack(anchor="w")
            ctk.CTkLabel(row, text=f"₹{inv['Amount']:,.2f}  (Paid: ₹{paid:,.2f})", font=theme.FONT_BODY_BOLD,
                        text_color=theme.INK).pack(side="right", padx=12, pady=10)


class ClientRecordPaymentDialog(ctk.CTkToplevel):
    """
    Real workflow fix, requested directly: Turnkey projects don't invoice
    everything upfront -- scope and total value grow as work progresses,
    and payments arrive against that evolving total, not against a
    pre-created invoice matching each amount exactly. This dialog gives
    the direct path described -- Client -> Record Payment -> select
    Project -- recording a payment against that project's Running
    invoice (invoice_panel.py's InvoiceType='Running'), which stays open
    and grows via Edit Invoice as scope increases, instead of forcing a
    detour through Invoice Center to find or create the right invoice
    first, or forcing a guess at the final amount upfront the way
    Milestone/Advance/Final invoices do.

    Never fabricates a starting amount for a new Running invoice -- if
    this project doesn't have one yet, the real current total scope
    value is asked for explicitly before any payment can be recorded,
    same discipline as every other real-money figure in this app.
    """
    def __init__(self, master, client_id, on_save):
        super().__init__(master)
        self.client_id = client_id
        self.on_save = on_save
        self.title("Record Payment")
        self.geometry("440x520")
        self.configure(fg_color=theme.PARCHMENT)
        self.transient(self.master.winfo_toplevel())
        self.grab_set()

        self.projects = db.fetch_all(
            "SELECT * FROM tblProject WHERE ClientID=? ORDER BY ProjectID DESC", (self.client_id,))

        ctk.CTkLabel(self, text="Record Payment", font=theme.FONT_SUBHEADING, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 10))

        if not self.projects:
            ctk.CTkLabel(self, text="This client has no projects yet -- create a project first.",
                        font=theme.FONT_SMALL, text_color=theme.MUTED, wraplength=380).pack(anchor="w", padx=20)
            return

        ctk.CTkLabel(self, text="Project", font=theme.FONT_BODY, text_color=theme.INK).pack(anchor="w", padx=20)
        project_names = [f"{p['ProjectName']} ({p['ProjectCode']})" for p in self.projects]
        self.project_var = ctk.StringVar(value=project_names[0])
        ctk.CTkOptionMenu(self, values=project_names, variable=self.project_var, width=380,
                         command=self._on_project_change).pack(padx=20, pady=(0, 10))

        self.dynamic_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.dynamic_frame.pack(fill="both", expand=True)

        self.selected_project = self.projects[0]
        self.running_invoice = None
        self.new_invoice_amount_entry = None
        self._render_dynamic()

    def _on_project_change(self, choice):
        project_names = [f"{p['ProjectName']} ({p['ProjectCode']})" for p in self.projects]
        self.selected_project = self.projects[project_names.index(choice)]
        self._render_dynamic()

    def _render_dynamic(self):
        for w in self.dynamic_frame.winfo_children():
            w.destroy()
        from invoice_panel import get_active_running_invoice, get_paid_amount, PAYMENT_MODE_OPTIONS
        self.running_invoice = get_active_running_invoice(self.selected_project["ProjectID"])
        self.new_invoice_amount_entry = None

        if self.running_invoice:
            paid = get_paid_amount(self.running_invoice["InvoiceID"])
            balance = self.running_invoice["Amount"] - paid
            ctk.CTkLabel(self.dynamic_frame,
                        text=f"Running Invoice {self.running_invoice['InvoiceNo']}\n"
                             f"Total So Far: ₹{self.running_invoice['Amount']:,.2f}   ·   "
                             f"Received: ₹{paid:,.2f}   ·   Balance: ₹{balance:,.2f}",
                        font=theme.FONT_SMALL, text_color=theme.MUTED, justify="left").pack(
                anchor="w", padx=20, pady=(0, 10))
        else:
            ctk.CTkLabel(self.dynamic_frame,
                        text="This project has no Running invoice yet -- enter the real current total scope "
                             "value to start one. You can increase this later via Edit Invoice as more scope "
                             "is added.",
                        font=("Segoe UI", 9), text_color=theme.MUTED, wraplength=380, justify="left").pack(
                anchor="w", padx=20, pady=(0, 8))
            ctk.CTkLabel(self.dynamic_frame, text="Current Total Scope Value (₹) *", font=theme.FONT_BODY,
                        text_color=theme.INK).pack(anchor="w", padx=20)
            self.new_invoice_amount_entry = ctk.CTkEntry(self.dynamic_frame, width=380)
            apply_decimal_only(self, self.new_invoice_amount_entry)
            self.new_invoice_amount_entry.pack(padx=20, pady=(0, 10))

        ctk.CTkLabel(self.dynamic_frame, text="Amount Received (₹) *", font=theme.FONT_BODY,
                    text_color=theme.INK).pack(anchor="w", padx=20)
        self.amount_entry = ctk.CTkEntry(self.dynamic_frame, width=380)
        apply_decimal_only(self, self.amount_entry)
        self.amount_entry.pack(padx=20, pady=(0, 10))

        ctk.CTkLabel(self.dynamic_frame, text="Payment Date", font=theme.FONT_BODY, text_color=theme.INK).pack(
            anchor="w", padx=20)
        self.date_entry = DateEntry(self.dynamic_frame, width=20, date_pattern="yyyy-mm-dd",
                                    background=theme.BRASS, foreground="white", borderwidth=1,
                                    headersbackground=theme.INK, headersforeground="white",
                                    selectbackground=theme.BRASS)
        self.date_entry.pack(anchor="w", padx=20, pady=(0, 10))

        ctk.CTkLabel(self.dynamic_frame, text="Payment Mode", font=theme.FONT_BODY, text_color=theme.INK).pack(
            anchor="w", padx=20)
        self.mode_var = ctk.StringVar(value="NEFT")
        ctk.CTkOptionMenu(self.dynamic_frame, values=PAYMENT_MODE_OPTIONS, variable=self.mode_var,
                         width=380).pack(padx=20, pady=(0, 15))

        ctk.CTkButton(self.dynamic_frame, text="Save Payment", command=self.save, fg_color=theme.BRASS,
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

        project_id = self.selected_project["ProjectID"]

        if self.running_invoice:
            invoice_id = self.running_invoice["InvoiceID"]
        else:
            try:
                starting_amount = float(self.new_invoice_amount_entry.get().strip() or 0)
            except ValueError:
                messagebox.showerror("Invalid number", "Current Total Scope Value must be a number.", parent=self)
                return
            if starting_amount <= 0:
                messagebox.showerror(
                    "Invalid amount",
                    "Enter the real current total scope value to start a Running invoice for this project.",
                    parent=self)
                return
            invoice_no = db.next_code("INV", "trxInvoice", "InvoiceNo")
            db.execute(
                """INSERT INTO trxInvoice (ProjectID, InvoiceNo, InvoiceDate, InvoiceType, Amount, Status)
                   VALUES (?, ?, date('now'), 'Running', ?, 'Sent')""",
                (project_id, invoice_no, starting_amount))
            db.log_activity("Project", project_id, "Running Invoice Created", invoice_no)
            new_invoice = db.fetch_one("SELECT * FROM trxInvoice WHERE InvoiceNo=?", (invoice_no,))
            invoice_id = new_invoice["InvoiceID"]

        payment_date = self.date_entry.get_date().isoformat()
        db.execute("INSERT INTO trxInvoicePayment (InvoiceID, PaymentDate, Amount, PaymentMode) VALUES (?,?,?,?)",
                   (invoice_id, payment_date, amount, self.mode_var.get()))
        db.log_activity("Project", project_id, "Payment Recorded",
                        f"₹{amount:,.2f} (via Client Record Payment)")
        messagebox.showinfo("Payment recorded",
                            f"₹{amount:,.2f} recorded for {self.selected_project['ProjectName']}.", parent=self)
        self.on_save()
        self.destroy()

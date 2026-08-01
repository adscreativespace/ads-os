"""
ADS OS Desktop v0.4.2
Entry point. Run with: python main.py
"""
import os
import datetime
import customtkinter as ctk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import db
import theme
import version
import ui_components as ui
from client_screen import ClientScreen
from project_screen import ProjectScreen

ctk.set_appearance_mode("light")

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# A handful of distinct colors for the status donut -- cycles if there are
# more distinct statuses than colors, which is fine for a solo practice's
# realistic status spread.
STATUS_CHART_COLORS = ["#B68100", "#1A1A1A", "#1E5FA8", "#2E8B57", "#8B2E2E", "#6B6B6B", "#9B59B6", "#D4A017"]


class DashboardScreen(ctk.CTkFrame):
    def __init__(self, master, app=None):
        super().__init__(master, fg_color=theme.PARCHMENT)
        self.app = app  # reference to the App instance, used only by Quick Actions to navigate + open a form

        # Genuinely missing before -- unlike Clients/Projects (whose card
        # lists were already wrapped in a CTkScrollableFrame), Dashboard's
        # top-level content was packed directly into self with no scroll
        # wrapping at all. On a resized/non-maximized window, content taller
        # than the visible area would simply clip with no way to reach it.
        # AdaptiveScrollFrame only shows a scrollbar when content genuinely
        # overflows, rather than always showing one like CTkScrollableFrame.
        container = ui.AdaptiveScrollFrame(self, fg_color=theme.PARCHMENT)
        container.pack(fill="both", expand=True)

        hour = datetime.datetime.now().hour
        greeting = "Good Morning" if hour < 12 else ("Good Afternoon" if hour < 17 else "Good Evening")

        header = ctk.CTkFrame(container.content, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 5))
        # Fixed a real bug: CTkEntry's placeholder_text does not render when
        # state="disabled" -- the box just looked empty, which read as
        # broken rather than "reserved for later." A disabled-look BUTTON
        # (not an Entry) can show real static text regardless of state,
        # which is what "reserved space" actually needs here.
        search_placeholder = ctk.CTkButton(header, text="🔍  Global Search (Ctrl+K)", width=220, height=30,
                                           state="disabled", fg_color=theme.PARCHMENT, text_color=theme.MUTED,
                                           hover=False, border_width=1, border_color=theme.MUTED,
                                           font=theme.FONT_SMALL)
        search_placeholder.pack(side="right", pady=(2, 0))
        ctk.CTkLabel(header, text=f"{greeting}!", font=("Georgia", 23, "bold"), text_color=theme.INK).pack(anchor="w")
        ctk.CTkLabel(header, text="Here's what's happening across your projects.",
                     font=("Segoe UI", 11), text_color=theme.MUTED).pack(anchor="w")

        # One canonical status -> color mapping, built once and reused by both
        # the donut chart and the Top Projects table below, so a given status
        # always reads as the same color everywhere on the Dashboard --
        # computing this separately in two places risked them disagreeing.
        all_statuses_alpha = [s["ProjectStatus"] for s in db.fetch_all(
            "SELECT DISTINCT ProjectStatus FROM tblProject ORDER BY ProjectStatus")]
        self.status_color_map = {
            status: STATUS_CHART_COLORS[i % len(STATUS_CHART_COLORS)] for i, status in enumerate(all_statuses_alpha)
        }

        # ---------------- Real KPI cards ----------------
        stats_frame = ctk.CTkFrame(container.content, fg_color="transparent")
        stats_frame.pack(fill="x", padx=20, pady=(15, 10))

        total_projects = db.fetch_one("SELECT COUNT(*) AS n FROM tblProject")["n"]
        active_projects = db.fetch_one(
            "SELECT COUNT(*) AS n FROM tblProject WHERE ProjectStatus NOT IN ('Completed','Cancelled')")["n"]
        total_clients = db.fetch_one("SELECT COUNT(*) AS n FROM tblClient")["n"]
        active_clients = db.fetch_one("""
            SELECT COUNT(DISTINCT c.ClientID) AS n FROM tblClient c
            JOIN tblProject p ON c.ClientID = p.ClientID
            WHERE p.ProjectStatus NOT IN ('Completed','Cancelled')
        """)["n"]
        total_invoiced = db.fetch_one(
            "SELECT COALESCE(SUM(Amount),0) AS t FROM trxInvoice WHERE Status != 'Cancelled'")["t"]

        invoices = db.fetch_all("SELECT InvoiceID, Amount FROM trxInvoice WHERE Status != 'Cancelled'")
        outstanding_total, outstanding_count = 0, 0
        for inv in invoices:
            paid = db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxInvoicePayment WHERE InvoiceID=?",
                                (inv["InvoiceID"],))["t"]
            bal = inv["Amount"] - paid
            if bal > 0.01:
                outstanding_total += bal
                outstanding_count += 1

        pending_milestones = db.fetch_one("SELECT COUNT(*) AS n FROM tblMilestone WHERE Status != 'Completed'")["n"]
        pdfs_this_month = db.fetch_one("""
            SELECT COUNT(*) AS n FROM logActivity
            WHERE Action LIKE '%Generated%' AND strftime('%Y-%m', LoggedOn) = strftime('%Y-%m', 'now')
        """)["n"]

        # Real trend context -- computed from actual CreatedOn/CompletedOn
        # timestamps, never a fabricated delta.
        projects_this_week = db.fetch_one(
            "SELECT COUNT(*) AS n FROM tblProject WHERE CreatedOn >= datetime('now', '-7 days')")["n"]
        milestones_completed_today = db.fetch_one(
            "SELECT COUNT(*) AS n FROM tblMilestone WHERE Status='Completed' AND date(CompletedOn) = date('now')")["n"]

        ui.stat_card(stats_frame, str(total_projects), "Total Projects",
                    f"{active_projects} Active" + (f" · +{projects_this_week} this week" if projects_this_week else ""),
                    icon="📁").pack(side="left", padx=(0, 12))
        ui.stat_card(stats_frame, str(total_clients), "Total Clients", f"{active_clients} Active",
                    icon="👥").pack(side="left", padx=(0, 12))
        ui.stat_card(stats_frame, f"₹{total_invoiced:,.0f}", "Total Invoiced", "All Time",
                    icon="💰").pack(side="left", padx=(0, 12))
        ui.stat_card(stats_frame, f"₹{outstanding_total:,.0f}", "Outstanding", f"{outstanding_count} Invoice(s)",
                    icon="⚠️").pack(side="left", padx=(0, 12))
        ui.stat_card(stats_frame, str(pending_milestones), "Pending Milestones",
                    f"{milestones_completed_today} completed today" if milestones_completed_today else "Across Projects",
                    icon="📅").pack(side="left", padx=(0, 12))
        ui.stat_card(stats_frame, str(pdfs_this_month), "PDFs Generated", "This Month",
                    icon="📄").pack(side="left", padx=(0, 12))

        # ---------------- Middle row: Status chart / Financial snapshot / Activity ----------------
        middle = ctk.CTkFrame(container.content, fg_color="transparent")
        middle.pack(fill="both", expand=True, padx=20, pady=(10, 10))

        status_card = ctk.CTkFrame(middle, fg_color=theme.WHITE, corner_radius=8)
        status_card.pack(side="left", fill="both", expand=True, padx=(0, 10))
        ctk.CTkLabel(status_card, text="Project Status", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=15, pady=(15, 5))
        self._render_status_chart(status_card, total_projects)

        finance_card = ctk.CTkFrame(middle, fg_color=theme.WHITE, corner_radius=8, width=240, height=420)
        finance_card.pack(side="left", fill="y", padx=(0, 10))
        finance_card.pack_propagate(False)
        # Reverted from the AdaptiveScrollFrame wrapping -- that introduced
        # its own visual complications (a stray scroll-arrow artifact,
        # unclear whether the scrollbar was even usable) without cleanly
        # fixing the actual problem. This is a micro-layout spacing issue,
        # not one that needs a scrollable container: reclaiming the
        # ~25-30px shortfall directly from existing whitespace is simpler
        # and more predictable. Every pady below was reduced deliberately,
        # not guessed -- see the itemized breakdown in the changelog.
        ctk.CTkLabel(finance_card, text="Financial Snapshot (This Month)", font=theme.FONT_BODY_BOLD,
                     text_color=theme.INK, wraplength=210, justify="left").pack(anchor="w", padx=15, pady=(15, 8))
        self._render_financial_snapshot(finance_card)

        ctk.CTkFrame(finance_card, fg_color=theme.PARCHMENT, height=1).pack(fill="x", padx=15, pady=6)
        ctk.CTkLabel(finance_card, text="Quick Actions", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=15, pady=(2, 4))
        ctk.CTkButton(finance_card, text="+ New Client", command=self._quick_new_client,
                      fg_color=theme.BRASS, hover_color=theme.INK, font=theme.FONT_SMALL, height=24).pack(
            fill="x", padx=15, pady=(0, 2))
        ctk.CTkButton(finance_card, text="+ New Project", command=self._quick_new_project,
                      fg_color=theme.INK, hover_color=theme.BRASS, font=theme.FONT_SMALL, height=24).pack(
            fill="x", padx=15, pady=(2, 8))

        activity_card = ctk.CTkFrame(middle, fg_color=theme.WHITE, corner_radius=8, width=380)
        activity_card.pack(side="left", fill="both", expand=True)
        activity_header = ctk.CTkFrame(activity_card, fg_color="transparent")
        activity_header.pack(fill="x", padx=15, pady=(15, 5))
        ctk.CTkLabel(activity_header, text="Recent Activity", font=theme.FONT_BODY_BOLD,
                     text_color=theme.INK).pack(side="left")
        ctk.CTkButton(activity_header, text="Clear Log", command=self._clear_log,
                      fg_color=theme.MUTED, hover_color="#8B2E2E",
                      font=theme.FONT_SMALL, width=80, height=24).pack(side="right")
        self._render_activity(activity_card)

        # ---------------- Bottom row: Top Projects by Invoiced Amount ----------------
        bottom = ctk.CTkFrame(container.content, fg_color=theme.WHITE, corner_radius=8)
        bottom.pack(fill="x", padx=20, pady=(0, 15))
        ctk.CTkLabel(bottom, text="Top Projects by Invoiced Amount", font=theme.FONT_BODY_BOLD,
                     text_color=theme.INK).pack(anchor="w", padx=15, pady=(15, 5))
        self._render_top_projects(bottom)

    def _render_status_chart(self, parent, total_projects):
        if total_projects == 0:
            ctk.CTkLabel(parent, text="No projects yet.", font=theme.FONT_SMALL, text_color=theme.MUTED).pack(
                padx=15, pady=20)
            return
        status_dist = db.fetch_all(
            "SELECT ProjectStatus, COUNT(*) AS n FROM tblProject GROUP BY ProjectStatus ORDER BY n DESC")

        fig = Figure(figsize=(4.2, 3.8), dpi=100)
        fig.patch.set_facecolor(theme.WHITE)
        ax = fig.add_subplot(111)
        labels = [s["ProjectStatus"] for s in status_dist]
        sizes = [s["n"] for s in status_dist]
        colors = [self.status_color_map[label] for label in labels]
        ax.pie(sizes, colors=colors, startangle=90, wedgeprops={"width": 0.4, "edgecolor": "white"})
        ax.text(0, 0, str(total_projects), ha="center", va="center", fontsize=24, fontweight="bold", color="#1A1A1A")
        ax.text(0, -0.25, "Projects", ha="center", va="center", fontsize=10, color="#6B6B6B")
        ax.set_aspect("equal")

        # Wrapped in a container packed with expand=True (no fill) --
        # centers the whole chart+legend cluster within the card instead of
        # it sitting flush-left with a large empty gap to the right, which
        # is what made it feel disconnected/floating.
        cluster = ctk.CTkFrame(parent, fg_color="transparent")
        cluster.pack(expand=True)

        canvas = FigureCanvasTkAgg(fig, master=cluster)
        canvas.draw()
        canvas.get_tk_widget().pack(side="left", padx=(0, 2))

        legend_frame = ctk.CTkFrame(cluster, fg_color="transparent")
        legend_frame.pack(side="left", padx=(2, 0))
        for s in status_dist:
            row = ctk.CTkFrame(legend_frame, fg_color="transparent")
            row.pack(anchor="w", pady=3)
            dot = ctk.CTkLabel(row, text="●", font=("Segoe UI", 12),
                               text_color=self.status_color_map[s["ProjectStatus"]])
            dot.pack(side="left")
            ctk.CTkLabel(row, text=f" {s['ProjectStatus']} ({s['n']})", font=theme.FONT_SMALL,
                        text_color=theme.INK).pack(side="left")

    def _render_financial_snapshot(self, parent):
        invoiced_this_month = db.fetch_one("""
            SELECT COALESCE(SUM(Amount),0) AS t FROM trxInvoice
            WHERE Status != 'Cancelled' AND strftime('%Y-%m', InvoiceDate) = strftime('%Y-%m', 'now')
        """)["t"]
        received_this_month = db.fetch_one("""
            SELECT COALESCE(SUM(Amount),0) AS t FROM trxInvoicePayment
            WHERE strftime('%Y-%m', PaymentDate) = strftime('%Y-%m', 'now')
        """)["t"]
        boq_this_month = db.fetch_one("""
            SELECT COALESCE(SUM(Amount),0) AS t FROM trxBOQItem
            WHERE strftime('%Y-%m', CreatedOn) = strftime('%Y-%m', 'now')
        """)["t"]
        material_this_month = db.fetch_one("""
            SELECT COALESCE(SUM(TotalCost),0) AS t FROM trxMaterialPurchase
            WHERE strftime('%Y-%m', PurchaseDate) = strftime('%Y-%m', 'now')
        """)["t"]

        rows = [
            (f"₹{invoiced_this_month:,.0f}", "Invoiced"),
            (f"₹{received_this_month:,.0f}", "Received"),
            (f"₹{boq_this_month:,.0f}", "BOQ Costs"),
            (f"₹{material_this_month:,.0f}", "Material Costs"),
        ]
        for value, label in rows:
            ui.metric_row(parent, value, label)

    def _render_activity(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent", height=260)
        scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        entries = db.fetch_all(
            "SELECT LoggedOn, Action, Details FROM logActivity ORDER BY LoggedOn DESC LIMIT 12")
        if not entries:
            ctk.CTkLabel(scroll, text="No activity yet.", font=theme.FONT_SMALL, text_color=theme.MUTED).pack(
                anchor="w", pady=10)
            return
        for e in entries:
            ui.activity_card(scroll, e["Action"], e["Details"], e["LoggedOn"])

    def _render_top_projects(self, parent):
        top_projects = db.fetch_all("""
            SELECT p.ProjectName, c.ClientName, p.ProjectStatus, COALESCE(SUM(i.Amount),0) AS total
            FROM tblProject p
            JOIN tblClient c ON p.ClientID = c.ClientID
            LEFT JOIN trxInvoice i ON p.ProjectID = i.ProjectID AND i.Status != 'Cancelled'
            GROUP BY p.ProjectID ORDER BY total DESC LIMIT 5
        """)
        table_frame = ctk.CTkFrame(parent, fg_color="transparent")
        table_frame.pack(fill="x", padx=10, pady=(0, 15))
        cols = ("project", "client", "status", "amount")
        tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=5)
        headings = {"project": "Project", "client": "Client", "status": "Status", "amount": "Invoiced (₹)"}
        widths = {"project": 250, "client": 180, "status": 120, "amount": 130}
        for c in cols:
            tree.heading(c, text=headings[c])
            tree.column(c, width=widths[c])
        tree.pack(fill="x")
        # Same status -> color mapping as the donut chart above, so a given
        # status always reads as the same color across the whole Dashboard.
        for status, color in self.status_color_map.items():
            tree.tag_configure(f"status_{status}", foreground=color)
        for p in top_projects:
            tree.insert("", "end", values=(p["ProjectName"], p["ClientName"], p["ProjectStatus"], f"{p['total']:,.2f}"),
                       tags=(f"status_{p['ProjectStatus']}",))

    def _quick_new_client(self):
        if not self.app:
            return
        self.app.show("Clients")
        self.app.screens["Clients"].open_add_form()

    def _quick_new_project(self):
        if not self.app:
            return
        self.app.show("Projects")
        self.app.screens["Projects"].open_add_form()

    def _clear_log(self):
        if messagebox.askyesno("Clear Activity Log",
                                "This permanently deletes all Recent Activity history. "
                                "It does not affect any clients, projects, milestones, or site visits. Continue?", parent=self):
            db.execute("DELETE FROM logActivity")
            container = self.master
            app_ref = self.app
            self.destroy()
            DashboardScreen(container, app=app_ref).pack(fill="both", expand=True)


from vendors_panel import VendorsPanel
from contractors_panel import ContractorsPanel
from financial_dashboard import FinancialDashboardScreen
from reports_module import ReportsLandingScreen


class App(ctk.CTk):
    NAV_LABELS = {"Dashboard": "🏠  Dashboard", "Clients": "👥  Clients", "Projects": "📁  Projects",
                 "Vendors": "🧱  Vendors", "Contractors": "👷  Contractors",
                 "Financial Dashboard": "💰  Financial Dashboard", "Reports": "📊  Reports"}

    def __init__(self):
        super().__init__()
        self.title("ADS OS")
        self.geometry("1100x700")
        self.configure(fg_color=theme.PARCHMENT)
        self._set_window_icon()

        # Explicitly force a Unicode-safe font for every ttk.Treeview in the
        # app (BOQ, Materials, Vendors, Invoice Center, Commercial Reports,
        # Dashboard all display Rupee amounts inside Treeviews). MUST be here,
        # after super().__init__(), not at module level -- ttk.Style() needs a
        # live Tk root to attach to. This exact bug has now been reintroduced
        # twice by full-file regeneration reverting to an older module-level
        # version; keeping it here, inline in __init__, is the fix that survives.
        ttk.Style().configure("Treeview", font=("Segoe UI", 10), rowheight=28, borderwidth=0, relief="flat")
        ttk.Style().configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), padding=(8, 8),
                              relief="flat", borderwidth=1)
        # Selected-row highlight, softened from ttk's default harsh blue to
        # match the app's brass/ink palette -- this is centralized here, so
        # every Treeview in the app (BOQ, Materials, Vendors, Invoice
        # Center, Contracts, Reports, Projects Table View, and any future
        # one) gets the same look automatically, without editing each file.
        ttk.Style().map("Treeview", background=[("selected", theme.BRASS)], foreground=[("selected", theme.WHITE)])
        # Genuine limitation, not silently skipped: true zebra striping
        # (alternating row background colors) needs each row tagged
        # individually at insert time -- ttk has no single style-level
        # setting for it, unlike rowheight/selection color above. Doing
        # that properly would mean touching every Treeview row-insertion
        # call site across the app (a dozen-plus files), which is real,
        # separate future work, not something this centralized change can
        # cover on its own.

        # No separate header bar -- logo now lives directly in the dark sidebar
        # using an inverted (white line-art) version, so content starts at the
        # very top of the window instead of below a header strip.
        sidebar = ctk.CTkFrame(self, width=180, fg_color=theme.INK, corner_radius=0)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        self._add_logo(sidebar)

        ctk.CTkLabel(sidebar, text="ADS OS", font=("Georgia", 16, "bold"),
                     text_color=theme.WHITE).pack(pady=(10, 5))
        version_label = ctk.CTkLabel(sidebar, text=f"v{version.APP_VERSION}", font=theme.FONT_SMALL,
                                     text_color=theme.MUTED, cursor="hand2")
        version_label.pack(pady=(0, 25))
        version_label.bind("<Button-1>", lambda e: self._show_changelog())

        self.container = ctk.CTkFrame(self, fg_color=theme.PARCHMENT)
        self.container.pack(side="right", fill="both", expand=True)

        self.screens = {}
        for name, cls in [("Dashboard", DashboardScreen), ("Clients", ClientScreen),
                           ("Projects", ProjectScreen), ("Vendors", VendorsPanel),
                           ("Contractors", ContractorsPanel), ("Financial Dashboard", FinancialDashboardScreen),
                           ("Reports", ReportsLandingScreen)]:
            if cls in (DashboardScreen, ProjectScreen, ReportsLandingScreen, FinancialDashboardScreen):
                frame = cls(self.container, app=self)
            elif cls in (VendorsPanel, ContractorsPanel):
                # Genuine top-level master modules now, not a Project
                # feature -- project_id=None since neither uses it for
                # anything (both were already global masters underneath;
                # this only changes where they're reached from).
                frame = cls(self.container, None)
            else:
                frame = cls(self.container)
            self.screens[name] = frame

        self.nav_buttons = {}
        for name in self.screens:
            btn = ctk.CTkButton(sidebar, text=self.NAV_LABELS.get(name, name), command=lambda n=name: self.show(n),
                                fg_color="transparent", hover_color=theme.BRASS,
                                font=theme.FONT_BODY, anchor="w", width=160, corner_radius=6)
            btn.pack(pady=4, padx=10)
            self.nav_buttons[name] = btn

        ctk.CTkFrame(sidebar, fg_color=theme.MUTED, height=1).pack(fill="x", padx=10, pady=10)
        self.current_project_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        self.current_project_frame.pack(fill="x")
        self._render_current_project_section()

        self._add_health_status(sidebar)

        # Alt+1 through Alt+7 -- global navigation shortcuts, bound at the
        # root window so they work regardless of which screen has focus.
        # Matches the explicit request that keyboard shortcuts should work
        # everywhere, not be hidden behind a specific widget's focus.
        shortcut_order = ["Dashboard", "Clients", "Projects", "Vendors", "Contractors",
                          "Financial Dashboard", "Reports"]
        for i, screen_name in enumerate(shortcut_order, start=1):
            if screen_name in self.screens:
                self.bind_all(f"<Alt-Key-{i}>", lambda e, n=screen_name: self.show(n))

        self.show("Dashboard")

    # ---------------- Current Project (v4.2 infrastructure) ----------------
    # Purely additive -- the existing Projects -> Open Workspace path is
    # completely untouched and still works exactly as before. This section
    # is a second, faster entry point into the same ProjectWorkspace, not a
    # replacement for it. Selecting a project here, or opening one via
    # Projects -> Open Workspace, both update the same current_project_id,
    # so the two paths never disagree about which project is "current."

    def _render_current_project_section(self):
        for w in self.current_project_frame.winfo_children():
            w.destroy()

        project_id = db.get_current_project_id()
        if not project_id:
            ctk.CTkButton(self.current_project_frame, text="▼ Select a Project", command=self._open_project_picker,
                          fg_color="transparent", hover_color=theme.BRASS, font=theme.FONT_BODY,
                          anchor="w", width=160).pack(pady=4, padx=10)
            return

        project = db.fetch_one("SELECT ProjectName FROM tblProject WHERE ProjectID=?", (project_id,))

        header_btn = ctk.CTkButton(self.current_project_frame, text=f"▼ {project['ProjectName']}",
                                   command=self._open_project_picker, fg_color="transparent",
                                   hover_color=theme.BRASS, font=theme.FONT_BODY_BOLD, text_color=theme.BRASS,
                                   anchor="w", width=160)
        header_btn.pack(pady=(4, 8), padx=10)

        sub_items = [("Overview", "Overview"), ("Planning", "Planning"), ("Commercial", "Commercial"),
                    ("Design", "Design"), ("Execution", "Execution"), ("Activity", "Activity")]
        for label, tab in sub_items:
            ctk.CTkButton(self.current_project_frame, text=f"      {label}",
                          command=lambda t=tab: self._open_current_project_tab(t),
                          fg_color="transparent", hover_color=theme.BRASS, font=theme.FONT_SMALL,
                          anchor="w", width=160, height=26).pack(pady=1, padx=10)

    def _open_project_picker(self):
        picker = ctk.CTkToplevel(self)
        picker.title("Select Current Project")
        picker.geometry("420x480")
        picker.configure(fg_color=theme.PARCHMENT)
        picker.transient(self)
        picker.grab_set()

        ctk.CTkLabel(picker, text="Select Current Project", font=theme.FONT_SUBHEADING,
                     text_color=theme.INK).pack(anchor="w", padx=20, pady=(15, 10))

        recent = db.get_recent_projects(limit=5)
        if recent:
            ctk.CTkLabel(picker, text="Recent", font=theme.FONT_BODY_BOLD, text_color=theme.MUTED).pack(
                anchor="w", padx=20, pady=(0, 5))
            for r in recent:
                ctk.CTkButton(picker, text=f"{r['ProjectName']} ({r['ProjectCode']})",
                              command=lambda pid=r["ProjectID"]: self._select_current_project(pid, picker),
                              fg_color=theme.WHITE, hover_color=theme.BRASS, text_color=theme.INK,
                              font=theme.FONT_SMALL, anchor="w", height=30).pack(fill="x", padx=20, pady=2)
            ctk.CTkFrame(picker, fg_color=theme.MUTED, height=1).pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(picker, text="All Projects", font=theme.FONT_BODY_BOLD, text_color=theme.MUTED).pack(
            anchor="w", padx=20, pady=(0, 5))
        all_projects_scroll = ctk.CTkScrollableFrame(picker, fg_color="transparent")
        all_projects_scroll.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        all_projects = db.fetch_all("""
            SELECT p.ProjectID, p.ProjectName, p.ProjectCode, c.ClientName FROM tblProject p
            JOIN tblClient c ON p.ClientID = c.ClientID ORDER BY p.ProjectID DESC
        """)
        if not all_projects:
            ctk.CTkLabel(all_projects_scroll, text="No projects yet.", font=theme.FONT_SMALL,
                        text_color=theme.MUTED).pack(pady=10)
        for p in all_projects:
            ctk.CTkButton(all_projects_scroll, text=f"{p['ProjectName']} -- {p['ClientName']}",
                          command=lambda pid=p["ProjectID"]: self._select_current_project(pid, picker),
                          fg_color=theme.WHITE, hover_color=theme.BRASS, text_color=theme.INK,
                          font=theme.FONT_SMALL, anchor="w", height=30).pack(fill="x", pady=2)

    def _select_current_project(self, project_id, picker_window):
        db.set_current_project_id(project_id)
        self._render_current_project_section()
        picker_window.destroy()

    def _open_current_project_tab(self, tab_name):
        project_id = db.get_current_project_id()
        if not project_id:
            return
        from project_workspace import ProjectWorkspace
        ProjectWorkspace(self, project_id, initial_tab=tab_name)

    def set_current_project(self, project_id):
        """Called by ProjectScreen when a workspace is opened the old way (Projects ->
        Open Workspace), so both entry points always agree on the current project."""
        db.set_current_project_id(project_id)
        self._render_current_project_section()

    def _add_health_status(self, sidebar):
        """
        Persistent Database Health indicator, computed once at startup (not
        re-run on every navigation -- the full check is fast on a small
        SQLite file, but there's no reason to repeat it dozens of times per
        session). Click it to open the full About/Health panel for details.
        """
        import health_check
        results = health_check.run_health_check()
        has_error = any(status == "error" for _, status, _ in results)
        has_warning = any(status == "warning" for _, status, _ in results)
        if has_error:
            dot, label = "🔴", "Database Issue"
        elif has_warning:
            dot, label = "🟡", "Check Warnings"
        else:
            dot, label = "🟢", "Database Healthy"

        backup_line = next((detail for name, _, detail in results if name == "Backup Recency"), "")

        footer = ctk.CTkFrame(sidebar, fg_color="transparent", cursor="hand2")
        footer.pack(side="bottom", fill="x", padx=10, pady=10)
        status_label = ctk.CTkLabel(footer, text=f"{dot} {label}", font=theme.FONT_SMALL, text_color=theme.WHITE)
        status_label.pack(anchor="w")
        backup_label = ctk.CTkLabel(footer, text=backup_line, font=("Segoe UI", 8), text_color=theme.MUTED,
                                    wraplength=160, justify="left")
        backup_label.pack(anchor="w")
        for widget in (footer, status_label, backup_label):
            widget.bind("<Button-1>", lambda e: self._show_changelog())

    def _add_logo(self, sidebar):
        logo_path = os.path.join(ASSETS_DIR, "logo_white.png")
        if not os.path.exists(logo_path):
            # Fallback if the inverted logo file wasn't copied into assets/ -- app still runs
            ctk.CTkLabel(sidebar, text="ADS OS", font=("Georgia", 22, "bold"),
                         text_color=theme.BRASS).pack(pady=(20, 10))
            return
        img = Image.open(logo_path)
        target_width = 150
        ratio = target_width / img.width
        target_height = int(img.height * ratio)
        ctk_img = ctk.CTkImage(light_image=img, size=(target_width, target_height))
        logo_label = ctk.CTkLabel(sidebar, image=ctk_img, text="")
        logo_label.pack(pady=(20, 5))

    def _set_window_icon(self):
        ico_path = os.path.join(ASSETS_DIR, "logo_mark.ico")
        png_path = os.path.join(ASSETS_DIR, "logo_mark.png")
        # iconbitmap with a real .ico is what actually sets the Windows taskbar icon;
        # wm_iconphoto alone (PNG) often only affects the title bar, not the taskbar.
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
                return
            except Exception:
                pass  # fall through to PNG attempt below
        if os.path.exists(png_path):
            try:
                icon_img = Image.open(png_path)
                self._icon_photo = ImageTk.PhotoImage(icon_img)
                self.wm_iconphoto(True, self._icon_photo)
            except Exception:
                pass  # Non-critical -- app runs fine without a custom icon

    def _show_changelog(self):
        win = ctk.CTkToplevel(self)
        win.title("About ADS OS")
        win.geometry("560x680")
        win.configure(fg_color=theme.PARCHMENT)

        ctk.CTkLabel(win, text="About ADS OS", font=theme.FONT_SUBHEADING,
                     text_color=theme.INK).pack(anchor="w", padx=20, pady=(15, 5))

        # Version info: app version, SQLite engine version, and migration
        # status -- exactly what you need to state precisely when reporting a
        # bug or checking whether a specific copy of the database is current.
        import sqlite3
        applied = db.get_applied_migrations()
        expected = set(version.EXPECTED_MIGRATIONS)
        missing = expected - applied

        info_lines = [
            f"ADS OS Version: {version.APP_VERSION}",
            f"SQLite Engine: {sqlite3.sqlite_version}",
            f"Migrations Applied: {len(applied)} / {len(expected)}",
        ]
        info_text = "\n".join(info_lines)
        ctk.CTkLabel(win, text=info_text, font=theme.FONT_BODY, text_color=theme.INK,
                     justify="left").pack(anchor="w", padx=20, pady=(0, 5))

        if missing:
            warning = "⚠ This database is missing: " + ", ".join(sorted(missing))
            ctk.CTkLabel(win, text=warning, font=theme.FONT_SMALL, text_color="#8B2E2E",
                        wraplength=500, justify="left").pack(anchor="w", padx=20, pady=(0, 10))
        else:
            ctk.CTkLabel(win, text="✔ Database is fully up to date with this app version.",
                        font=theme.FONT_SMALL, text_color="#2E8B57").pack(anchor="w", padx=20, pady=(0, 10))

        health_frame = ctk.CTkFrame(win, fg_color="transparent")
        health_frame.pack(fill="x", padx=20, pady=(0, 5))
        ctk.CTkLabel(health_frame, text="System Health", font=theme.FONT_BODY_BOLD,
                     text_color=theme.INK).pack(side="left")
        ctk.CTkButton(health_frame, text="Verify Database", command=lambda: self._run_health_check(health_results_box),
                      fg_color=theme.BRASS, hover_color=theme.INK, font=theme.FONT_SMALL, height=24, width=130).pack(side="right")

        health_results_box = ctk.CTkTextbox(win, fg_color=theme.WHITE, text_color=theme.INK,
                                            wrap="word", height=110)
        health_results_box.pack(fill="x", padx=20, pady=(0, 10))
        health_results_box.insert("end", "Click 'Verify Database' to run integrity, foreign key, orphan-record, "
                                          "duplicate-code, migration, and backup checks.")
        health_results_box.configure(state="disabled")

        ctk.CTkLabel(win, text="Version History", font=theme.FONT_BODY_BOLD,
                     text_color=theme.INK).pack(anchor="w", padx=20, pady=(5, 5))
        box = ctk.CTkTextbox(win, fg_color=theme.WHITE, text_color=theme.INK, wrap="word")
        box.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        for ver, notes in reversed(version.CHANGELOG):
            box.insert("end", f"v{ver}\n{notes}\n\n")
        box.configure(state="disabled")

    def _run_health_check(self, results_box):
        import health_check
        results = health_check.run_health_check()
        icon = {"ok": "✔", "warning": "⚠", "error": "✘"}
        results_box.configure(state="normal")
        results_box.delete("1.0", "end")
        for name, status, detail in results:
            results_box.insert("end", f"{icon[status]} {name}: {detail}\n")
        results_box.configure(state="disabled")

    def show(self, name):
        for frame in self.screens.values():
            frame.pack_forget()
        frame = self.screens[name]
        frame.pack(fill="both", expand=True)
        if hasattr(frame, "refresh"):
            frame.refresh()
        # Dashboard has no refresh() method (it queries fresh data in __init__ each time);
        # rebuild it cheaply so its stats and activity feed are current on every visit
        if name == "Dashboard":
            frame.destroy()
            new_frame = DashboardScreen(self.container, app=self)
            self.screens["Dashboard"] = new_frame
            new_frame.pack(fill="both", expand=True)

        for btn_name, btn in self.nav_buttons.items():
            if btn_name == name:
                btn.configure(fg_color=theme.BRASS, text_color=theme.WHITE)
            else:
                btn.configure(fg_color="transparent", text_color=theme.WHITE)


if __name__ == "__main__":
    app = App()
    app.mainloop()

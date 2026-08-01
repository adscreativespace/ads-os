"""
ADS OS Desktop -- Proposal Builder (completes Fee Calculation -> Proposal ->
Invoice). Every commercial number comes directly from a selected Fee
Calculation -- never re-entered or recalculated here. Deliverables are
pulled live from the real Package assembly logic (Sprint 1), not a
fabricated checklist.

Deliberately narrower than the reference mockups/spec. Built: base
calculation selection, auto-numbered Proposal No., Cover Letter/Scope/Terms
as editable text (with sensible defaults, not master-template libraries that
don't exist), real Deliverables from the project's package, editable Payment
Terms (% of Total Fee), and PDF generation reusing the same branding/font
infrastructure as the Project Summary Report.

NOT built, with reasons:
  - Multiple visual PDF templates (Modern/Luxury/Corporate/Government/etc.)
    -- one polished template is built; template *selection* needs genuinely
    distinct designs, not just relabeled color swaps.
  - Version History / Comparison View -- RevisionNo exists on the table from
    day one so this can be added later without a schema change, but the
    full multi-version diff UI is separate future work.
  - Attachments (mood boards, site photos) -- no file-attachment
    infrastructure exists anywhere in the app yet.
  - Email sending -- explicitly deferred in the source spec too.
  - Scope of Work / Terms & Conditions as selectable checkbox master
    libraries -- implemented as editable free text with one sensible
    default instead, since a master-template management system is its own
    feature with no real content behind it yet.
  - Timeline (project schedule in days) -- no real duration-tracking data
    exists to seed this meaningfully; fabricating placeholder day-counts
    would be inventing data.
"""
import customtkinter as ctk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
import os
import sys
import subprocess
import datetime
import db
import theme
import report_engine

PROPOSAL_STATUS_OPTIONS = ["Draft", "Sent", "Accepted", "Rejected", "Expired"]
STATUS_COLORS = {"Draft": "#6B6B6B", "Sent": "#1E5FA8", "Accepted": "#2E8B57",
                  "Rejected": "#8B2E2E", "Expired": "#8B2E2E"}

DEFAULT_SCOPE = ("We will provide complete architectural and interior design consultancy services "
                  "for the project, including planning, design, documentation, and coordination as "
                  "per the scope defined in this proposal.")
DEFAULT_TERMS = ("This proposal is valid for the period stated above. Fees are exclusive of GST unless "
                  "stated otherwise. Any changes in scope, area, or client requirements after approval "
                  "may affect the fees and timeline. Payments are to be made as per the schedule below. "
                  "Statutory fees, government charges, and site survey/soil testing costs (if required) "
                  "are not included in this proposal.")
DEFAULT_PAYMENT_TERMS = [
    ("Booking / Advance", 20), ("Concept Design Approval", 20),
    ("Working Drawings", 30), ("Execution Support", 20), ("Completion", 10),
]

PROPOSALS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Proposals")


class ProposalBuilderPanel(ctk.CTkFrame):
    def __init__(self, master, project_id):
        super().__init__(master, fg_color="transparent")
        self.project_id = project_id
        self.project = db.fetch_one("""
            SELECT p.*, c.ClientName FROM tblProject p JOIN tblClient c ON p.ClientID = c.ClientID
            WHERE p.ProjectID=?
        """, (project_id,))
        self.fee_calcs = db.fetch_all(
            "SELECT CalculationID, CalculationName, TotalFee FROM trxFeeCalculation WHERE ProjectID=? ORDER BY CalculationID DESC",
            (project_id,))
        self._build_ui()
        self.refresh_history()

    def _build_ui(self):
        ctk.CTkLabel(self, text="Proposal Builder", font=theme.FONT_HEADING, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 5))
        ctk.CTkLabel(self, text="Create a client-facing proposal directly from a saved Fee Calculation.",
                     font=theme.FONT_SMALL, text_color=theme.MUTED).pack(anchor="w", padx=20, pady=(0, 10))

        if not self.fee_calcs:
            ctk.CTkLabel(self, text="No saved Fee Calculations yet for this project.\n"
                                     "Go to Fee Calculator, calculate and save one first -- Proposal Builder "
                                     "always starts from a real Fee Calculation, never a blank form.",
                         font=theme.FONT_BODY, text_color=theme.MUTED, justify="left").pack(
                anchor="w", padx=20, pady=20)
            return

        columns = ctk.CTkFrame(self, fg_color="transparent")
        columns.pack(fill="both", expand=True, padx=20)

        left = ctk.CTkFrame(columns, fg_color=theme.WHITE, corner_radius=8)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        left.grid_columnconfigure(1, weight=1)  # field column stretches with the window instead of staying fixed at 280px
        right = ctk.CTkFrame(columns, fg_color=theme.WHITE, corner_radius=8, width=340)
        right.pack(side="left", fill="y")
        right.pack_propagate(False)

        row = 0
        ctk.CTkLabel(left, text="Proposal Information", font=theme.FONT_BODY_BOLD, text_color=theme.INK).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=15, pady=(15, 10))
        row += 1

        ctk.CTkLabel(left, text="Base Fee Calculation *", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        calc_names = [f"{c['CalculationName']} (₹{c['TotalFee']:,.2f})" for c in self.fee_calcs]
        self.calc_var = ctk.StringVar(value=calc_names[0])
        ctk.CTkOptionMenu(left, values=calc_names, variable=self.calc_var).grid(
            row=row, column=1, padx=15, pady=6, sticky="ew")
        row += 1

        ctk.CTkLabel(left, text="Proposal Date", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        self.date_entry = DateEntry(left, width=20, date_pattern="yyyy-mm-dd", background=theme.BRASS,
                                    foreground="white", borderwidth=1, headersbackground=theme.INK,
                                    headersforeground="white", selectbackground=theme.BRASS)
        self.date_entry.grid(row=row, column=1, padx=15, pady=6, sticky="w")
        row += 1

        ctk.CTkLabel(left, text="Valid Till", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        self.valid_entry = DateEntry(left, width=20, date_pattern="yyyy-mm-dd", background=theme.BRASS,
                                     foreground="white", borderwidth=1, headersbackground=theme.INK,
                                     headersforeground="white", selectbackground=theme.BRASS)
        self.valid_entry.set_date(datetime.date.today() + datetime.timedelta(days=15))
        self.valid_entry.grid(row=row, column=1, padx=15, pady=6, sticky="w")
        row += 1

        ctk.CTkLabel(left, text="Status", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="w", padx=15, pady=6)
        self.status_var = ctk.StringVar(value="Draft")
        ctk.CTkOptionMenu(left, values=PROPOSAL_STATUS_OPTIONS, variable=self.status_var).grid(
            row=row, column=1, padx=15, pady=6, sticky="ew")
        row += 1

        # Cover Letter, Scope of Work, and Terms & Conditions are the fields
        # people actually write real paragraphs into -- previously only ~4
        # visible lines regardless of content length or window size. Now
        # substantially taller and, since their parent row is weighted,
        # stretch vertically too when the window is resized.
        left.grid_rowconfigure(row, weight=2)
        ctk.CTkLabel(left, text="Cover Letter", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="nw", padx=15, pady=6)
        self.cover_text = ctk.CTkTextbox(left, height=220)
        self.cover_text.insert("1.0", f"Dear {self.project['ClientName']},\n\nThank you for considering ADS "
                                       f"Creative Space for your project. We are pleased to submit this proposal.")
        self.cover_text.grid(row=row, column=1, padx=15, pady=6, sticky="nsew")
        row += 1

        left.grid_rowconfigure(row, weight=2)
        ctk.CTkLabel(left, text="Scope of Work", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="nw", padx=15, pady=6)
        self.scope_text = ctk.CTkTextbox(left, height=180)
        self.scope_text.insert("1.0", DEFAULT_SCOPE)
        self.scope_text.grid(row=row, column=1, padx=15, pady=6, sticky="nsew")
        row += 1

        left.grid_rowconfigure(row, weight=1)
        ctk.CTkLabel(left, text="Terms & Conditions", font=theme.FONT_BODY, text_color=theme.INK).grid(
            row=row, column=0, sticky="nw", padx=15, pady=6)
        self.terms_text = ctk.CTkTextbox(left, height=140)
        self.terms_text.insert("1.0", DEFAULT_TERMS)
        self.terms_text.grid(row=row, column=1, padx=15, pady=6, sticky="nsew")
        row += 1

        ctk.CTkLabel(left, text="Payment Terms (% of Total Fee)", font=theme.FONT_BODY_BOLD, text_color=theme.INK).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=15, pady=(10, 6))
        row += 1
        self.payment_term_rows = []
        for stage_name, pct in DEFAULT_PAYMENT_TERMS:
            term_row = ctk.CTkFrame(left, fg_color="transparent")
            term_row.grid(row=row, column=0, columnspan=2, sticky="w", padx=15, pady=2)
            name_entry = ctk.CTkEntry(term_row, width=200)
            name_entry.insert(0, stage_name)
            name_entry.pack(side="left", padx=(0, 8))
            pct_entry = ctk.CTkEntry(term_row, width=60)
            pct_entry.insert(0, str(pct))
            pct_entry.pack(side="left")
            ctk.CTkLabel(term_row, text="%", font=theme.FONT_SMALL, text_color=theme.MUTED).pack(side="left", padx=(4, 0))
            self.payment_term_rows.append((name_entry, pct_entry))
            row += 1

        ctk.CTkButton(left, text="Save Proposal", command=self.save_proposal, fg_color=theme.BRASS,
                      hover_color=theme.INK, font=theme.FONT_BODY_BOLD).grid(
            row=row, column=0, columnspan=2, pady=20)

        ctk.CTkLabel(right, text="Proposal Summary", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=15, pady=(15, 8))
        self.summary_label = ctk.CTkLabel(right, text="", font=theme.FONT_BODY, text_color=theme.INK, justify="left")
        self.summary_label.pack(anchor="w", padx=15, pady=(0, 15))
        self.calc_var.trace_add("write", lambda *a: self._update_summary())

        ctk.CTkLabel(right, text="Deliverables (from Default Package)", font=theme.FONT_BODY_BOLD,
                     text_color=theme.INK).pack(anchor="w", padx=15, pady=(0, 8))
        self.deliverables_label = ctk.CTkLabel(right, text="", font=theme.FONT_SMALL, text_color=theme.INK,
                                               justify="left", wraplength=280)
        self.deliverables_label.pack(anchor="w", padx=15, pady=(0, 15))

        self._update_summary()
        self._load_deliverables_preview()

        ctk.CTkLabel(self, text="Saved Proposals", font=theme.FONT_BODY_BOLD, text_color=theme.INK).pack(
            anchor="w", padx=20, pady=(15, 5))
        history_frame = ctk.CTkFrame(self, fg_color=theme.WHITE)
        history_frame.pack(fill="x", padx=20, pady=(0, 10))
        cols = ("no", "date", "status", "fee")
        self.history_tree = ttk.Treeview(history_frame, columns=cols, show="headings", height=5)
        headings = {"no": "Proposal No.", "date": "Date", "status": "Status", "fee": "Total Fee (₹)"}
        for c in cols:
            self.history_tree.heading(c, text=headings[c])
            self.history_tree.column(c, width=150)
        self.history_tree.pack(fill="x", padx=5, pady=5)
        for status, color in STATUS_COLORS.items():
            self.history_tree.tag_configure(f"status_{status}", foreground=color)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 15))
        ctk.CTkButton(footer, text="Generate PDF for Selected", command=self.generate_pdf,
                      fg_color=theme.BRASS, hover_color=theme.INK, font=theme.FONT_SMALL, height=28).pack(side="left")

    def _selected_calc(self):
        idx = [f"{c['CalculationName']} (₹{c['TotalFee']:,.2f})" for c in self.fee_calcs].index(self.calc_var.get())
        return self.fee_calcs[idx]

    def _update_summary(self):
        calc = self._selected_calc()
        package_name = "Not set"
        if self.project["DefaultPackageID"]:
            pkg = db.fetch_one("SELECT PackageName FROM mstPackage WHERE PackageID=?", (self.project["DefaultPackageID"],))
            if pkg:
                package_name = pkg["PackageName"]

        line_items = db.fetch_all(
            "SELECT ServiceName FROM trxFeeCalculationItem i JOIN mstService s ON i.ServiceID=s.ServiceID WHERE CalculationID=?",
            (calc["CalculationID"],))
        services_text = "\n".join(f"✔ {i['ServiceName']}" for i in line_items) if line_items else "-"

        # Read the LIVE payment term entries, not the static defaults --
        # the user may have edited stage names/percentages before this
        # summary is shown. Guarded since this can fire (via calc_var's
        # trace) before payment_term_rows exists yet during initial build.
        if hasattr(self, "payment_term_rows"):
            payment_schedule = "\n".join(
                f"{name_entry.get().strip()}: {pct_entry.get().strip()}%"
                for name_entry, pct_entry in self.payment_term_rows if name_entry.get().strip())
        else:
            payment_schedule = "\n".join(f"{name}: {pct}%" for name, pct in DEFAULT_PAYMENT_TERMS)

        summary_text = (
            f"Client: {self.project['ClientName']}\n"
            f"Project: {self.project['ProjectName']}\n"
            f"Package: {package_name}\n\n"
            f"Selected Services:\n{services_text}\n\n"
            f"Total Fee: ₹{calc['TotalFee']:,.2f}\n\n"
            f"Payment Schedule:\n{payment_schedule}"
        )
        self.summary_label.configure(text=summary_text)

    def _load_deliverables_preview(self):
        if not self.project["DefaultPackageID"]:
            self.deliverables_label.configure(text="No Default Package set on this project -- no deliverables to show.")
            return
        deliverables = report_engine._assemble_package_deliverables(self.project["DefaultPackageID"])
        if not deliverables:
            self.deliverables_label.configure(text="No deliverables defined for this package yet.")
            return
        lines = []
        for category, items in deliverables.items():
            lines.append(f"{category}:")
            for item in items:
                lines.append(f"  • {item}")
        self.deliverables_label.configure(text="\n".join(lines))

    def save_proposal(self):
        calc = self._selected_calc()
        proposal_date = self.date_entry.get_date().isoformat()
        valid_till = self.valid_entry.get_date().isoformat()
        cover_letter = self.cover_text.get("1.0", "end").strip()
        scope = self.scope_text.get("1.0", "end").strip()
        terms = self.terms_text.get("1.0", "end").strip()

        total_pct = 0
        term_rows_data = []
        for i, (name_entry, pct_entry) in enumerate(self.payment_term_rows):
            name = name_entry.get().strip()
            try:
                pct = float(pct_entry.get().strip() or 0)
            except ValueError:
                messagebox.showerror("Invalid number", f"Payment term '{name}' has an invalid percentage.", parent=self)
                return
            if name:
                term_rows_data.append((name, pct, i))
                total_pct += pct

        if abs(total_pct - 100) > 0.5:
            if not messagebox.askyesno("Payment terms don't total 100%",
                                        f"Payment terms currently total {total_pct:.1f}%, not 100%. Save anyway?", parent=self):
                return

        proposal_no = db.next_code("PROP", "trxProposal", "ProposalNo")
        # Snapshot the package NOW -- fixes a confirmed bug where proposals
        # read the project's live DefaultPackageID, so a later package change
        # would silently alter what an already-created proposal showed when
        # reprinted. Same copy-not-reference discipline as BR-002.
        project = db.fetch_one("SELECT DefaultPackageID FROM tblProject WHERE ProjectID=?", (self.project_id,))
        proposal_id = db.execute(
            """INSERT INTO trxProposal (ProjectID, CalculationID, ProposalNo, ProposalDate, ValidTill, Status,
               CoverLetter, ScopeOfWork, TermsConditions, PackageID) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (self.project_id, calc["CalculationID"], proposal_no, proposal_date, valid_till,
             self.status_var.get(), cover_letter, scope, terms, project["DefaultPackageID"])
        )
        for name, pct, order in term_rows_data:
            db.execute("INSERT INTO trxProposalPaymentTerm (ProposalID, StageName, Percent, StageOrder) VALUES (?,?,?,?)",
                      (proposal_id, name, pct, order))

        db.log_activity("Project", self.project_id, "Proposal Created", proposal_no)
        messagebox.showinfo("Proposal saved", f"{proposal_no} saved successfully.", parent=self)
        self.refresh_history()

    def refresh_history(self):
        if not self.fee_calcs:
            return
        for row in self.history_tree.get_children():
            self.history_tree.delete(row)
        proposals = db.fetch_all("""
            SELECT p.*, f.TotalFee FROM trxProposal p LEFT JOIN trxFeeCalculation f ON p.CalculationID = f.CalculationID
            WHERE p.ProjectID=? ORDER BY p.ProposalID DESC
        """, (self.project_id,))
        for p in proposals:
            self.history_tree.insert("", "end", iid=p["ProposalID"],
                                     values=(p["ProposalNo"], p["ProposalDate"], p["Status"],
                                            f"{p['TotalFee']:,.2f}" if p["TotalFee"] else "-"),
                                     tags=(f"status_{p['Status']}",))

    def generate_pdf(self):
        sel = self.history_tree.selection()
        if not sel:
            messagebox.showinfo("Select a proposal", "Please select a saved proposal from the list first.", parent=self)
            return
        proposal_id = int(sel[0])
        os.makedirs(PROPOSALS_DIR, exist_ok=True)
        proposal = db.fetch_one("SELECT ProposalNo FROM trxProposal WHERE ProposalID=?", (proposal_id,))
        filename = f"{proposal['ProposalNo']}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        output_path = os.path.join(PROPOSALS_DIR, filename)

        try:
            report_engine.generate_proposal_pdf(proposal_id, output_path)
        except Exception as e:
            messagebox.showerror("PDF generation failed", f"Could not generate the proposal PDF:\n{e}", parent=self)
            return

        db.log_activity("Project", self.project_id, "Proposal PDF Generated", filename)
        if messagebox.askyesno("PDF generated", f"Saved to:\n{output_path}\n\nOpen it now?", parent=self):
            try:
                if sys.platform == "win32":
                    os.startfile(output_path)
                elif sys.platform == "darwin":
                    subprocess.run(["open", output_path])
                else:
                    subprocess.run(["xdg-open", output_path])
            except Exception as e:
                messagebox.showwarning("Couldn't open automatically", f"Saved, but couldn't open it:\n{e}", parent=self)

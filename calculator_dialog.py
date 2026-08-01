"""
ADS OS Desktop -- ADS Calculator (v4.5.0)
A floating utility, not a module -- launched from the Project Workspace
header, available regardless of which tab (Planning/Commercial/etc.) is
active. Deliberately NON-modal (no grab_set(), unlike every other dialog in
this app) so it can stay open while the user keeps working elsewhere in the
workspace.

CalculatorEngine (the arithmetic) is a separate, pure-Python class from the
Tkinter wrapper specifically so the math can be tested by actually running
it -- caught a real bug this way: Clear (C) was resetting memory too, but
real calculator behavior is that only MC clears memory, C only clears the
current calculation.

v4.5.0 scope, per explicit instruction: Standard mode only. A Mode selector
exists in the UI (Standard/Advanced) so the layout doesn't need to be
redesigned later, but Advanced is disabled with a "Coming Soon" state --
not implemented now. No history persistence, no BOQ/Contract field
integration, no database impact of any kind.
"""
import customtkinter as ctk
import theme


class CalculatorEngine:
    """
    Pure calculation logic, deliberately separate from the UI. Matches
    standard calculator behavior (Windows Calculator-like): chained
    operators apply the pending operation immediately rather than queuing,
    repeated operator presses just swap the pending one, Clear Entry (CE)
    only resets the current number while preserving a pending operator,
    and Clear (C) resets the calculation but never touches memory.
    """
    def __init__(self):
        self.display = "0"
        self.stored_value = None
        self.pending_operator = None
        self.new_entry = True
        self.memory = 0.0

    def input_digit(self, digit):
        if self.new_entry:
            self.display = digit
            self.new_entry = False
        else:
            self.display = digit if self.display == "0" else self.display + digit

    def input_decimal(self):
        if self.new_entry:
            self.display = "0."
            self.new_entry = False
        elif "." not in self.display:
            self.display += "."

    def _apply(self, a, b, op):
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            if b == 0:
                raise ZeroDivisionError
            return a / b

    def input_operator(self, op):
        current = float(self.display)
        if self.pending_operator and not self.new_entry:
            try:
                result = self._apply(self.stored_value, current, self.pending_operator)
            except ZeroDivisionError:
                self.display, self.stored_value, self.pending_operator, self.new_entry = "Error", None, None, True
                return
            self.stored_value = result
            self.display = self._format(result)
        else:
            self.stored_value = current
        self.pending_operator = op
        self.new_entry = True

    def input_equals(self):
        if self.pending_operator is None:
            return
        current = float(self.display)
        try:
            result = self._apply(self.stored_value, current, self.pending_operator)
        except ZeroDivisionError:
            self.display, self.stored_value, self.pending_operator, self.new_entry = "Error", None, None, True
            return
        self.display = self._format(result)
        self.stored_value, self.pending_operator, self.new_entry = None, None, True

    def clear(self):
        self.display = "0"
        self.stored_value = None
        self.pending_operator = None
        self.new_entry = True

    def clear_entry(self):
        self.display = "0"
        self.new_entry = True

    def backspace(self):
        if self.new_entry:
            return
        self.display = self.display[:-1] or "0"
        if self.display in ("", "-"):
            self.display, self.new_entry = "0", True

    def negate(self):
        if self.display.startswith("-"):
            self.display = self.display[1:]
        elif self.display != "0":
            self.display = "-" + self.display

    def memory_clear(self):
        self.memory = 0.0

    def memory_recall(self):
        self.display = self._format(self.memory)
        self.new_entry = True

    def memory_store(self):
        self.memory = float(self.display)

    def memory_add(self):
        self.memory += float(self.display)

    def memory_subtract(self):
        self.memory -= float(self.display)

    def _format(self, value):
        if value == int(value) and abs(value) < 1e15:
            return str(int(value))
        return f"{value:.10g}"


class CalculatorDialog(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.engine = CalculatorEngine()

        self.title("Calculator")
        self.geometry("280x420")
        self.resizable(False, False)
        self.configure(fg_color=theme.PARCHMENT)
        # Deliberately NOT modal (no grab_set()) -- this should stay open
        # and usable while the person keeps working in the rest of the
        # Project Workspace, unlike every other dialog in this app.
        self.attributes("-topmost", True)
        self.transient(self.master.winfo_toplevel())

        # ---------------- Mode selector (Standard only for v4.5.0) ----------------
        mode_row = ctk.CTkFrame(self, fg_color="transparent")
        mode_row.pack(fill="x", padx=10, pady=(10, 5))
        self.mode_var = ctk.StringVar(value="Standard")
        ctk.CTkSegmentedButton(mode_row, values=["Standard", "Advanced (Soon)"], variable=self.mode_var,
                               command=self._on_mode_change, fg_color=theme.WHITE, selected_color=theme.BRASS,
                               unselected_color=theme.WHITE, text_color=theme.INK,
                               selected_hover_color=theme.INK, font=("Segoe UI", 9)).pack(fill="x")

        # ---------------- Display ----------------
        self.display_label = ctk.CTkLabel(self, text="0", font=("Consolas", 26, "bold"), text_color=theme.INK,
                                          anchor="e", fg_color=theme.WHITE, corner_radius=6, height=50)
        self.display_label.pack(fill="x", padx=10, pady=(5, 5))

        self.memory_indicator = ctk.CTkLabel(self, text="", font=("Segoe UI", 9), text_color=theme.MUTED, anchor="w")
        self.memory_indicator.pack(fill="x", padx=12)

        # ---------------- Copy Result ----------------
        ctk.CTkButton(self, text="Copy Result", command=self._copy_result, fg_color=theme.MUTED,
                     hover_color=theme.INK, font=("Segoe UI", 10), height=24).pack(fill="x", padx=10, pady=(2, 8))

        # ---------------- Memory row ----------------
        mem_row = ctk.CTkFrame(self, fg_color="transparent")
        mem_row.pack(fill="x", padx=10, pady=(0, 6))
        for label, cmd in [("MC", self._mc), ("MR", self._mr), ("MS", self._ms),
                           ("M+", self._m_plus), ("M-", self._m_minus)]:
            ctk.CTkButton(mem_row, text=label, command=cmd, fg_color=theme.INK, hover_color=theme.BRASS,
                         font=("Segoe UI", 10), width=44, height=28).pack(side="left", padx=2, expand=True)

        # ---------------- Keypad ----------------
        keypad = ctk.CTkFrame(self, fg_color="transparent")
        keypad.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        for i in range(4):
            keypad.grid_columnconfigure(i, weight=1)
        for i in range(5):
            keypad.grid_rowconfigure(i, weight=1)

        rows = [
            [("CE", self._ce, theme.MUTED), ("C", self._c, theme.MUTED),
             ("⌫", self._backspace, theme.MUTED), ("÷", lambda: self._op("/"), theme.BRASS)],
            [("7", lambda: self._digit("7"), theme.WHITE), ("8", lambda: self._digit("8"), theme.WHITE),
             ("9", lambda: self._digit("9"), theme.WHITE), ("×", lambda: self._op("*"), theme.BRASS)],
            [("4", lambda: self._digit("4"), theme.WHITE), ("5", lambda: self._digit("5"), theme.WHITE),
             ("6", lambda: self._digit("6"), theme.WHITE), ("-", lambda: self._op("-"), theme.BRASS)],
            [("1", lambda: self._digit("1"), theme.WHITE), ("2", lambda: self._digit("2"), theme.WHITE),
             ("3", lambda: self._digit("3"), theme.WHITE), ("+", lambda: self._op("+"), theme.BRASS)],
            [("±", self._negate, theme.WHITE), ("0", lambda: self._digit("0"), theme.WHITE),
             (".", self._decimal, theme.WHITE), ("=", self._equals, theme.BRASS)],
        ]
        for r, row in enumerate(rows):
            for c, (label, cmd, color) in enumerate(row):
                text_color = theme.WHITE if color in (theme.MUTED, theme.BRASS) else theme.INK
                ctk.CTkButton(keypad, text=label, command=cmd, fg_color=color, hover_color=theme.INK,
                             text_color=text_color, font=("Segoe UI", 14), corner_radius=6).grid(
                    row=r, column=c, sticky="nsew", padx=2, pady=2)

        # ---------------- Keyboard support (mandatory, not optional) ----------------
        # Bound at the window level so it works the instant the calculator
        # opens, without needing to click into a specific widget first.
        for digit in "0123456789":
            self.bind(digit, lambda e, d=digit: self._digit(d))
        # Explicit numpad bindings rather than assuming KP_0-9 generate the
        # same character events as top-row digits -- that overlap isn't
        # guaranteed across keyboard drivers/platforms, and numpad support
        # was called out as mandatory, not incidental.
        for i in range(10):
            self.bind(f"<KP_{i}>", lambda e, d=str(i): self._digit(d))
        self.bind("<period>", lambda e: self._decimal())
        self.bind("<KP_Decimal>", lambda e: self._decimal())
        self.bind("+", lambda e: self._op("+"))
        self.bind("-", lambda e: self._op("-"))
        self.bind("*", lambda e: self._op("*"))
        self.bind("/", lambda e: self._op("/"))
        self.bind("<KP_Add>", lambda e: self._op("+"))
        self.bind("<KP_Subtract>", lambda e: self._op("-"))
        self.bind("<KP_Multiply>", lambda e: self._op("*"))
        self.bind("<KP_Divide>", lambda e: self._op("/"))
        self.bind("<Return>", lambda e: self._equals())
        self.bind("<KP_Enter>", lambda e: self._equals())
        self.bind("=", lambda e: self._equals())
        self.bind("<BackSpace>", lambda e: self._backspace())
        self.bind("<Delete>", lambda e: self._c())
        self.bind("<Escape>", lambda e: self.destroy())

        # Focus immediately so keyboard/numpad input works without a mouse
        # click first, per explicit requirement.
        self.focus_force()

    # ---------------- Engine-backed handlers ----------------
    def _refresh_display(self):
        self.display_label.configure(text=self.engine.display)
        self.memory_indicator.configure(text="M" if self.engine.memory else "")

    def _digit(self, d):
        self.engine.input_digit(d)
        self._refresh_display()

    def _decimal(self):
        self.engine.input_decimal()
        self._refresh_display()

    def _op(self, op):
        self.engine.input_operator(op)
        self._refresh_display()

    def _equals(self):
        self.engine.input_equals()
        self._refresh_display()

    def _c(self):
        self.engine.clear()
        self._refresh_display()

    def _ce(self):
        self.engine.clear_entry()
        self._refresh_display()

    def _backspace(self):
        self.engine.backspace()
        self._refresh_display()

    def _negate(self):
        self.engine.negate()
        self._refresh_display()

    def _mc(self):
        self.engine.memory_clear()
        self._refresh_display()

    def _mr(self):
        self.engine.memory_recall()
        self._refresh_display()

    def _ms(self):
        self.engine.memory_store()
        self._refresh_display()

    def _m_plus(self):
        self.engine.memory_add()
        self._refresh_display()

    def _m_minus(self):
        self.engine.memory_subtract()
        self._refresh_display()

    def _copy_result(self):
        self.clipboard_clear()
        self.clipboard_append(self.engine.display)

    def _on_mode_change(self, choice):
        if choice != "Standard":
            # Explicitly not implemented in v4.5.0 -- revert selection and
            # leave the layout ready for a real Advanced mode later without
            # needing to redesign this dialog.
            self.mode_var.set("Standard")

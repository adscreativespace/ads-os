# ADS OS — Regression Checklist

Run before every release, alongside the automated tests already run during
development. This exists because "I tested the new feature" and "I confirmed
nothing else broke" are different claims -- this file is for the second one.

Update this list whenever a new module or workflow is added; delete items
only when the underlying feature is genuinely retired, not just untested
this round.

---

## Startup
- [ ] No TclError or other crash on launch
- [ ] Sidebar loads with all icons visible
- [ ] Logo visible
- [ ] Database Health indicator shows (not stuck loading)

## Navigation
- [ ] Dashboard loads
- [ ] Clients loads
- [ ] Projects loads
- [ ] Current Project section shows correctly (or "Select a Project" if none set)
- [ ] Opening a project via Projects → Open Workspace updates the sidebar's Current Project
- [ ] Sidebar's Current Project sub-items (Overview/Planning/Design/Commercial/Execution/Activity) each open the correct tab
- [ ] All 6 Project Workspace tabs actually render content immediately on open --
      not just navigable, genuinely showing something, not blank (this specific
      check exists because of the v4.5.0/v4.5.0a/v4.5.0b Calculator regression,
      where the tabs were navigable in the UI sense but the content behind them
      had never actually been built)
- [ ] Calculator opens from the Project Workspace header, closes cleanly, and the
      workspace stays fully responsive throughout (click into another tab while
      it's still open)
- [ ] Reopen the same tab/dialog several times in a row -- content does not
      duplicate or stack (the exact symptom of the v4.5.0a/b regression;
      cheap enough to check explicitly rather than rely on catching it by luck)

## Clients
- [ ] Add Client
- [ ] Edit Client
- [ ] Delete Client (with no dependent projects)
- [ ] Search / filter works

## Projects
- [ ] Add Project
- [ ] Edit Project
- [ ] Card View / Table View toggle
- [ ] Export CSV

## Commercial
- [ ] Dashboard (landing page) loads with real KPIs, no crash
- [ ] Quick Actions open the correct existing dialogs
- [ ] Fee Calculator: calculate + save
- [ ] Proposal Builder: generate PDF from a saved Fee Calculation
- [ ] Vendors: add/edit/delete, Partner Type saves correctly
- [ ] Materials: add/edit, Vendor column shows correctly
- [ ] New Purchase: works without pre-selecting a Material
- [ ] BOQ: add item, Link to Material auto-fills correctly
- [ ] Invoice Center: create invoice, record payment, status updates correctly
- [ ] Reports: real aggregated numbers, no crash

## Persistence
- [ ] Current Project survives a full app restart (close completely, reopen)
- [ ] Recent Projects list updates after opening a new project

## Database
- [ ] Health Check (About ADS OS) shows fully up to date, no missing migrations
- [ ] Real client/project data confirmed intact after the update
- [ ] Backup was taken before applying the update

## Cross-Project Sanity (where practical)
- [ ] Core changes (new modules, schema changes, Commercial/Contract logic)
      re-tested against a SECOND real project, not just BJP Party Office --
      one project's data shape can hide a bug a second project reveals
      (e.g. a Running contract with no ContractAmount, a client with no
      email, a vendor with multiple scopes). Not required for small,
      narrowly-scoped fixes -- use judgment, but default to doing it for
      anything touching business logic.

---

## UI Structure Verification (for any file with significant edits)
Second time an indentation/scope mistake has caused a real regression
(BOQ's `table_frame`, then the entire tabview getting absorbed into
`_open_calculator`). `py_compile` cannot catch either class of bug -- both
are syntactically valid Python that just does the wrong thing. Before
shipping any file with a non-trivial edit:
- [ ] Does `__init__` still end where expected -- not swallowed by a method
      inserted partway through it?
- [ ] Did any new/edited method accidentally absorb code that follows it,
      because it landed at the same indentation level?
- [ ] For classes with delegated construction (`__init__` calling
      `_build_ui()`), does that delegation still actually happen?

A quick, real check for this (used to catch the `_open_calculator` bug):
parse the file with `ast`, list each method's line range, and look for any
small-sounding handler (`_open_*`, `_on_*`, `toggle_*`) that's implausibly
large for its name, or any `__init__` that's suspiciously short *without*
delegating to a real `_build_*` method. Both are real signs code landed in
the wrong scope.

---

Severity of anything found: see `RELEASE_GATES.md` (P0 blocks release, P1
needs explicit sign-off, P2/P3 can ship and get logged).


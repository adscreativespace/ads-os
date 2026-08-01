# ADS OS — Known Issues

A record of real, verified issues — fixed and deferred — so they don't get
rediscovered and re-debated from scratch. Only genuine, confirmed issues go
here, not speculative "might be a problem" notes.

---

### Fixed in 3.9.1 — Migration Registry not self-registering for Commercial modules
All six Commercial module migrations (`migrate_v300_fee_calculator` through
`migrate_v350_proposals`) built real tables correctly but never called the
self-registration function, so the Database Health indicator showed a
warning from v3.0.0 onward without it being noticed until the health check
was actually read closely. All 6 scripts now self-register; verified by
re-running each and confirming the registry reaches 16/16.

### Fixed in 4.1.1 — Vendors crash presenting as "kicked back to Projects"
What looked like a Tkinter modal-window/navigation bug (Save/Delete in
Materials/Vendors dropping back to the Projects list) was very likely the
v4.1.0 VendorType/PartnerType dead-code crash the whole time -- an uncaught
IndexError firing mid-render inside VendorsPanel can present to a real user
as broken navigation rather than an obvious error dialog. Once the crash
itself was fixed in 4.1.1, the navigation symptom stopped reproducing in
every test since, including on the real project (ID 33) with real vendors
and materials. The `self.transient()` anchoring fix applied preemptively in
v4.1.0 (based on a plausible but ultimately unconfirmed nested-Toplevel
hypothesis) was likely not the actual fix -- left in place since it's
harmless standard practice, but the crash fix is what mattered. Caveat:
verification was via real, visible windows driven programmatically, not
live mouse clicks -- treating this as resolved unless it recurs during
actual use.

### Fixed in 4.1.0 — Purchase required a pre-existing Material
Real usage feedback: buying something required selecting a Material first,
which doesn't match how procurement actually works (you get a vendor bill
with items, some new, some restocks). New "New Purchase" flow starts from
Vendor + Bill No and auto-creates-or-matches materials by name.

### Fixed in 4.1.0 — BOQ duplicated Material data
Real usage feedback: adding a BOQ item required retyping the same
Description/Vendor/Rate already entered in Materials, with no connection
between "Item Code" and "Material Code" for the same physical item. BOQ
items can now link to a real Material via a dropdown that auto-fills those
fields; new trxBOQItem.MaterialID column.

### Fixed in 4.1.0 — Vendor missing from Materials table, no phone validation, empty category list
Three separate real bugs from actual use: the Materials table's query
already joined Vendor but never displayed it; the Vendor Phone field had no
digit validation (unlike Client, which already had it); the Vendor Category
dropdown only ever showed "General" since it's user-populated and starts
empty. All three fixed.

---

### Unverified — dialogs may return to the Projects window after Save/Delete
Reported via real usage. Could not be reproduced in this development
sandbox (no live GUI available here). Code comparison found the affected
dialogs (Material/Vendor/BOQ forms) are nested 6-7 levels deep inside a
second Toplevel + Tabview, unlike the unaffected Client/Project forms which
are shallow — a known category of Tkinter modal-window bugs. Added
`self.transient()` anchoring as the standard fix in v4.1.0, but this needs
live confirmation before being considered resolved.

---

### Deferred — Upcoming Milestones require a due date
`tblMilestone` has no `DueDate` column, so the Dashboard can't show
milestone urgency ("due in 2 days") the way the reference mockups do.
Real, cheap fix whenever it matters: add a nullable `DueDate` column via an
additive migration, then wire it into the Dashboard.

### Deferred — No task-management system
Several mockups assume a general task engine (Pending Tasks, Task Summary
donut). Nothing like this exists in ADS OS -- Milestones are the closest
real analogue but represent a different concept (project stage-gates, not
day-to-day tasks). Would need a genuine new module, not a relabeling.

### Deferred — Empty states are generic across most modules
BOQ, Materials, Vendors, Invoice Center, Fee Calculator, and Proposal
Builder show plain "0" or empty tables rather than a guided "No X yet --
create your first one" message. Real, worth doing, but a broad shallow
change across 6+ files -- its own separate pass, not bundled into feature
work.

### Deferred — Workspace navigation requires several clicks to reach a module
Reaching Planning/Design/Commercial/Execution today requires: Projects →
double-click a project → Project Workspace → select the tab. This is a real,
valid UX concern for daily use, and a genuine architectural change (a global
"Current Project" concept) has been proposed to address it. Deliberately not
started -- it's a navigation/architecture change, not a UI polish change,
and should be scoped as its own incremental multi-sprint effort only once UI
modernization of the existing screens is further along, per the agreed
phased plan.

### Planned — Materials/BOQ full procurement pipeline
Current Materials/BOQ modules support a simple stock-in purchase log, not
the full Purchase Order → Goods Receipt → Stock Transfer → Return/Damage
workflow from the original reference mockups. Deferred as a separate,
larger feature.

### Planned — Proposal email sending, multi-template selection, version comparison
All explicitly deferred when Proposal Builder was built (v3.6.0) -- see that
changelog entry for the full reasoning on each.

### Planned — Turnkey Projects (conditional workspace by project type)
Real, substantial feedback: ADS OS is currently architect-centric (Fee →
Proposal → Invoice), but the business also executes turnkey work (BOQ →
Materials → Purchase → Labour → Billing → Profit). The right shape: a
Project Type field (Design Consultancy / PMC / Execution / Turnkey) that
determines which Commercial/Execution modules are relevant for that
project. This is a genuine architectural feature, not a quick add --
deserves its own dedicated sprint once Design/Execution modules exist to
integrate with.

### Planned — Calculator inside amount fields
Real, valuable productivity idea (type "200*35", press Enter, get 7000,
instead of alt-tabbing to Windows Calculator). Building a safe expression
evaluator as a reusable input widget across dozens of amount fields is its
own scoped feature -- not bundled into the v4.1.0 bug-fix release.

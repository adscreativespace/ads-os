# ADS OS — Decisions

A record of business/product decisions actually frozen and implemented in ADS OS.
Unlike the ChatGPT session documents (which propose, debate, and often revise ideas
before landing somewhere), this file only records what was genuinely built and is
live in the app today. If a decision is later changed, its entry is updated in place
with a note — this file always reflects current reality, not history of the debate.

Search this before re-litigating a settled question.

---

### D-001 — Sector / Service Split
**Status:** Implemented (v2.0.0)
A project has two independent classifications: **Sector** (what the project IS —
Residential, Healthcare, Airport, 18 total) and **Service** (what you're DOING —
Architectural Design, Interior Design, Renovation, 17 total). Previously these were
conflated into one "Project Type" field. The Space Library is Sector-based, not
Service-based — what spaces exist depends on the building type, not what service
you're providing.

### D-002 — Floor Usage (Mixed-Use Support)
**Status:** Implemented (v1.2.0)
Each Floor has its own Usage (a Sector), defaulting to the project's own Sector but
overridable per floor. This is what lets a single project have a Commercial ground
floor and Residential upper floors, each showing the correct Space Type options.

### D-003 — 5-Tier Package System with Inheritance
**Status:** Implemented (v0.4.0)
Packages: Building Planning → Essential → Essential Plus → Signature → Complete.
Each tier stores only its *new or upgraded* deliverables (not a full copy) — a
`SupersedesDeliverableID` link lets a higher tier's deliverable explicitly replace
a lower tier's version. Rates: ₹20 / ₹25 / ₹30 / ₹70 / ₹110 per sq.ft.
Building Planning and Essential Plus rates were inferred from the Master Rate Card,
not stated directly in the source document — flagged for confirmation, never
corrected, so treat as provisional.

### D-004 — Package is Per-Space, Not Per-Project
**Status:** Implemented (v0.6.0)
A project has a **Default Package**, but each individual Space can override it via
"Use Default Project Package" (unchecked = pick a different package for just that
space). This is what lets a Master Bedroom be Complete while a guest toilet stays
Essential, within the same project.

### D-005 — "Room" → "Space" Terminology
**Status:** Implemented (v1.0.0, UI only)
Not everything is a room (Balcony, Parking, Staircase aren't rooms) — so all
user-facing text says "Space Type" / "Space Name" / "Space Status" instead of
"Room". Database table/column names (`tblRoom`, `RoomName`, `mstRoomLibrary`) were
deliberately NOT renamed — that's an internal detail, renaming it would have been
pure churn with real migration risk for zero user-facing benefit.

### D-006 — Space Type is Locked After Creation
**Status:** Implemented (v2.3.0)
Once a Space exists, its Space Type cannot be changed (only Space Name can, for
renames like "Bedroom 2" → "Guest Room"). Changing what a space fundamentally *is*
after creation risks silently disconnecting it from its library entry and any
future package/deliverable rules tied to that type.

### D-007 — Floor Identity: Level / Display Name / Code
**Status:** Implemented (v0.6.1)
A Floor has three distinct fields, not one: **Floor Level** (structural, drives
ordering — Ground Floor, First Floor...), **Display Name** (what shows on
quotations/drawings — e.g. a hospital's Ground Floor shown as "OPD Block"), and
**Floor Code** (drawing sheet numbering — GF, B1, FF). Previously conflated into a
single "Floor Name" that allowed contradictions like "Third Floor" named "Basement".

### D-008 — Floor & Space Default Ceiling Height
**Status:** Implemented (v2.7.0)
Each Floor has a Default Ceiling Height (starts at 10 ft). New Spaces inherit it
automatically. "Use Floor Default Ceiling Height" checkbox on a Space — checked
(default) locks the height to the floor's value and updates automatically if the
floor default changes; unchecked allows a permanent custom height that's never
touched by floor-level changes.

### D-009 — Add Space: Structure First, Details After
**Status:** Implemented (v2.1.0)
Add Space is a checklist (check spaces, click Generate) with no Area/Package/Status
fields upfront — those are set afterward via Edit Space. Checking a Space that
already exists on the floor auto-numbers it ("Bedroom" → "Bedroom 2"), same pattern
as Windows' "New Folder (2)". No dialog, no quantity field. A "Duplicate Space"
button separately copies a space's full configured details when needed.

### D-010 — Space Library is Curated, Not Exhaustive by Default
**Status:** Implemented (v1.4.0)
Add Space shows a short "common spaces" list per Sector (e.g. 20 for Residential)
rather than the full library (113 for Residential) by default. "Show Full Library"
reveals everything when needed. Full libraries were seeded using standard
architectural terminology (v1.1.0) — a Materials/Furniture library was deliberately
NOT seeded, since that needs your actual vendor/product choices to be useful,
not generic placeholder names.

### D-011 — Client: Priority + Calculated Relationship, No Tags
**Status:** Implemented (v2.2.0)
Client Tags (a free-form list mixing VIP/Repeat/Healthcare/Interior into one
unstructured field) were removed. Replaced with: **Priority** (Normal/High/VIP,
manually set — a genuine judgment call) and **Relationship** (New Lead / Existing
Client / Repeat Client — calculated live from actual project count, never
manually set, so it can't drift out of sync with reality).

### D-012 — Sector/Service Belong to the Project, Not the Client
**Status:** Implemented (v2.0.0 / v2.2.0)
"A client is who pays you. A project is what you design." A client's projects can
span multiple sectors (a developer client might have both Residential and
Commercial projects) — that information lives on each Project, not as a fixed
label on the Client.

### D-013 — Smart Country & Phone Engine
**Status:** Implemented (v0.7.0)
"Indian Client" checkbox (default checked) replaces an India/Foreign dropdown.
Foreign clients pick one Country from a dropdown that sets both Country Name and
Mobile country code together. Alternate Mobile has its own "Same Country Code as
Primary" checkbox, so it can independently use a different country's code (e.g. a
Dubai-based client with an India-based caretaker contact).

### D-014 — Single-User SQLite, Multi-User Deferred
**Status:** Implemented / Standing Decision
SQLite (embedded, zero-cost, zero-config) is the deliberate choice for the current
single-user scale. PostgreSQL + client-server architecture + user roles/permissions
+ audit-log immutability are explicitly **not** being implemented now — revisit
only once hiring staff and real concurrent multi-user access is actually imminent,
not preemptively. New schema additions should stay reasonably forward-compatible
(nullable fields, avoid hard assumptions) without building unused infrastructure.

### D-015 — Archive Fields Exist, Archive Workflow Doesn't (Yet)
**Status:** Partially implemented (v2.8.0)
Client/Project/Floor/Space all have an `Archived` column (default 0), unused by any
current UI or logic. Pure schema future-proofing so a future Archive workflow won't
require a database redesign — the actual archive/restore behavior is still
unbuilt and deferred as its own dedicated piece of work.

### D-016 — No Database File in Updates Once Real Data Exists
**Status:** Standing Decision (from v2.6.0 onward)
Once real client/project data exists in the database, no update ever includes a
full `ads_office_suite.db` replacement. Every schema change ships as a standalone,
additive migration script (`ALTER TABLE` / `CREATE TABLE IF NOT EXISTS`) that never
deletes or overwrites existing rows. `backup_database.py` should be run before every
update as an independent safety net.

### D-017 — CHANGELOG.md is Generated, Not Hand-Maintained
**Status:** Implemented
`version.py`'s `CHANGELOG` list is the single source of truth (it's what the app
itself reads for the in-app "About" panel). `generate_changelog.py` produces
`CHANGELOG.md` from it — never maintain the two separately, that creates drift.

### D-018 — Migration Registry
**Status:** Implemented
`sysMigrationHistory` table records every migration script that's actually been
applied to a specific database file. The "About ADS OS" panel compares this against
`version.EXPECTED_MIGRATIONS` and warns if anything is missing — directly solves
the "which copy of the database am I actually looking at" uncertainty that came up
repeatedly before this existed.

### D-019 — ttk.Style() Must Live Inside App.__init__, Never at Module Level
**Status:** Standing Decision (regressed twice — v3.9.2's fix was silently
reverted at least once before this note existed, then again in v4.2.0)
`ttk.Style().configure(...)` calls (currently the Treeview font fix) require a
live Tk root to attach to. Placing them at module level in `main.py` — even
right next to `ctk.set_appearance_mode("light")`, which *is* safe at module
level — crashes immediately with a TclError before any window exists, since
`ctk.set_appearance_mode` doesn't need a root but `ttk.Style()` does. This
belongs inside `App.__init__`, immediately after `super().__init__()`, and
nowhere else. Before any future full rewrite or large-scale edit of
`main.py`, explicitly check that this hasn't drifted back to module level.

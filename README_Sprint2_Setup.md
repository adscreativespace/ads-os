# ADS OS Desktop — Sprint 2 Setup Guide (Windows)
**Deliverable: Client & Project Manager (v0.2.0)**

## What's in this Sprint

| File | Purpose |
|---|---|
| `ads_office_suite.db` | Same database from Sprint 1 — untouched, nothing lost in the pivot from Excel |
| `db.py` | Data access layer — every SQL query in the app goes through here |
| `theme.py` | Brand colors (brass/ink/parchment) and fonts, shared by every screen |
| `client_screen.py` | Client list + Add/Edit/Delete forms |
| `project_screen.py` | Project list + Add/Edit/Delete forms (linked to Client + Project Type) |
| `main.py` | The actual application — run this one |
| `project_workspace.py` | The "Project Command Center" — double-click any project to open its dedicated workspace |
| `constants.py` | **New.** Indian states list, shared across screens |
| `requirements.txt` | Now two libraries: `customtkinter` and `tkcalendar` (for the date picker) |

## Latest changes

**Client form:**
- Country is now a India / Foreign toggle instead of free text. India auto-fills "India" and gives you a proper Indian States dropdown; Foreign gives you free-text Country + State entry.
- "Source" is now labeled "How did you come to know about us?" in the UI (the underlying database column is still called `Source` — no data disruption).
- Mandatory fields enforced on save: Client Name, Mobile, Email, Address, Country. Trying to save without these shows exactly what's missing.

**Project form:**
- Start Date is now a real dropdown calendar (click the field to pop open a date picker) instead of typing `YYYY-MM-DD` by hand.
- Expected Completion field removed per your instruction — if you actually want it back later, it's a one-line change since the database column is still there, just unused.
- Package section is now clearly labeled, and selecting a package shows its Rate and Minimum Fee right below the dropdown.
- "Same as Client's Residence" checkbox (added earlier) is confirmed in this version — auto-fills Site Address/City/State/Country from the selected client, uncheck to enter a custom site address.

**New dependency:** this version needs `tkcalendar` for the date picker. Run `pip install -r requirements.txt` again to pick it up — it'll install both libraries.

## Step 1: Check if Python is installed

Open Command Prompt (Windows key → type `cmd` → Enter) and run:
```
python --version
```
- If you see something like `Python 3.11.x` or `Python 3.12.x` → skip to Step 2.
- If you see an error ("not recognized") → install Python:
  1. Go to https://www.python.org/downloads/
  2. Download the latest Windows installer
  3. **Important:** on the first install screen, check the box **"Add python.exe to PATH"** before clicking Install
  4. Once installed, reopen Command Prompt and re-run `python --version` to confirm

## Step 2: Install the one required library

In Command Prompt, navigate to this folder and run:
```
cd path\to\this\folder
pip install -r requirements.txt
```
This installs `customtkinter` — everything else the app uses (`sqlite3`, `tkinter`) comes built into Python already, no extra installs needed.

## Step 3: Run it
```
python main.py
```
A window titled "ADS Office Suite" should open with a Dashboard, Clients, and Projects section in the sidebar.

## What to test
1. **Dashboard** — should show 0 clients, 0 projects, 0 active projects (clean database)
2. **Clients → + New Client** — add a real client, fill in name + mobile at minimum, Save
3. Client should appear in the list with an auto-generated code like `ADS-CL-0001`
4. **Projects → + New Project** — pick the client you just created, give it a name and project type, Save
5. Double-click any row in either list to edit it
6. Go back to Dashboard — the counts should now reflect what you added

## If it doesn't run
- **"No module named customtkinter"** → Step 2 didn't complete; re-run `pip install -r requirements.txt` in the same folder
- **Window opens but looks unstyled/tiny** → this is a known CustomTkinter first-run quirk on some Windows scaling settings; resize the window once and it should render correctly from then on
- **"database is locked"** → close any other program that might have `ads_office_suite.db` open (e.g., a SQLite browser tool), then retry

## What's deliberately NOT built yet (next sprints)
- No Floor/Room manager inside a project yet — Sprint 3
- No Quotation engine or PDF generation — Sprint 4 (this is where the ₹20/₹25/₹30/₹70/₹110 rate card and package logic actually gets applied)
- No Master Rate Card screen (currently only editable by hand in the `.db` file) — will build a Settings screen for this
- Fonts are Georgia/Segoe UI as stand-ins for Bodoni Moda/Work Sans — real brand fonts need font files bundled; tell me if this matters enough to prioritize before Sprint 3

## Latest changes (UI restructuring)

- **Dashboard is now "Mission Control"**: real stat cards (Total Clients, Active Projects, Today's Site Visits, Pending Milestones) plus a live Recent Activity feed pulled from the actual activity log. Revenue/Outstanding/Pending Quotations are intentionally *not* shown yet — faking zeros for numbers that don't exist until the Quotation Engine (Sprint 4) is built would be misleading.
- **"Clients" renamed to "CRM"** in the sidebar (display label only — nothing structural changed).
- **Project Workspace tabs regrouped**: Overview, Planning (Milestones + Floors & Rooms placeholder), Design (placeholder), Commercial (placeholder), Execution (Site Visits), Activity (new — a live log of everything that's happened on this specific project). This taxonomy is where Sprint 3/4 features will slot in without needing another reshuffle.

**Also new:** version number now shows in the sidebar (e.g. `v0.3.0`) — click it to see the full changelog. Every future update bumps `version.py`'s `APP_VERSION` and adds a changelog entry, so you can always tell exactly what build you're running.

**Not done in this pass** (flagged, not forgotten): a dual-pane Client screen (list + detail panel instead of popup forms), collapsible sections in the New Client form, and card-based Project display instead of a list. These are real improvements but deserve their own focused round rather than being bundled into an already-large change.

## Confirm before Sprint 3
Run through the app with a couple of real clients and projects, open a workspace, check the Dashboard reflects real activity. Tell me anything that feels wrong, missing, or awkward — then Sprint 3 (Floor/Room manager, feeding the "Planning" tab) is next.

## v0.4.0: Package Deliverable System + quick fixes

**Quick fixes:**
- Sidebar reverted to "Clients" (was briefly "CRM")
- Pin/Zip Code field added to Client form
- "How did you find us?" (renamed from "How did you come to know about us?")
- "Project Closed" milestone now shows a Yes/No dropdown instead of the 3-state status
- Site Visit date is now a calendar picker, matching Start Date

**Package Deliverable System (the big one):** implements the exact 5-tier structure from your rate card document — Building Planning → Essential → Essential Plus → Signature → Complete — with true inheritance:
- Each package only stores its *new or upgraded* deliverables, not a full copy
- A `SupersedesDeliverableID` link lets a package's deliverable explicitly replace an earlier tier's version (e.g. Essential Plus's "1 Photorealistic 3D Exterior Design" replaces Essential's "1 Photorealistic Exterior Design" instead of showing both)
- `migrate_packages.py` assembles the full deliverable list for any package by walking the inheritance chain — ran this and verified all 5 tiers assemble correctly with no duplicates
- Professional Services (Consultation/Site Visit/Site Supervision/Structural/Exterior) now have an Included/Optional/Not Included flag per package
- Revision Policy (Planning/Exterior/Interior revision counts) stored per package/category

**One assumption I made, worth confirming:** your document didn't give Building Planning or Essential Plus numeric rates directly. I mapped them from your earlier Master Rate Card — Building Planning = ₹20/sq.ft. (its "planning only" tier), Essential Plus = ₹30/sq.ft. (the "Planning + Furniture + Exterior" tier you hadn't named yet). If that mapping is wrong, tell me the correct rates and I'll fix them — it's a one-line change per package now, not a rewrite.

**What this enables next:** Sprint 4's Quotation Engine can now pull `migrate_packages.py`'s `get_assembled_package()` function directly to auto-populate every deliverable, revision rule, and included service for whatever package a room is assigned — exactly the "automatically generate all the required details" behavior you asked for. That's the next real step once Sprint 3 (Floors & Rooms) is built.

## v0.4.2: Logo added

Your logo now appears in two places:
- **Header bar**: a new light-colored strip above the sidebar shows the full logo. It's not in the dark sidebar because your logo is black line-art — placed directly on the near-black sidebar, it would be nearly invisible. The header bar solves that without needing an inverted/white version of the logo.
- **Window/taskbar icon**: just the house-mark portion (cropped from the full logo) is set as the app's icon, so it shows up properly in the Windows taskbar and title bar.

**New folder**: `assets/` containing `logo.png` and `logo_mark.png` — must be copied along with the other files, in the same folder as `main.py`.

**New dependency**: `Pillow` (image handling) — added to `requirements.txt`, run `pip install -r requirements.txt` again to pick it up.

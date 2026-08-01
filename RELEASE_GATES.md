# ADS OS — Release Gates

A severity framework for deciding whether a found issue blocks a release,
needs explicit sign-off, or can ship as-is. Applied by whoever finds the
issue — Claude, Claude Code, or Atish during real use.

A version number assigned by Claude means "proposed, and self-verified
wherever that's actually possible" — not "proven." Proof comes from Claude
Code running `REGRESSION_CHECKLIST.md` against real data, or from real use.
Until that happens, treat the release as a candidate, not a confirmed one.

---

## 🔴 P0 — Release Blocker
Crash, data corruption, wrong calculation, migration failure, or inability
to save. Release is prohibited until fixed — no exceptions, no "ship now,
fix later." Example: v4.4.4's BOQ crash (undefined `table_frame`).

## 🟠 P1 — Major Workflow Broken
A core workflow produces wrong output, even without crashing. Example: the
Proposal Package snapshot bug (v4.4.3) — no crash, but a reprinted proposal
could silently show the wrong package. Release only with explicit
acknowledgment of the issue, never silently.

## 🟡 P2 — Workflow Inconvenience
Missing search, awkward layout, wrong default selection, a field that's
technically usable but annoying. May release; log it (`KNOWN_ISSUES.md` or
`USER_FEEDBACK.md`) rather than let it disappear.

## 🔵 P3 — Enhancement
Would be nice. Can wait indefinitely. Not a defect in what exists today.

---

## What each level requires before shipping

| Gate | Requirement |
|------|-------------|
| P0   | Must be fixed. Full regression re-run after the fix. |
| P1   | Must be fixed, or explicitly accepted with the risk stated in the changelog. |
| P2   | Fine to ship; log it so it doesn't get silently lost. |
| P3   | No action needed now. |

## The pipeline this supports

```
Claude writes code
      |
Self-verification (syntax check + execute what's actually testable --
      SQL/business logic can be run directly; UI construction code can
      only be reviewed, not executed, in this sandbox -- see the BOQ
      table_frame regression for exactly why that gap matters)
      |
Version bump + delivery  <-- this is a CANDIDATE, not a confirmed release
      |
Claude Code: REGRESSION_CHECKLIST.md against real data
      |
Real project test (and a SECOND real project where practical --
      one project's data shape can hide bugs a second project reveals)
      |
Report back --> any P0/P1 found here gets fixed before anything new starts
```

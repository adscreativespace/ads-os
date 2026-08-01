# ADS OS — Backlog

Ideas, not commitments. Nothing here is scheduled or sequenced — that only
happens when one item gets picked, scoped narrowly, and actually built.
Only real ideas that have genuinely come up in conversation go here, never
invented ones added to look thorough.

An item leaves this list one of two ways: it gets scoped and built (moves
to `CHANGELOG.md`), or real use shows it isn't actually needed.

---

## Workflow Polish (raised repeatedly, never scoped narrowly enough to build)
- **Project Dashboard as command centre** — today's site visits, pending
  contractor payments, outstanding client payments, latest purchase/invoice,
  at a glance without opening six modules. Raised multiple times; the
  Commercial Dashboard already covers Commercial-specific numbers, this
  would be broader, at the Project Overview level.
- **Information Density** — several tables show contact/reference fields
  (Phone, Partner Type) where aggregated data (Outstanding, Last Purchase,
  Current Contract) might be more useful. Needs a specific screen picked,
  not applied everywhere at once.
- **Dialog & Form Standardization** — inconsistent sizing, some scroll and
  some don't, DateEntry adoption is now consistent (fixed in v4.4.4) but
  general dialog sizing/spacing isn't audited.
- **Typography pass** — header/subheader/body hierarchy is weak in places;
  no concrete plan yet, needs actual design direction, not just "more
  contrast."
- **Empty States beyond Commercial** — done for BOQ/Materials/Vendors/
  Invoice Center/Contracts (v4.4.4). Planning and Execution still show
  blank tables with no data.

## Mentioned, real workflow gap, not yet scoped
- **Weekly Labour** — explicitly PENDING in `BUSINESS_RULES.md`. Needs one
  real week's labour entry from Atish before any schema work starts; not
  speculative, just blocked on a real example.
- **Scope Templates per trade** — explicitly PENDING in `BUSINESS_RULES.md`,
  same reason.

## Mentioned once, genuinely speculative, needs a real trigger before scoping
- Execution Module (site diary, photos, issues, daily progress)
- Document/Drawing management with revisions
- Site photo tagging
- AI-assisted BOQ/Proposal drafting

These four are furthest from ready — no real workflow has been walked
through for any of them the way Contract Management's was before it got
built. Not dismissed, just not something to scope from a wish list; wait
for an actual "I needed to do X and couldn't" moment.

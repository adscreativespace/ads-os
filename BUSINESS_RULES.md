# ADS OS — Business Rules

Verified truths about how ADS Creative Space actually operates, independent
of any implementation. These survive a full rewrite; `DECISIONS.md` records
implementation choices, this records the business itself. A rule only
belongs here once confirmed with a real example — an unconfirmed rule is
marked **Pending** rather than guessed at.

---

### BR-001 — Contractors are a separate master from Vendors/Business Partners
**Superseded in v4.6.0.** This rule originally said the opposite: no
separate Contractor Master, everything under `mstVendor` distinguished by
`PartnerType`. That was correct reasoning for a database-normalization
question -- but this was reclassified as an explicit business decision by
the business owner ("I need Contractor fully separate. Must, No
Compromise"), not a technical one, and the business owner's call on their
own product takes precedence. Contractors now live in `mstContractor`, a
genuine first-class master built independently (not a thin wrapper reusing
Vendor logic), because in this business a masonry contractor and a
hardware supplier are operationally different entities with different
workflows (labour/scope/running-bills vs. materials/purchase/invoice), even
though some contact fields overlap. Existing Contractor-type Vendors
(PartnerType IN ('Contractor', 'Labour Agency')) were migrated into
mstContractor via migrate_v394_contractor_module.py -- the original Vendor
rows were left untouched, not deleted, so nothing was lost in the split.

### BR-002 — Quotations are copied into contracts, never referenced live
A Business Partner may have multiple quotation versions over time. When a
quotation is assigned to a project, the Project Contract copies it at that
moment. Revising the Business Partner's default quotation later must never
retroactively change any existing project's contract. Same pattern already
proven by Fee Calculation -> Proposal (mirrors D-017 in DECISIONS.md).

### BR-003 — Commission belongs to the Project Contract, never the Business Partner
Commission terms are negotiated per project, not a fixed property of the
partner. The same Business Partner can have different commission
arrangements on different projects.

### BR-004 — Contract payments are additive; status is always computed
A contract is never manually marked "Paid in Full." Every payment (advance,
partial, final) is logged as its own entry; the contract's paid amount is
the sum of those entries, and its status is derived from comparing that sum
to the Contract Amount. Same discipline already used for Invoice status.

### BR-005 — Fixed contracts have a Contract Amount; Running contracts do not
A Fixed contract has one total amount, paid down over time. A Running
contract (e.g. weekly labour, ongoing site work) has no single total -- only
a running log of payments against ongoing work. The two are structurally
different, not the same table used two different ways.

### BR-006 — Board is not a measurement unit
Confirmed formula: Area (Sq.ft) = Length x Width x Quantity. "Board
Calculation" is a *method* for deriving a Sq.ft quantity, not a unit itself
-- the stored measurement is always Sq.ft, and payment is always calculated
on that derived Sq.ft, never on board count directly.
**Status:** Implemented in v4.4.2. Formula confirmed and verified against a
real save() flow (8' x 4' x 15 boards = 480 Sq.ft, correctly stored with
Unit='Sq.ft', never 'Board').

---

## Pending Business Rules
Not yet confirmed with a real example. Do not design schema around these
until a real record is provided.

### PENDING — Weekly Labour
Needs one real week's actual labour entry (shifts, headcounts by skill
level, rates per shift or per worker, how Sundays are handled, whether the
same labourer can work both shifts) before any schema is designed.

### PENDING — Scope Templates per trade (False Ceiling, Flooring, Painting, etc.)
Needs real default item lists per trade as actually quoted, not an assumed
generic list.

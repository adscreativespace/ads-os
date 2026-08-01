"""
ADS OS Desktop -- Landed Cost Management (v4.9.7)

Core allocation logic for spreading a purchase invoice's additional
charges (Transportation, Loading, Handling, Packing, Insurance, Misc)
across the materials on that same invoice, so each material's true
landed cost -- not just its purchase rate -- is knowable.

Deliberately built as pure, database-light functions first, tested
against real allocation math before any dialog depends on them --
allocation math that's subtly wrong (e.g. off-by-one in a proportional
split, or a rounding remainder silently dropped) is worse than not
having the feature at all, since it would produce a landed cost that
LOOKS authoritative but is quietly incorrect.

Three allocation methods, matching real invoicing practice:
- "By Value": expensive materials absorb more of the shared charge
  (the default, and the most common in practice -- a ₹35,000 material
  and a ₹5,000 material on the same bill don't cause equal freight).
- "By Quantity": split proportional to unit count instead of value.
- "Manual": the person recording the purchase decides the split
  directly, when they know it doesn't fit a proportional pattern
  (e.g. transportation clearly belonged to one bulky item, not all of
  them).

Scope of this pass: the schema (trxPurchaseInvoice, trxPurchaseCharge),
this allocation module, and wiring Additional Charges into the existing
multi-item purchase dialog (materials_panel.py's NewPurchaseDialog).
Explicitly NOT built this round, staged as real future phases matching
the roadmap's own sequencing: BOQ variance warnings (Landed Cost vs BOQ
Rate), Material Cost History trend charts, Financial Dashboard
integration, and Site Expense Management (a separate, later milestone --
mixing it into this one would blur two genuinely different features).
"""
import db


def create_purchase_invoice(vendor_id, invoice_no, invoice_date, db_conn=db):
    """
    Real invoice header -- one row per vendor bill, the structural piece
    multi-material charge allocation needs.

    db_conn defaults to the db module itself (standalone, own commit --
    exactly the prior behavior). Pass a db.transaction() object instead
    to make this participate in a larger atomic operation, so it commits
    or rolls back together with the rest of that operation rather than
    on its own.
    """
    return db_conn.execute(
        "INSERT INTO trxPurchaseInvoice (VendorID, InvoiceNo, InvoiceDate) VALUES (?,?,?)",
        (vendor_id, invoice_no or None, invoice_date))


def add_purchase_charge(invoice_id, charge_type, amount, allocation_method="By Value", db_conn=db):
    """Records one additional charge line (Transportation, Loading, etc.) against a real invoice. See create_purchase_invoice for db_conn."""
    return db_conn.execute(
        "INSERT INTO trxPurchaseCharge (PurchaseInvoiceID, ChargeType, Amount, AllocationMethod) VALUES (?,?,?,?)",
        (invoice_id, charge_type, amount, allocation_method))


def allocate_charges(line_items, charges, manual_shares=None):
    """
    Real allocation math -- given this invoice's line items and its
    charges, returns {purchase_id: allocated_charge_amount} such that
    the allocated amounts sum EXACTLY to the total charges (no rounding
    remainder silently dropped).

    line_items: list of {"purchase_id": int, "amount": float, "quantity": float}
    charges: list of {"amount": float, "allocation_method": "By Value"|"By Quantity"|"Manual"}
    manual_shares: optional {purchase_id: fraction} for "Manual" charges,
        fractions must sum to 1.0 across the invoice's line items.

    Each charge is allocated independently by its OWN method (an invoice
    can mix a "By Value" transportation charge with a "Manual" packing
    charge), then summed per line item.
    """
    result = {item["purchase_id"]: 0.0 for item in line_items}
    total_value = sum(item["amount"] for item in line_items)
    total_qty = sum(item["quantity"] for item in line_items)

    for charge in charges:
        method = charge["allocation_method"]
        amount = charge["amount"]
        if method == "By Value":
            if total_value <= 0:
                continue
            for item in line_items:
                result[item["purchase_id"]] += amount * (item["amount"] / total_value)
        elif method == "By Quantity":
            if total_qty <= 0:
                continue
            for item in line_items:
                result[item["purchase_id"]] += amount * (item["quantity"] / total_qty)
        elif method == "Manual":
            shares = manual_shares or {}
            for item in line_items:
                result[item["purchase_id"]] += amount * shares.get(item["purchase_id"], 0.0)
    return result


def get_invoice_landed_costs(invoice_id):
    """
    Real, complete landed-cost breakdown for every line item on a given
    invoice -- purchase rate, allocated charges, and the resulting
    landed cost per unit. This is what a Purchase Entry confirmation or
    a Material's cost history would actually display.
    """
    line_items_raw = db.fetch_all(
        "SELECT PurchaseID, Quantity, TotalCost AS Amount FROM trxMaterialPurchase WHERE PurchaseInvoiceID=?",
        (invoice_id,))
    line_items = [{"purchase_id": r["PurchaseID"], "amount": r["Amount"], "quantity": r["Quantity"]}
                 for r in line_items_raw]
    charges_raw = db.fetch_all(
        "SELECT Amount, AllocationMethod FROM trxPurchaseCharge WHERE PurchaseInvoiceID=?", (invoice_id,))
    charges = [{"amount": r["Amount"], "allocation_method": r["AllocationMethod"]} for r in charges_raw]

    allocated = allocate_charges(line_items, charges)
    result = []
    for item in line_items:
        qty = item["quantity"]
        purchase_rate = item["amount"] / qty if qty else 0
        allocated_amount = allocated.get(item["purchase_id"], 0.0)
        landed_cost = (item["amount"] + allocated_amount) / qty if qty else 0
        result.append({
            "purchase_id": item["purchase_id"],
            "purchase_rate": purchase_rate,
            "allocated_charge": allocated_amount,
            "allocated_charge_per_unit": allocated_amount / qty if qty else 0,
            "landed_cost": landed_cost,
        })
    return result


def get_material_landed_cost(material_id):
    """
    Real, current landed cost for a material -- based on its MOST RECENT
    purchase. If that purchase has no invoice-level charges (either it
    predates this feature, or it was a standalone purchase with no
    additional charges), landed cost correctly equals the purchase rate,
    not a fabricated markup.
    """
    latest = db.fetch_one(
        "SELECT PurchaseID, PurchaseInvoiceID, TotalCost, Quantity FROM trxMaterialPurchase "
        "WHERE MaterialID=? ORDER BY PurchaseDate DESC, PurchaseID DESC LIMIT 1", (material_id,))
    if not latest:
        return None
    purchase_rate = latest["TotalCost"] / latest["Quantity"] if latest["Quantity"] else 0
    if not latest["PurchaseInvoiceID"]:
        return {"purchase_rate": purchase_rate, "landed_cost": purchase_rate, "has_charges": False}
    breakdown = get_invoice_landed_costs(latest["PurchaseInvoiceID"])
    match = next((b for b in breakdown if b["purchase_id"] == latest["PurchaseID"]), None)
    if not match:
        return {"purchase_rate": purchase_rate, "landed_cost": purchase_rate, "has_charges": False}
    return {"purchase_rate": match["purchase_rate"], "landed_cost": match["landed_cost"], "has_charges": True}

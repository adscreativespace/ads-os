"""
ADS OS Desktop -- Shared Financial Calculations
Single source of truth for every revenue/expense/outstanding/operations
number shown in both the Financial Dashboard and the Reports module.
Extracted specifically so a fix or refinement here applies everywhere it's
used, rather than two screens quietly drifting apart from duplicated logic.

Every function optionally accepts a (start_date, end_date) ISO-format date
range -- None means "all time," matching Financial Dashboard's existing
unfiltered behavior. Reports pass a real range from their filter controls.

Vendor Outstanding is now genuinely real -- trxVendorPayment (built for
the Vendors module) closed the exact gap that used to make this an
honest guess rather than a fact. Still governed by the same principle as
everything else here: only what's honestly computable from real data.
"""
import db
import datetime


def get_revenue_summary(start_date=None, end_date=None):
    contracts = db.fetch_all("SELECT ContractAmount FROM trxContract")
    total_contract_value = sum(c["ContractAmount"] for c in contracts if c["ContractAmount"] is not None)

    invoice_query = "SELECT InvoiceID, Amount FROM trxInvoice WHERE Status != 'Cancelled'"
    params = []
    if start_date:
        invoice_query += " AND InvoiceDate >= ?"
        params.append(start_date)
    if end_date:
        invoice_query += " AND InvoiceDate <= ?"
        params.append(end_date)
    invoices = db.fetch_all(invoice_query, tuple(params))
    total_invoiced = sum(i["Amount"] for i in invoices)
    total_received = sum(db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxInvoicePayment WHERE InvoiceID=?",
                                      (i["InvoiceID"],))["t"] for i in invoices)
    return {
        "total_contract_value": total_contract_value,
        "total_invoiced": total_invoiced,
        "total_received": total_received,
        "pending_receivables": total_invoiced - total_received,
    }


def get_expenses_summary(start_date=None, end_date=None):
    purchase_query = "SELECT COALESCE(SUM(TotalCost),0) AS t FROM trxMaterialPurchase WHERE 1=1"
    payment_query = "SELECT COALESCE(SUM(Amount),0) AS t FROM trxContractPayment WHERE 1=1"
    # Additional purchase charges (Transportation, Loading, etc.) are real
    # money spent, but live in a separate table (trxPurchaseCharge) added
    # for Landed Cost Management -- without this, they were invisible to
    # the Financial Dashboard entirely, silently understating real expenses.
    charges_query = "SELECT COALESCE(SUM(c.Amount),0) AS t FROM trxPurchaseCharge c " \
                    "JOIN trxPurchaseInvoice i ON c.PurchaseInvoiceID = i.PurchaseInvoiceID WHERE 1=1"
    # Site Expenses (labour wages, site transport, refreshments, tools,
    # security, misc.) are real, non-material site spend -- were entirely
    # invisible to Expenses/Net Position until this feature existed.
    site_expense_query = "SELECT COALESCE(SUM(Amount),0) AS t FROM trxSiteExpense WHERE 1=1"
    purchase_params, payment_params, charges_params, site_expense_params = [], [], [], []
    if start_date:
        purchase_query += " AND PurchaseDate >= ?"
        payment_query += " AND PaymentDate >= ?"
        charges_query += " AND i.InvoiceDate >= ?"
        site_expense_query += " AND ExpenseDate >= ?"
        purchase_params.append(start_date)
        payment_params.append(start_date)
        charges_params.append(start_date)
        site_expense_params.append(start_date)
    if end_date:
        purchase_query += " AND PurchaseDate <= ?"
        payment_query += " AND PaymentDate <= ?"
        charges_query += " AND i.InvoiceDate <= ?"
        site_expense_query += " AND ExpenseDate <= ?"
        purchase_params.append(end_date)
        payment_params.append(end_date)
        charges_params.append(end_date)
        site_expense_params.append(end_date)
    total_purchases = db.fetch_one(purchase_query, tuple(purchase_params))["t"]
    total_contractor_payments = db.fetch_one(payment_query, tuple(payment_params))["t"]
    total_additional_charges = db.fetch_one(charges_query, tuple(charges_params))["t"]
    total_site_expenses = db.fetch_one(site_expense_query, tuple(site_expense_params))["t"]
    return {"total_purchases": total_purchases, "total_contractor_payments": total_contractor_payments,
            "total_additional_charges": total_additional_charges, "total_site_expenses": total_site_expenses}


def get_cash_position(start_date=None, end_date=None):
    revenue = get_revenue_summary(start_date, end_date)
    expenses = get_expenses_summary(start_date, end_date)
    money_in = revenue["total_received"]
    money_out = (expenses["total_purchases"] + expenses["total_contractor_payments"]
                 + expenses["total_additional_charges"] + expenses["total_site_expenses"])
    return {"money_in": money_in, "money_out": money_out, "net_position": money_in - money_out}


def get_outstanding_summary():
    # Deliberately NOT date-filtered -- an outstanding balance is a current,
    # point-in-time fact, not something that makes sense to ask "as of a
    # past date" without a full historical ledger this app doesn't have.
    revenue = get_revenue_summary()
    contracts_full = db.fetch_all("SELECT ContractID, ContractAmount FROM trxContract WHERE ContractAmount IS NOT NULL")
    contractor_paid_total = sum(db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxContractPayment WHERE ContractID=?",
                                             (c["ContractID"],))["t"] for c in contracts_full)
    contractor_contract_total = sum(c["ContractAmount"] for c in contracts_full)

    # Real, now that trxVendorPayment exists -- same join pattern already
    # verified in vendors_panel.py's vendor_total_purchase(), aggregated
    # across every vendor instead of one at a time.
    total_vendor_purchases = db.fetch_one("SELECT COALESCE(SUM(TotalCost),0) AS t FROM trxMaterialPurchase")["t"]
    total_vendor_payments = db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxVendorPayment")["t"]

    return {
        "client_receivables_outstanding": revenue["pending_receivables"],
        "contractor_outstanding": contractor_contract_total - contractor_paid_total,
        "vendor_outstanding": total_vendor_purchases - total_vendor_payments,
    }


def get_operations_summary():
    active_projects = db.fetch_one("SELECT COUNT(*) AS n FROM tblProject WHERE ProjectStatus NOT IN ('Completed', 'Cancelled')")["n"]
    active_contractors = db.fetch_one("SELECT COUNT(*) AS n FROM mstContractor WHERE Active=1")["n"]
    active_vendors = db.fetch_one("SELECT COUNT(*) AS n FROM mstVendor WHERE Active=1")["n"]
    return {"active_projects": active_projects, "active_contractors": active_contractors, "active_vendors": active_vendors}


def get_overdue_invoices():
    today = datetime.date.today().isoformat()
    overdue = db.fetch_all("""
        SELECT i.*, p.ProjectName FROM trxInvoice i JOIN tblProject p ON i.ProjectID = p.ProjectID
        WHERE i.Status != 'Cancelled' AND i.DueDate IS NOT NULL AND i.DueDate < ?
    """, (today,))
    result = []
    for inv in overdue:
        paid = db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxInvoicePayment WHERE InvoiceID=?", (inv["InvoiceID"],))["t"]
        if paid < inv["Amount"]:
            days_overdue = (datetime.date.today() - datetime.date.fromisoformat(inv["DueDate"])).days
            result.append({"invoice": inv, "paid": paid, "outstanding": inv["Amount"] - paid, "days_overdue": days_overdue})
    return sorted(result, key=lambda x: -x["days_overdue"])


def get_vendors_with_payments_due():
    """Real vendors with a genuine positive outstanding balance -- for the Alerts section."""
    vendors = db.fetch_all("SELECT VendorID, VendorName FROM mstVendor WHERE Active=1")
    result = []
    for v in vendors:
        purchased = db.fetch_one("""
            SELECT COALESCE(SUM(p.TotalCost),0) AS t FROM trxMaterialPurchase p
            JOIN mstMaterial m ON p.MaterialID = m.MaterialID WHERE m.VendorID=?
        """, (v["VendorID"],))["t"]
        paid = db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxVendorPayment WHERE VendorID=?",
                           (v["VendorID"],))["t"]
        if purchased - paid > 0:
            result.append({"id": v["VendorID"], "name": v["VendorName"], "outstanding": purchased - paid})
    return sorted(result, key=lambda x: -x["outstanding"])


def get_contractors_with_payments_due():
    """Real contractors with a genuine positive outstanding balance -- for the Alerts section."""
    contractors = db.fetch_all("SELECT ContractorID, Name FROM mstContractor WHERE Active=1")
    result = []
    for c in contractors:
        contracts = db.fetch_all("SELECT ContractID, ContractAmount FROM trxContract WHERE ContractorID=?",
                                 (c["ContractorID"],))
        contract_total = sum(ct["ContractAmount"] for ct in contracts if ct["ContractAmount"] is not None)
        paid = sum(db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxContractPayment WHERE ContractID=?",
                                (ct["ContractID"],))["t"] for ct in contracts)
        if contract_total - paid > 0:
            result.append({"id": c["ContractorID"], "name": c["Name"], "outstanding": contract_total - paid})
    return sorted(result, key=lambda x: -x["outstanding"])


def get_top_outstanding_clients(limit=5):
    """Real clients ranked by pending receivables, for the Top Outstanding Clients table."""
    clients = db.fetch_all("SELECT ClientID, ClientName FROM tblClient")
    result = []
    for c in clients:
        invoices = db.fetch_all("""
            SELECT i.InvoiceID, i.Amount FROM trxInvoice i JOIN tblProject p ON i.ProjectID = p.ProjectID
            WHERE p.ClientID=? AND i.Status != 'Cancelled'
        """, (c["ClientID"],))
        invoiced = sum(i["Amount"] for i in invoices)
        received = sum(db.fetch_one("SELECT COALESCE(SUM(Amount),0) AS t FROM trxInvoicePayment WHERE InvoiceID=?",
                                    (i["InvoiceID"],))["t"] for i in invoices)
        if invoiced - received > 0:
            result.append({"id": c["ClientID"], "name": c["ClientName"], "outstanding": invoiced - received})
    result.sort(key=lambda x: -x["outstanding"])
    return result[:limit]


def get_top_vendor_payables(limit=5):
    """Real vendors ranked by outstanding payable, for the Top Vendor Payables table."""
    return get_vendors_with_payments_due()[:limit]


def get_top_contractor_payables(limit=5):
    """Real contractors ranked by outstanding payable, for the Top Contractor Payables table."""
    return get_contractors_with_payments_due()[:limit]


def get_financial_health():
    """
    Real, operational health indicator -- explicitly NOT an accounting
    rating. Formula: Receivables + Net Position - Outstanding Payables
    (Vendor + Contractor). All four inputs are already-real numbers from
    the functions above; only the THRESHOLDS below are a judgment call
    (there's no certified accounting standard for "operational health"),
    stated plainly as a heuristic rather than implied to be authoritative.
    """
    revenue = get_revenue_summary()
    cash = get_cash_position()
    outstanding = get_outstanding_summary()
    score = (revenue["pending_receivables"] + cash["net_position"]
             - outstanding["vendor_outstanding"] - outstanding["contractor_outstanding"])
    if score >= 0:
        status_color, label = "#2E8B57", "Healthy"
    elif score >= -outstanding["vendor_outstanding"] - outstanding["contractor_outstanding"]:
        # Negative, but net position alone could still cover payables --
        # a real middle ground between comfortably fine and genuinely tight.
        status_color, label = "#B68100", "Attention"
    else:
        status_color, label = "#8B2E2E", "Critical"
    return {"status_color": status_color, "label": label, "score": score}


def get_recent_financial_activity(limit=10):
    """
    Real, merged, chronologically-sorted list of the most recent actual
    payments/receipts across all three real payment tables (client
    invoice payments, vendor payments, contractor payments) -- not a
    fabricated activity feed, genuinely the latest real transactions.
    """
    activity = []
    for row in db.fetch_all("""
        SELECT ip.PaymentDate, ip.Amount, p.ProjectName FROM trxInvoicePayment ip
        JOIN trxInvoice i ON ip.InvoiceID = i.InvoiceID JOIN tblProject p ON i.ProjectID = p.ProjectID
    """):
        activity.append({"date": row["PaymentDate"], "type": "Client Receipt", "detail": row["ProjectName"],
                         "amount": row["Amount"]})
    for row in db.fetch_all("SELECT vp.PaymentDate, vp.Amount, v.VendorName FROM trxVendorPayment vp "
                            "JOIN mstVendor v ON vp.VendorID = v.VendorID"):
        activity.append({"date": row["PaymentDate"], "type": "Vendor Payment", "detail": row["VendorName"],
                         "amount": row["Amount"]})
    for row in db.fetch_all("""
        SELECT cp.PaymentDate, cp.Amount, c.Name FROM trxContractPayment cp
        JOIN trxContract ct ON cp.ContractID = ct.ContractID JOIN mstContractor c ON ct.ContractorID = c.ContractorID
    """):
        activity.append({"date": row["PaymentDate"], "type": "Contractor Payment", "detail": row["Name"],
                         "amount": row["Amount"]})
    activity.sort(key=lambda x: x["date"], reverse=True)
    return activity[:limit]

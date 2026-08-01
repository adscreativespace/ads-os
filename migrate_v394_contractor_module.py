"""
Standalone migration for Contractor Module Phase 1 -- a deliberate business
decision, not a database-normalization one (explicit instruction: "I need
Contractor fully separate. Must, No Compromise"). Contractors become a
genuine first-class master entity, separate from Vendors, matching how
ADS Creative Space actually thinks about them.

Creates:
  - mstContractor: the new master table (Name/Trade/Contact/Banking/
    Commission/Status -- contractor-specific fields, not a Vendor subtype).
  - mstContractorScope: links to the EXISTING mstScopeOfWork master (Scope
    of Work is a genuinely shared concept -- Civil Works/Flooring/False
    Ceiling mean the same thing regardless of which master owns them --
    so reusing that table is not the same kind of compromise as sharing
    the Vendor/Contractor identity table itself).
  - trxContract.ContractorID: new nullable column. Contracts now belong to
    Contractors going forward, not Vendors -- but VendorID is kept (not
    dropped) so existing/historical contracts and any Vendor-side (non-
    contractor) commercial history remain fully intact and queryable.

Data migration (careful, tested against the real production scenario):
  For every real Vendor with PartnerType IN ('Contractor', 'Labour Agency')
  -- the two PartnerType values that genuinely mean "contractor" today,
  confirmed against real data (Goutam Roy is PartnerType='Contractor') --
  a corresponding mstContractor record is created, their Scope of Work is
  copied to mstContractorScope, and every trxContract row that referenced
  their VendorID gets ContractorID set to point to the new record.

Nothing is deleted. The original mstVendor rows and their trxVendorScope
entries are left completely untouched -- this migration only ADDS the
Contractor-side records and links; it does not touch or remove the Vendor
side, so there is no possible data loss even if this migration needs to be
reconsidered later.

Safe to run against a database with real data.

Usage: python migrate_v394_contractor_module.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_office_suite.db")
CONTRACTOR_PARTNER_TYPES = ("Contractor", "Labour Agency")

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON")
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS mstContractor (
    ContractorID          INTEGER PRIMARY KEY AUTOINCREMENT,
    ContractorCode         TEXT UNIQUE,
    Name                    TEXT NOT NULL,
    BusinessName            TEXT,
    Trade                   TEXT,
    Mobile                  TEXT,
    AltMobile               TEXT,
    Email                   TEXT,
    GSTNo                   TEXT,
    PANNo                   TEXT,
    AadhaarNo               TEXT,
    Address                 TEXT,
    BankAccountName         TEXT,
    BankAccountNumber       TEXT,
    BankIFSC                TEXT,
    BankName                TEXT,
    UPIID                   TEXT,
    DefaultCommissionPercent REAL,
    IsPreferred             INTEGER NOT NULL DEFAULT 0,
    Status                  TEXT NOT NULL DEFAULT 'Active',
    Active                  INTEGER NOT NULL DEFAULT 1,
    Rating                  REAL,
    Notes                   TEXT,
    CreatedOn               TEXT NOT NULL DEFAULT (datetime('now')),
    ModifiedOn               TEXT NOT NULL DEFAULT (datetime('now'))
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS mstContractorScope (
    ContractorID  INTEGER NOT NULL REFERENCES mstContractor(ContractorID) ON DELETE CASCADE,
    ScopeID        INTEGER NOT NULL REFERENCES mstScopeOfWork(ScopeID) ON DELETE CASCADE,
    PRIMARY KEY (ContractorID, ScopeID)
)""")
conn.commit()

cur.execute("PRAGMA table_info(trxContract)")
existing_cols = [r[1] for r in cur.fetchall()]
vendor_col_info = next(r for r in cur.execute("PRAGMA table_info(trxContract)").fetchall() if r[1] == "VendorID")
vendor_is_not_null = vendor_col_info[3] == 1  # column index 3 is the "notnull" flag

if "ContractorID" not in existing_cols or vendor_is_not_null:
    # SQLite can't ALTER COLUMN to drop a NOT NULL constraint directly --
    # VendorID was NOT NULL from before Contractors existed, back when every
    # contract required a Vendor. Now that a contract can belong entirely to
    # a Contractor with no Vendor involved at all, that constraint has to go.
    # Standard SQLite pattern: rebuild the table with the corrected schema,
    # copy all real data across by explicit column list (never SELECT *,
    # to guarantee column order/count match regardless of how the old
    # table's columns happen to be ordered), then swap the table in.
    # ContractID values are preserved exactly, so every other table that
    # references ContractID (trxContractItem, trxContractPayment,
    # trxCommissionReceipt, trxContractScope) keeps working correctly.
    print("Rebuilding trxContract to make VendorID nullable (Contracts can now be Contractor-only)...")
    cur.execute("PRAGMA foreign_keys=OFF")
    cur.execute("""CREATE TABLE trxContract_new (
        ContractID          INTEGER PRIMARY KEY AUTOINCREMENT,
        ProjectID           INTEGER NOT NULL REFERENCES tblProject(ProjectID) ON DELETE CASCADE,
        VendorID            INTEGER REFERENCES mstVendor(VendorID),
        ContractorID        INTEGER REFERENCES mstContractor(ContractorID),
        SourceQuotationID   INTEGER REFERENCES mstPartnerQuotation(QuotationID),
        ContractType        TEXT NOT NULL DEFAULT 'Fixed',
        ContractAmount      REAL,
        Status              TEXT NOT NULL DEFAULT 'Active',
        CommissionType      TEXT,
        CommissionValue     REAL,
        Notes               TEXT,
        CreatedOn           TEXT NOT NULL DEFAULT (datetime('now')),
        ModifiedOn          TEXT NOT NULL DEFAULT (datetime('now'))
    )""")
    contractor_id_select = "ContractorID" if "ContractorID" in existing_cols else "NULL"
    cur.execute(f"""INSERT INTO trxContract_new
        (ContractID, ProjectID, VendorID, ContractorID, SourceQuotationID, ContractType, ContractAmount,
         Status, CommissionType, CommissionValue, Notes, CreatedOn, ModifiedOn)
        SELECT ContractID, ProjectID, VendorID, {contractor_id_select}, SourceQuotationID, ContractType,
               ContractAmount, Status, CommissionType, CommissionValue, Notes, CreatedOn, ModifiedOn
        FROM trxContract""")
    row_count = cur.execute("SELECT COUNT(*) FROM trxContract_new").fetchone()[0]
    original_count = cur.execute("SELECT COUNT(*) FROM trxContract").fetchone()[0]
    if row_count != original_count:
        conn.rollback()
        raise RuntimeError(f"Row count mismatch during trxContract rebuild ({row_count} vs {original_count}) "
                          f"-- aborted, no changes made, original table untouched.")
    cur.execute("DROP TABLE trxContract")
    cur.execute("ALTER TABLE trxContract_new RENAME TO trxContract")
    cur.execute("PRAGMA foreign_keys=ON")
    print(f"Rebuilt trxContract: {row_count} real row(s) preserved exactly, VendorID is now nullable, "
          f"ContractorID column present.")
else:
    print("trxContract already has a nullable VendorID and a ContractorID column -- nothing to do.")
conn.commit()

# ---------------- Data migration ----------------
placeholders = ",".join("?" * len(CONTRACTOR_PARTNER_TYPES))
cur.execute(f"SELECT * FROM mstVendor WHERE PartnerType IN ({placeholders})", CONTRACTOR_PARTNER_TYPES)
contractor_vendors = cur.fetchall()
col_names = [d[0] for d in cur.description]

migrated = []
for row in contractor_vendors:
    v = dict(zip(col_names, row))
    # Skip if this vendor was already migrated in a previous run of this
    # script. Checks Notes, which is set once and never overwritten --
    # ContractorCode is NOT safe to check here, since it starts as a
    # temporary marker but gets immediately overwritten with the real
    # CON-#### code right after insertion, so a second run would never
    # find a match and would create a duplicate.
    migration_marker = f"Migrated from Vendor {v['VendorCode'] or v['VendorID']} "
    cur.execute("SELECT ContractorID FROM mstContractor WHERE Notes LIKE ?", (migration_marker + "%",))
    already_migrated = cur.fetchone()
    if already_migrated:
        # Still re-point any NEW contracts created against this vendor
        # since the last run (a real, if unlikely, scenario if someone
        # created a contract before re-running this migration).
        cur.execute("UPDATE trxContract SET ContractorID=? WHERE VendorID=? AND ContractorID IS NULL",
                   (already_migrated[0], v["VendorID"]))
        continue

    cur.execute("""INSERT INTO mstContractor (ContractorCode, Name, Trade, Mobile, Email, GSTNo, PANNo,
                   AadhaarNo, Address, BankAccountName, BankAccountNumber, BankIFSC, BankName, IsPreferred,
                   Status, Active, Rating, Notes, CreatedOn, ModifiedOn)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
               (f"PENDING-{v['VendorID']}", v["VendorName"], v["Category"], v["Phone"], v["Email"],
                v["GSTNo"], v["PANNo"], v["AadhaarNo"], v["Address"], v["BankAccountName"],
                v["BankAccountNumber"], v["BankIFSC"], v["BankName"], v["IsPreferred"], v["Status"],
                v["Active"], v["Rating"], f"{migration_marker}on Contractor Module Phase 1.",
                v["CreatedOn"], v["ModifiedOn"]))
    contractor_id = cur.lastrowid
    real_code = f"CON-{contractor_id:04d}"
    cur.execute("UPDATE mstContractor SET ContractorCode=? WHERE ContractorID=?", (real_code, contractor_id))

    # Migrate Scope of Work
    cur.execute("SELECT ScopeID FROM trxVendorScope WHERE VendorID=?", (v["VendorID"],))
    for (scope_id,) in cur.fetchall():
        cur.execute("INSERT OR IGNORE INTO mstContractorScope (ContractorID, ScopeID) VALUES (?,?)",
                   (contractor_id, scope_id))

    # Re-point their real contracts
    cur.execute("UPDATE trxContract SET ContractorID=? WHERE VendorID=?", (contractor_id, v["VendorID"]))
    contracts_repointed = cur.rowcount

    migrated.append((v["VendorName"], v["PartnerType"], real_code, contracts_repointed))

conn.commit()

cur.execute("""CREATE TABLE IF NOT EXISTS sysMigrationHistory (
    MigrationID INTEGER PRIMARY KEY AUTOINCREMENT,
    MigrationName TEXT UNIQUE NOT NULL,
    AppliedOn TEXT NOT NULL DEFAULT (datetime('now')),
    AppVersion TEXT
)""")
cur.execute("INSERT OR IGNORE INTO sysMigrationHistory (MigrationName) VALUES (?)", ("migrate_v394_contractor_module",))
conn.commit()
conn.close()

print(f"\nMigrated {len(migrated)} vendor(s) with PartnerType in {CONTRACTOR_PARTNER_TYPES} into mstContractor:")
for name, ptype, code, n_contracts in migrated:
    print(f"  {name} ({ptype}) -> {code}, {n_contracts} real contract(s) re-pointed to ContractorID")
print("\nOriginal mstVendor rows and their trxVendorScope entries were left completely untouched -- "
      "this only ADDED Contractor-side records, nothing was deleted or modified on the Vendor side.")

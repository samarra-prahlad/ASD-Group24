import os
import sqlite3
from pathlib import Path

from mcp_instance import mcp

BASE_DIR = Path(__file__).resolve().parent.parent  # mcp-server/
REPO_ROOT = BASE_DIR.parent

DEFAULT_DB_PATH = REPO_ROOT / "4-samarra-billing" / "database" / "data" / "billing.db"
DATABASE_PATH = Path(os.environ.get("BILLING_DB_PATH", str(DEFAULT_DB_PATH)))


def get_invoice_status(invoice_id: int) -> dict:
    """Look up an invoice's payment status and amounts by invoice_id."""
    if not DATABASE_PATH.exists():
        return {"error": "Billing database not found", "path": str(DATABASE_PATH)}

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT
                invoices.id,
                invoices.patient_id,
                invoices.status,
                invoices.total_amount,
                invoices.insurance_covered_amount,
                invoices.patient_owed_amount,
                invoices.date,
                insurance_providers.name AS insurance_provider_name
            FROM invoices
            LEFT JOIN insurance_providers
                ON invoices.insurance_provider_id = insurance_providers.id
            WHERE invoices.id = ?
            """,
            (invoice_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return {"error": "Invoice not found", "invoice_id": invoice_id}

    return {
        "invoice_id": row["id"],
        "patient_id": row["patient_id"],
        "status": row["status"],
        "total_amount": row["total_amount"],
        "insurance_covered_amount": row["insurance_covered_amount"],
        "patient_owed_amount": row["patient_owed_amount"],
        "date": row["date"],
        "insurance_provider_name": row["insurance_provider_name"],
    }


mcp.tool(name="billing_get_invoice_status")(get_invoice_status)
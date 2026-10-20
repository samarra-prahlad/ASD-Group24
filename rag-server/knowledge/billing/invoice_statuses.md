# Invoice Statuses

Every invoice in the billing system has one of three statuses: pending, partially_paid, or paid.

## Pending
A pending invoice has not yet received any payment from the patient. The full patient_owed_amount is still outstanding. Pending invoices are created automatically whenever a new invoice is generated for a patient, unless a different status is explicitly set.

## Partially Paid
A partially_paid invoice means the patient has made a payment towards their owed amount, but the full patient_owed_amount has not yet been settled. Staff should check the payment history alongside the invoice record to determine the remaining balance.

## Paid
A paid invoice means the patient has settled their full patient_owed_amount. No further payment is required for that invoice. Paid invoices remain in the system for record-keeping and can still be viewed via the invoice lookup tools.

## Checking Invoice Status
Invoice status can be checked using the billing_get_invoice_status MCP tool, which returns the invoice's status, total_amount, insurance_covered_amount, patient_owed_amount, date, and insurance provider name for a given invoice_id.
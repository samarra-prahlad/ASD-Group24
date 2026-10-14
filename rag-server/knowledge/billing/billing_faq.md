# Billing FAQ

## What do I do if my invoice is marked pending?
A pending invoice means no payment has been received yet. Contact billing to arrange payment for the full patient_owed_amount shown on the invoice.

## Why is my patient_owed_amount higher than expected?
Check whether an insurance provider is linked to the invoice. Invoices without a linked insurance_provider_id have no coverage applied, so the patient is responsible for the entire total_amount.

## Can an invoice have bed charges without an appointment cost?
Yes. Invoices for ward or bed stays may have bed_charges as the primary cost, with lower or zero appointment_cost and medication_cost, depending on the treatment received.

## How do I look up the status of a specific invoice?
Use the billing_get_invoice_status MCP tool with the invoice_id to retrieve its current status, amounts, and insurance provider.

## What does partially_paid mean for a patient's outstanding balance?
It means some but not all of the patient_owed_amount has been paid. The invoice remains open until the full amount is settled and the status is updated to paid.
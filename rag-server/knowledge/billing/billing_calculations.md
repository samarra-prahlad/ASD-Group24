# How Invoice Amounts Are Calculated

Every invoice tracks three cost components: appointment_cost, medication_cost, and bed_charges. These combine into a total, which is then split between insurance and the patient.

## Total Amount
total_amount = appointment_cost + medication_cost + bed_charges, rounded to 2 decimal places.

## Insurance Covered Amount
insurance_covered_amount = total_amount multiplied by the patient's insurance coverage_percentage (as a fraction), rounded to 2 decimal places. If the patient has no insurance provider linked to the invoice, this amount is 0.

## Patient Owed Amount
patient_owed_amount = total_amount minus insurance_covered_amount, rounded to 2 decimal places. This is the amount the patient is responsible for paying directly.

## Example
An invoice with appointment_cost of 150.00, medication_cost of 45.00, and bed_charges of 0.00 has a total_amount of 195.00. If the patient's insurance plan covers 60%, insurance_covered_amount is 117.00, and patient_owed_amount is 78.00.

These calculations are performed server-side whenever an invoice is created or updated, so the three amounts always stay consistent with each other.
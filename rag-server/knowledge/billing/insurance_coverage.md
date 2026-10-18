# Insurance Coverage

Each invoice can optionally be linked to an insurance provider. If no insurance_provider_id is set on an invoice, the patient is responsible for the full total_amount.

## Supported Insurance Providers
The billing system recognises the following insurance providers and plan types, each with a fixed coverage_percentage:

- Medibank Basic: 60% coverage
- Medibank Premium: 85% coverage
- Bupa Basic: 65% coverage
- Bupa Premium: 90% coverage
- HCF Standard: 70% coverage
- NIB Basic: 60% coverage
- NIB Premium: 80% coverage
- Australian Unity Standard: 70% coverage
- AHM Basic: 55% coverage
- Medicare Public: 100% coverage

## How Coverage Is Applied
The coverage_percentage for a patient's insurance plan determines how much of the invoice total is paid by insurance versus the patient. A higher coverage_percentage means the insurance provider pays a larger share of the total_amount, and the patient owes less out of pocket.

## No Insurance
If an invoice has no insurance_provider_id, insurance_covered_amount is 0, and patient_owed_amount equals the full total_amount.
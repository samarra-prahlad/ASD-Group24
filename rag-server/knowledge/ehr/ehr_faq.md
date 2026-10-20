# EHR Frequently Asked Questions

## Why can't I see another patient's medical record?
Patients can only view medical records and change requests tied to their own patient_id. If you need information about a different patient, an admin account is required.

## How do I report a missing or wrong allergy on my record?
Submit a change request with request_type set to Update Allergies and describe the correction in request_details, for example adding a newly diagnosed allergy or removing an outdated one.

## How do I check the status of a change request I submitted?
Look up the change request by its id; the status field will show pending if it has not been reviewed yet, approved if the correction was accepted, or rejected if it was not.

## Why is my change request still pending?
A change request stays pending until an admin reviews the request_details and updates its status. There is no automatic approval.

## Can I get a summary of my medical history instead of reading every record?
Yes, the EHR service can generate a plain-language summary of a patient's medical_records using an AI model, covering diagnosis, treatment, and notes across visits.
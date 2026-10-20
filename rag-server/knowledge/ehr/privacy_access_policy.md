# Medical Record Access and Privacy Policy

## Who can view a patient's medical records?
A patient with role patient can only view records where the record's patient_id matches their own caller_id. A user with role admin can view medical records for any patient_id.

## Who can view a patient's change requests?
The same rule applies to change requests as to medical records: a patient can only view or list change requests tied to their own patient_id, while an admin can view change requests for any patient.

## Who can create or edit a medical record?
Creating, updating, or deleting entries in medical_records is an admin action, since medical_records holds clinical data such as diagnosis and treatment that only clinical staff should be able to write.

## What identifies a user when calling the EHR service?
The EHR service has no local login of its own. Identity arrives as a token issued by the shared session system, verified via a session check that returns the caller's patient_id (as caller_id) and their role, either patient or admin.

## What counts as sensitive data in a medical record?
A medical record's diagnosis, treatment, notes, and allergies fields are all treated as sensitive clinical data and are subject to the same patient/admin access rule as the rest of the record; none of these fields are exposed without a valid session token.
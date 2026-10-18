# EHR Data Dictionary

## medical_records fields
patient_id identifies which patient the record belongs to. visit_date is the date of the appointment. diagnosis is the clinical diagnosis given. doctor_name is the treating doctor. treatment describes the prescribed medication or procedure. notes holds free-text clinical observations. allergies lists known allergies and their severity.

## change_requests fields
patient_id identifies which patient the request is about. request_type categorizes the change, one of Update Allergies, Update Treatment, Update Diagnosis, Update Notes, or Other. request_details is a free-text description of the requested correction. status tracks review progress as pending, approved, or rejected.

## What does the allergies field look like?
The allergies field is free text, typically naming the allergen followed by a reaction and severity in parentheses, for example "Penicillin (rash, moderate)" or "Peanuts (anaphylaxis, severe)". A value of "None reported" means no known allergies.

## What roles exist in the EHR system?
There are two roles: patient, who can only access their own patient_id's data, and admin, who can access and modify data for any patient.

## What is caller_id?
caller_id is the patient_id extracted from the caller's session token after verification. It is compared against the patient_id on a record or change request to enforce that patients only see their own data.
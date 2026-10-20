# Change Request Policy

## What is a change request?
A change request is a patient or staff-submitted request to correct or update information in a medical record. Each request has a request_type, request_details describing the change, and a status of pending, approved, or rejected.

## What request types are supported?
Supported request_type values are Update Allergies, Update Treatment, Update Diagnosis, Update Notes, and Other. Choose the type that most closely matches what needs to change; use Other only when no specific category fits.

## How is a change request's status determined?
Every change request starts with status pending. An admin reviews the request_details and changes the status to approved if the correction is verified, or rejected if it is not valid or cannot be confirmed.

## Who can submit a change request?
Patients can submit change requests for their own patient_id only. Admins can submit or review change requests for any patient. A patient cannot submit or view a change request belonging to a different patient_id.

## Can a change request be edited after submission?
Yes, a change request can be updated while it is still pending, for example to correct the request_details or request_type. Once a request has moved to approved or rejected, further correction should be filed as a new change request rather than editing the old one.
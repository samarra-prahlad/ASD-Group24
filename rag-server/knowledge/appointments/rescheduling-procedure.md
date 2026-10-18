# Rescheduling Procedure

## Requesting a change

A patient can request to move an existing appointment to a new date and time
by submitting a change request. The request includes the appointment being
changed and the newly requested date and time.

Only one change request can be pending per appointment at a time — if a
patient already has a pending request for that appointment, a new one
cannot be submitted until the existing one is reviewed.

## What happens after a request is submitted

The appointment itself is not changed immediately. Instead, the request sits
in a pending state, visible on the appointment as "Change requested" with the
new date and time shown, until an administrator reviews it.

## Admin review

An administrator reviews pending change requests and either approves or
rejects each one.

- **If approved:** the system checks whether the newly requested slot is
  still free. If it is, the appointment is updated to the new date and time.
  If someone else has since booked that slot, the change is rejected instead
  and the patient keeps their original appointment time.
- **If rejected:** the appointment stays at its original date and time, and
  the patient is notified the request was not approved.

Each change request can only be reviewed once — once it's been approved or
rejected, it can't be reviewed again.

# Clinic Hours & Closures

## Current system behavior

There is no separate concept of "clinic-wide" opening hours in this system.
Availability is set individually per doctor — each doctor has their own
weekly availability window (for example, "Mon-Fri 09:00-17:00" or
"Tue,Thu 10:00-16:00"). Appointments can only be booked within a doctor's
own stated hours, on the days they work.

To find out when the clinic is effectively "open," check the combined
availability windows of the doctors in a given specialty, rather than
looking for a single clinic-wide schedule.

## Public holidays and closures

The system does not currently account for public holidays or one-off
closures. If a doctor is normally available on a given day but is actually
unavailable due to a holiday or unplanned closure, this isn't reflected in
the booking system — a patient could still see and book a slot that won't
actually happen.

## Note for the team

If clinic-wide hours or holiday closures should exist, that's a feature
that would need to be built (e.g. a closures table checked during
availability lookups), not just documented. This file reflects current
behavior only.

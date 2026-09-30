# Booking Policy

## Appointment slot length

All appointments are booked in fixed 30-minute slots. A doctor's available hours
are divided into consecutive 30-minute blocks, and each block can only be
booked by one patient at a time.

## Patient ID requirement

Every booking requires a valid patient ID. Before an appointment can be created,
the system checks that the patient ID exists in the shared patient records. If
the ID isn't recognised, the booking is rejected and the patient is asked to
double-check the ID they entered.

## How booking works

1. The patient selects a specialty (e.g. Cardiology, Dermatology) and a date.
2. The system shows every doctor in that specialty who works on that day,
   along with their open 30-minute slots for that date.
3. Already-booked slots are automatically hidden — a doctor's booked
   appointments are excluded from what's shown as available.
4. The patient picks an open slot and enters their patient ID to confirm.
5. If someone else books that exact slot in the moment between viewing and
   confirming, the booking is rejected and the patient is asked to pick
   another time.

## Doctor availability

Each doctor has a fixed weekly availability window (e.g. "Mon-Fri 09:00-17:00").
Appointments can only be booked within a doctor's stated availability window,
on the days they work.

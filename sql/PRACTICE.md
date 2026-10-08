# SQL practice

Run queries with:

```
python scripts/sql.py "SELECT * FROM bookings LIMIT 5"
```

or start the interactive shell with `python scripts/sql.py` and end each query with `;`.

Reset the data any time with `python -m app.seed`. The seed is fixed, so the answers below always give the same rows right after a reset.

**Rules:** write each query by hand first. Say the logic out loud before typing: *one row per what, filtered how, counted or summed how, condition on each row or on the total.* Only then check `spoilers/SQL_ANSWERS.md`.

## Tables

```
users            (id, username, password, role, full_name, email)
airports         (code, name, city, country)
bookings         (id, awb_number, customer_id, origin, destination, pieces, weight_kg,
                  length_cm, width_cm, height_cm, volumetric_kg, chargeable_kg,
                  commodity, special_handling, flight_date, status, created_at, updated_at)
tracking_events  (id, booking_id, milestone, location, event_time, remarks)
documents        (id, booking_id, filename, content_type, size_bytes, stored_path, uploaded_at)
```

`bookings.customer_id` points to `users.id`. `tracking_events.booking_id` points to `bookings.id`.

## Level 1: the basics every interview asks

1. Find AWB numbers that appear more than once. *(Expected: 1 row)*
2. Find bookings whose customer does not exist in `users`. *(Expected: 1 row)*
3. Find bookings with no commodity. *(Expected: 1 row)*
4. Count bookings per status in a **single row** with columns booked, in_transit, delivered, cancelled.
5. Number of bookings created per day for the last 7 days.

## Level 2: the integration checks a cargo QA actually runs

6. Bookings with status `DLV` but no `DLV` tracking event. *(Expected: 3 rows. Explain why a JOIN with `<>` gives the wrong answer here.)*
7. Bookings that have no `BKD` tracking event at all. Look at the `special_handling` column of the result. What pattern do you see? *(This points at a real bug in the app.)*
8. Bookings where `status` does not match the latest tracking event. *(Expected: 4 rows right after reset)*
9. Bookings where the chargeable weight is wrong. Spec: chargeable = higher of actual and volumetric, rounded **up** to the next 0.5 kg. *(0 rows after reset. Create a few bookings in the app with odd dimensions, then run it again.)*
10. Airports with no outbound bookings. Use LEFT JOIN with IS NULL. *(Expected: 3 rows)*

## Level 3: what makes you stand out

11. Latest tracking event per booking, using `ROW_NUMBER()`.
12. Top 2 heaviest bookings (chargeable kg) **per customer**, keeping ties. Use `DENSE_RANK()`.
13. Total chargeable kg per customer, including customers with zero bookings, highest first. Exclude cancelled bookings.
14. Total chargeable kg per origin, only origins above 3,000 kg, excluding cancelled bookings. *(Expected: 3 rows)*
15. Delete the duplicate AWB rows but keep the oldest one. Run it as a `SELECT` first to see exactly what would be deleted. Then reset the database.

## Bonus: talk through these out loud, no typing

* Why does the `bookings` table allow duplicate AWB numbers? What would you recommend?
* `COUNT(*)` versus `COUNT(commodity)` on this table. Which numbers differ and why?
* Why does `NOT IN` become dangerous if the subquery can return NULL?
* After creating a booking in the UI, which three queries would you run to prove it was saved correctly?

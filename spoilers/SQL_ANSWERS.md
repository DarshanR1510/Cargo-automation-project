# SQL answers (spoilers)

Try every question in `sql/PRACTICE.md` yourself first. Reading these before writing your own query teaches you nothing.

Results below are right after `python -m app.seed`. SQLite syntax; differences from PostgreSQL and SQL Server are noted.

---

**1. Duplicate AWBs**
```sql
SELECT awb_number, COUNT(*) AS copies
FROM bookings
GROUP BY awb_number
HAVING COUNT(*) > 1;
```
Result: `607-10000082`, 2 copies. Condition on the group total, so HAVING, not WHERE.

**2. Orphan bookings**
```sql
SELECT b.id, b.awb_number, b.customer_id
FROM bookings b
LEFT JOIN users u ON u.id = b.customer_id
WHERE u.id IS NULL;
```
Result: booking 38, customer 99. Check NULL on the **right** table.

**3. Missing commodity**
```sql
SELECT id, awb_number, status FROM bookings WHERE commodity IS NULL;
```
Never `= NULL`.

**4. Status counts in one row**
```sql
SELECT
  COUNT(CASE WHEN status = 'BKD' THEN 1 END) AS booked,
  COUNT(CASE WHEN status NOT IN ('BKD','DLV','CAN') THEN 1 END) AS in_transit,
  COUNT(CASE WHEN status = 'DLV' THEN 1 END) AS delivered,
  COUNT(CASE WHEN status = 'CAN' THEN 1 END) AS cancelled
FROM bookings;
```
Works because COUNT skips NULL, and CASE returns NULL when nothing matches.

**5. Bookings per day, last 7 days**
```sql
SELECT DATE(created_at) AS day, COUNT(*) AS bookings
FROM bookings
WHERE created_at >= DATE('now', '-7 days')
GROUP BY DATE(created_at)
ORDER BY day;
```
PostgreSQL: `WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'`, `GROUP BY created_at::date`.

**6. Delivered but no DLV event**
```sql
SELECT b.id, b.awb_number
FROM bookings b
WHERE b.status = 'DLV'
  AND NOT EXISTS (
    SELECT 1 FROM tracking_events t
    WHERE t.booking_id = b.id AND t.milestone = 'DLV'
  );
```
Result: 1, 37, 38. A JOIN with `t.milestone <> 'DLV'` returns every booking that has any other event, which is almost every delivered booking. The question is "does no DLV row exist", which is a NOT EXISTS question.

**7. No BKD event**
```sql
SELECT b.id, b.awb_number, b.special_handling, b.status
FROM bookings b
WHERE NOT EXISTS (
  SELECT 1 FROM tracking_events t
  WHERE t.booking_id = b.id AND t.milestone = 'BKD'
);
```
Result: 11 rows. Nine are `DGR`. Every dangerous goods booking is missing its BKD event. That is a pattern, not bad luck, and it is planted bug #4. The other two are the legacy copies 37 and 38, imported without events.

**8. Status does not match latest event**
```sql
SELECT b.id, b.awb_number, b.status, x.milestone AS last_event
FROM bookings b
LEFT JOIN (
  SELECT booking_id, milestone,
         ROW_NUMBER() OVER (PARTITION BY booking_id ORDER BY event_time DESC, id DESC) AS rn
  FROM tracking_events
) x ON x.booking_id = b.id AND x.rn = 1
WHERE x.milestone IS NULL OR b.status <> x.milestone;
```
Result: 1, 21, 37, 38. The LEFT JOIN plus `IS NULL` catches bookings with no events at all; a plain `<>` would silently skip them, because comparing to NULL is unknown.

**9. Wrong chargeable weight**
```sql
SELECT id, awb_number, weight_kg, volumetric_kg, chargeable_kg
FROM bookings
WHERE chargeable_kg < MAX(weight_kg, volumetric_kg)
   OR chargeable_kg * 2 <> CAST(chargeable_kg * 2 AS INTEGER);
```
SQLite `MAX(a, b)` with two arguments returns the larger value. PostgreSQL and MySQL: `GREATEST(weight_kg, volumetric_kg)`.
0 rows after reset. Create a 100 × 100 × 100 cm, 100 kg booking in the app and it appears: chargeable 166.5, should be 167.0. Planted bug #2.

**10. Airports with no outbound bookings**
```sql
SELECT a.code, a.city
FROM airports a
LEFT JOIN bookings b ON b.origin = a.code
WHERE b.id IS NULL;
```
Result: ORD, BOM, CDG.

**11. Latest event per booking**
```sql
SELECT booking_id, milestone, event_time
FROM (
  SELECT booking_id, milestone, event_time,
         ROW_NUMBER() OVER (PARTITION BY booking_id ORDER BY event_time DESC, id DESC) AS rn
  FROM tracking_events
)
WHERE rn = 1;
```
PARTITION BY restarts the numbering for each booking.

**12. Top 2 per customer, ties kept**
```sql
SELECT customer_id, awb_number, chargeable_kg, rnk
FROM (
  SELECT customer_id, awb_number, chargeable_kg,
         DENSE_RANK() OVER (PARTITION BY customer_id ORDER BY chargeable_kg DESC) AS rnk
  FROM bookings
)
WHERE rnk <= 2;
```

**13. Weight per customer, including zero**
```sql
SELECT u.full_name,
       COUNT(b.id) AS bookings,
       COALESCE(SUM(b.chargeable_kg), 0) AS total_kg
FROM users u
LEFT JOIN bookings b ON b.customer_id = u.id AND b.status <> 'CAN'
WHERE u.role = 'customer'
GROUP BY u.id, u.full_name
ORDER BY total_kg DESC;
```
The trap: the `status <> 'CAN'` filter goes in the **ON** clause. Put it in WHERE and a customer with zero bookings disappears, because WHERE removes the NULL row the LEFT JOIN created. `COUNT(b.id)` gives 0 for them; `COUNT(*)` would wrongly give 1.

**14. Weight per origin above 3,000 kg**
```sql
SELECT origin, SUM(chargeable_kg) AS total_kg
FROM bookings
WHERE status <> 'CAN'
GROUP BY origin
HAVING SUM(chargeable_kg) > 3000
ORDER BY total_kg DESC;
```
Result: AUH, HKG, FRA. WHERE filters rows before grouping, HAVING filters totals after.

**15. Delete duplicates, keep the oldest**
```sql
-- 1. Look first
SELECT id, awb_number, created_at
FROM (
  SELECT id, awb_number, created_at,
         ROW_NUMBER() OVER (PARTITION BY awb_number ORDER BY created_at, id) AS rn
  FROM bookings
)
WHERE rn > 1;

-- 2. Then delete
DELETE FROM bookings
WHERE id IN (
  SELECT id FROM (
    SELECT id, ROW_NUMBER() OVER (PARTITION BY awb_number ORDER BY created_at, id) AS rn
    FROM bookings
  ) WHERE rn > 1
);
```
In a real database, wrap it in a transaction so you can roll back. Then run `python -m app.seed` to restore the data.

---

## Bonus answers

* **Duplicates allowed:** `awb_number` has no UNIQUE constraint. Recommend a unique index, after cleaning existing duplicates, plus an API check that returns 409 Conflict.
* **COUNT(*) vs COUNT(commodity):** they differ by 1, booking 3 has NULL commodity.
* **NOT IN with NULL:** if the subquery returns any NULL, every comparison becomes unknown and the query returns zero rows. Use NOT EXISTS.
* **Three queries after creating a booking in the UI:** the booking row with every field compared to what was entered, including chargeable weight; the BKD tracking event for it; and the duplicate check on its AWB.

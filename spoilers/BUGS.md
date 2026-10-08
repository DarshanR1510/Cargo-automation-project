# Planted bugs (spoilers)

**Do not open this until you have hunted for at least two hours.** Finding them yourself is the whole exercise. When you think you have found one, write a test that fails because of it, then check here.

Run the fixed app with `CARGO_BUGS=0 python run.py`. A good test **fails** on the buggy app and **passes** on the fixed one. That is how you prove the test checks the right thing.

| # | Bug | Layer | Severity | How to catch it |
|---|---|---|---|---|
| 1 | **Customer can view another customer's booking.** `GET /api/bookings/{id}` and the detail page do not check ownership. | API + UI | Critical, data leak | Log in as `globex`, open an `acme` booking ID. Two users in one test. |
| 2 | **Chargeable weight rounds to nearest 0.5 instead of up.** 166.67 becomes 166.5, should be 167.0. The form preview shows 167.0, the saved booking shows 166.5. | API | High, revenue loss on every booking | Boundary values. Compare UI estimate with saved value. SQL question 9. |
| 3 | **Weight of 0 is accepted.** Server checks `< 0` instead of `<= 0`. The UI does not block it either. | API + UI | Medium | Boundary value test at the API layer. |
| 4 | **DGR bookings get no BKD tracking event.** Tracking shows nothing for dangerous goods. | Integration | High, customer sees no status | Create a DGR booking, track it. SQL question 7 shows the pattern in old data too. |
| 5 | **Double click creates two bookings.** Submit button is not disabled and the API is slow. | UI | High, duplicate charges | `dblclick()`, then count bookings through the API or SQL. |
| 6 | **Expired token returns 500 instead of 401.** | API | Medium | Start with `CARGO_TOKEN_TTL=5`, wait, call `/api/me`. |
| 7 | **Milestones accepted out of order.** DLV can be recorded straight after BKD. | API | High, false delivery status | Negative test: post DLV on a new booking, expect 409. |
| 8 | **Files over 5 MB accepted.** | API | Medium, storage and abuse risk | Upload a 6 MB file, expect 413. |
| 9 | **Dashboard counts cancelled bookings as active.** | API + UI | Medium, wrong business numbers | Compare dashboard number with SQL `WHERE status <> 'CAN'`. |
| 10 | **Search results race.** Type fast and an older, slower response can overwrite the newer one. The table shows results for the wrong search text. | UI | Medium, and makes tests flaky | Type a search, change it quickly, assert every row matches the final text. Run with `--repeat-each=20` style loops to see it fail sometimes. |

## Data problems in the seed (not app bugs, legacy import issues)

* AWB `607-10000082` exists twice (no UNIQUE constraint on `awb_number`).
* Booking 38 belongs to customer 99, who does not exist.
* Booking 1 is DLV but its DLV event is missing.
* Booking 3 has no commodity.

## How to talk about these in an interview

Pick bug 1, 2 or 10. For each, say: how you found it, which layer you tested it at and why, the test you wrote, and the impact. Bug 10 is your flaky test story: the test failed one run in five, you ran it in a loop, opened the trace, saw two `/api/bookings` responses arriving out of order, and the fix belonged in the product, not in a longer wait.

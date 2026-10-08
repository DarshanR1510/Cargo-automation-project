# Product specification

This is the **source of truth**. Test the app against this document, not against what the app happens to do. When the app and this spec disagree, that is a bug.

## Users and roles

| Role | Can do |
|---|---|
| Customer (freight forwarder) | Create, view, edit and cancel **their own** bookings. Upload documents. Track any shipment. |
| Admin (cargo operations) | View all bookings. Record tracking milestones. See the operations dashboard. Cannot create bookings. |
| Anyone, not logged in | Track a shipment by AWB number. |

A customer must never see or change another customer's booking. Trying to open one returns **404** (not 403, so we do not confirm the booking exists).

## Authentication

* `POST /api/auth/login` returns a bearer token valid for `CARGO_TOKEN_TTL` seconds (default 900).
* Wrong username or wrong password returns **401** with the same message for both, so attackers cannot discover valid usernames.
* Missing, invalid or **expired** token returns **401**. Never a 500.
* The UI uses the same token in a `session` cookie.

## Booking rules

| Field | Rule |
|---|---|
| origin, destination | Must be a known airport code. Must be different. |
| pieces | Whole number, 1 to 999 |
| weight_kg | Greater than 0, at most 10,000 |
| length_cm, width_cm, height_cm | Greater than 0, at most 300 |
| commodity | Required, not blank |
| special_handling | One of GEN, DGR, PER, PIL, AVI. Default GEN |
| flight_date | Today or later |

* Missing fields or wrong types return **422**. Business rule failures return **400** with a list of errors.
* A successful booking returns **201**, gets status **BKD**, and a **BKD tracking event is created immediately, for every type of cargo**.
* Submitting the form once must create exactly **one** booking, however many times the button is clicked.

## AWB number

Format `607-NNNNNNNC`: airline prefix 607, a 7 digit serial, then a check digit equal to the serial modulo 7. Example: `607-10000082` is valid because 1000008 mod 7 = 2.

Tracking an AWB with a wrong format or wrong check digit returns **400**. A valid but unknown AWB returns **404**.

## Weight calculation

* Volumetric weight = length × width × height in cm ÷ 6000
* Chargeable weight = the higher of actual and volumetric weight, **rounded up** to the next 0.5 kg

Example: 100 × 100 × 100 cm, 100 kg actual. Volumetric = 166.67 kg. Chargeable = **167.0 kg**.

The UI shows an estimate on the form before saving. The saved value must match it.

## Editing and cancelling

* Only bookings in **BKD** status can be edited or cancelled. Otherwise **409**.
* Cancelling sets status **CAN** and adds a CAN tracking event. The UI asks for confirmation first.
* Editing weight or dimensions recalculates chargeable weight.

## Tracking milestones

Milestones must happen in this order, one step at a time:

`BKD → RCS → MAN → DEP → ARR → RCF → NFD → DLV`

* Recording a milestone out of order returns **409**.
* No events can be added after DLV or CAN.
* The booking status always equals its latest milestone.
* Only admins can record milestones. Customers get **403**.

## Documents

* PDF, PNG or JPG only. Anything else returns **400**.
* Maximum 5 MB. Larger files return **413**.
* Empty files return **400**.

## Operations dashboard

* **Active bookings** and **active chargeable kg** exclude cancelled bookings.

## Bookings list

* Customers see only their own bookings. Admins see all.
* Search matches AWB or commodity. Status filter. 10 per page.
* The table must always show results for the **latest** search text, even if the network is slow.
* Export CSV downloads the same set of bookings the user is allowed to see.

## Test support

* `POST /api/test/reset` restores the seed data. Use it to make tests independent. Disabled when `CARGO_TEST_MODE=0`.
* API documentation: http://127.0.0.1:8000/docs

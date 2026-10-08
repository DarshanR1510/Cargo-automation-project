# Learning plan

You write every test. The app is only the target.

Each module has four parts: **build**, **concepts**, **interview questions** and **when it breaks**. A module is done when the tests are green (or red on purpose, against a planted bug) **and** you can explain every concept out loud in three minutes without notes. Add your answers to `docs/MY_NOTES.md` as you go. That file becomes your interview prep.

Order follows the test pyramid on purpose: API first, then data, then UI.

## Target structure

Build towards this. Do not create it all at once, let it grow module by module.

```
tests/
  conftest.py              shared fixtures: reset, auth, api client, db
  api/
    test_auth_api.py
    test_bookings_api.py
    test_tracking_api.py
    test_documents_api.py
  ui/
    test_login.py
    test_bookings_list.py
    test_create_booking.py
    test_booking_detail.py
    test_tracking_page.py
    test_admin.py
  pages/                   page objects
  utils/                   api client, db helper, test data builders
```

## Git rules for this project

* One branch per module: `git switch -c module-1-api-tests`
* Small commits with a clear message: `Add parametrized validation tests for booking weight`
* Merge back to `main` when the module is done, then push.
* Never commit `data/`, reports or `.venv` (already in `.gitignore`).

---

## Module 0: setup and first push (30 min)

**Build**
1. Create a virtual environment, install `requirements-dev.txt`, run `playwright install chromium`.
2. Start the app, log in as each user, click through every page, read `docs/SPEC.md` fully.
3. `git init`, first commit, create an empty GitHub repo, push.
4. Run `pytest -v`. Two tests should pass.

**Interview questions**
* How do you set up Playwright with Python from scratch? (`pip install pytest-playwright`, `playwright install`)
* What is the difference between `git add`, `git commit` and `git push`?

---

## Module 1: API tests first (2 h)

**Build** `tests/api/`
* A fixture that logs in and returns an `APIRequestContext` with the `Authorization` header set. One for each user.
* Login: valid, wrong password, unknown user (same message?), missing fields.
* Create booking: happy path checks status 201, every field in the body, AWB format, status BKD.
* Validation with `@pytest.mark.parametrize`: weight 0, negative, 10000, 10000.1, pieces 0 and 1000, same origin and destination, unknown airport, past date, blank commodity, missing field (422).
* Permissions: no token (401), customer calling admin summary (403), admin creating a booking (403), `globex` reading an `acme` booking (spec says 404).
* Milestones: correct next step (201), skipping ahead (spec says 409), event after CAN (409).
* Tracking: valid, bad check digit (400), unknown valid AWB (404).
* Documents: PDF ok, `.exe` (400), empty (400), 6 MB (spec says 413).
* Expired token: start the app with `CARGO_TOKEN_TTL=5`, wait, expect 401.

**Concepts**
* `APIRequestContext`, `playwright.request.new_context(base_url=..., extra_http_headers=...)`
* Fixture scopes: function, module, session, and what each costs
* `parametrize` with `ids=` so failures are readable
* 400 vs 401 vs 403 vs 404 vs 409 vs 413 vs 422
* Why validation belongs at this layer and not the UI

**Interview questions**
* Why test validation at API level instead of UI?
* How do you handle authentication in API automation? Token expiry?
* 401 vs 403. Authentication vs authorization.
* What is idempotency? Which method is not idempotent?

**When it breaks** (write your own sentence for each concept)

You should find **at least 5 planted bugs** in this module.

---

## Module 2: database checks (1 h)

**Build** `tests/utils/db.py` and tests that use it
* A `db` fixture that opens `data/cargo.db` with `sqlite3` and closes it after.
* After creating a booking through the API, assert the row in `bookings` matches every field, including `chargeable_kg` calculated from the spec.
* Assert a `BKD` row exists in `tracking_events` for that booking. Try it with `special_handling` GEN and DGR.
* After cancelling, assert status `CAN` and a CAN event.
* Compare the admin summary numbers with your own SQL.
* Finish `sql/PRACTICE.md`, all 15 questions.

**Concepts**
* Why a 201 does not prove the data is correct
* Test data setup through the API, verification through the DB
* `@pytest.mark.parametrize` for boundary values of the weight calculation (166.67 kg, exactly 166.5, exactly 167.0)

**Interview questions**
* How do you use SQL in testing?
* A booking is successful in the UI but missing in tracking. How do you investigate?
* How do you find records missing downstream?

---

## Module 3: first UI tests and page objects (1.5 h)

**Build** `tests/pages/login_page.py`, `tests/pages/bookings_page.py`, `tests/ui/test_login.py`
* Login success redirects to `/bookings` for customers and `/admin` for the admin.
* Wrong password shows the error and stays on `/login`.
* Logged out user opening `/bookings/1` is sent to login with `next` set.
* Logout, then press back. What do you see?

**Concepts**
* Locator priority: `get_by_role`, `get_by_label`, `get_by_test_id`, text, CSS last
* Strict mode, and why matching two elements fails
* `expect(locator).to_have_text()` retries, `assert locator.inner_text() == ...` does not
* What a page object holds and what it should not (assertions stay in tests)
* `base_url` in `pytest.ini`

**Interview questions**
* What makes a good locator? How do you handle dynamic elements?
* What is a page object? Where do assertions belong?
* What does auto waiting check, and when does it not save you?

---

## Module 4: login once, two users (1 h)

**Build**
* A session fixture that logs in each user once through the API and saves `storage_state` to a file. Tests reuse it, no UI login per test.
* A test with **two browser contexts** in one test: `acme` creates a booking, `globex` tries to open it by URL.

**Concepts**
* Browser vs context vs page. The context is the isolation unit.
* `browser.new_context(storage_state="acme.json")`
* Why every test logging in through the UI is slow and fragile

**Interview questions**
* How do you avoid logging in for every test?
* How do you test permissions between two users?

---

## Module 5: the booking journey (2 h)

**Build** `tests/pages/new_booking_page.py`, `tests/ui/test_create_booking.py`, `tests/ui/test_booking_detail.py`
* Fill the form, check the chargeable estimate, submit, land on the detail page, compare the saved chargeable weight with the estimate.
* Client side validation: submit empty form, check each field error.
* **Double click** the submit button, then count bookings through the API. Spec says one.
* Cancel a booking: handle the `confirm()` dialog with `page.once("dialog", ...)`. Also test dismissing it.
* Print label opens a new tab: `with page.expect_popup() as popup:`
* Export CSV: `with page.expect_download() as download:`, then open the file and check its rows.
* Upload a PDF with `set_input_files`, then a wrong type.

**Git exercise: stash.** Halfway through this module, stash your unfinished work with `git stash`, switch to `main`, fix a typo in the README, commit, switch back and `git stash pop`.

**Concepts**
* Dialogs, popups, downloads, uploads
* Why you verify the double click through the API, not the UI

---

## Module 6: waiting, flakiness, trace, mocking (2 h)

This is the module that wins interviews.

**Build** `tests/ui/test_bookings_list.py`
* Search for `Auto`, then quickly change it to `Doc`. Assert every row contains `Documents`.
* Run it 20 times: `pytest tests/ui/test_bookings_list.py -k search --count 20` (needs `pip install pytest-repeat`) or a loop. Write down how many times it fails.
* Turn on tracing (`--tracing retain-on-failure`), open a failed trace with `playwright show-trace`, and find the cause in the network tab.
* Decide: product bug or test bug? Write the defect report in `docs/MY_NOTES.md`.
* Network mocking with `page.route`: make `/api/bookings` return 500 and check the page does not hang. Make it return an empty list and check the empty state. Delay it by 3 seconds and check the loading message.
* Wait for the right signal: `with page.expect_response("**/api/bookings*") as response:`

**Git exercise: rebase.** Create a branch, make two commits. Meanwhile commit something on `main`. Then `git rebase main` on your branch and look at `git log --oneline --graph`. Compare with what `git merge` would have produced.

**Concepts**
* Why `wait_for_timeout` is the wrong fix
* `expect_response`, `page.route`, `route.fulfill`, `route.abort`
* Trace viewer: actions, DOM snapshots, network, console
* Product race vs test race. Retries hide, they do not fix.

**Interview questions**
* How do you handle flaky tests?
* How do you debug a test that only fails in CI?
* How do you test a page when the backend is down?

---

## Module 7: parallel and isolation (1 h)

**Build**
* `pip install pytest-xdist`, run `pytest -n 4`. Watch what breaks.
* Fix it: each test creates its own data instead of relying on seed rows, or reset in a session fixture. Avoid tests that depend on order.
* Add markers: `@pytest.mark.smoke`, `api`, `ui`. Run `pytest -m smoke`.
* Run against the fixed app: `CARGO_BUGS=0 python run.py`. Tests that caught bugs should now pass.

**Interview questions**
* How do you run tests in parallel in Playwright? (Python: `pytest-xdist`. TypeScript: `workers` in config.)
* What makes a test independent?
* Smoke vs sanity vs regression?

---

## Module 8: reports and CI (1 h)

**Build**
* HTML report: `pytest --html=report.html`. Screenshots and traces on failure: `--screenshot only-on-failure --tracing retain-on-failure`.
* `.github/workflows/tests.yml`: checkout, set up Python, install requirements, `playwright install --with-deps chromium`, start the app in the background, wait for `/api/health`, run `pytest -n 2`, upload `test-results/` as an artifact **even when tests fail** (`if: always()`).
* Decide: should the pipeline go red because of planted bugs? Mark known bug tests with `@pytest.mark.xfail(reason="BUG-1 IDOR", strict=True)` and explain why `strict=True` matters.

**Interview questions**
* How do you integrate tests into CI/CD?
* Why upload artifacts even when the job fails?
* What is xfail and when is it honest to use it?

---

## Module 9: say it out loud

For each module, three minutes, no notes, recorded on your phone if possible. Then write the README section **What I found** with your 10 bugs, the layer each was caught at, and the test that proves it. That section is what a client reads.

# Cargo QA Lab

An air cargo booking platform, and a test automation suite that tests it at every layer: API, database and browser.

The app is deliberately imperfect. It ships with **10 planted defects** across security, business rules, integration and UI timing. The goal of this project is to find them the way a QA engineer would on a real cargo platform, and to prove each one with an automated test.

**Stack:** Python · Playwright · pytest · SQL (SQLite) · FastAPI · GitHub Actions

## What the app does

* Freight forwarders log in, create shipment bookings, and get an AWB (air waybill) number with a check digit
* Chargeable weight is calculated from actual and volumetric weight
* Shipments move through IATA style milestones: BKD, RCS, MAN, DEP, ARR, RCF, NFD, DLV
* Anyone can track a shipment by AWB
* Operations staff record milestones and see a dashboard
* Customers upload shipping documents, print labels and export bookings to CSV

Full rules: [`docs/SPEC.md`](docs/SPEC.md). That document is the source of truth. Anything the app does differently is a bug.

## Run it

Needs Python 3.10 or newer.

```bash
python -m venv .venv
# Windows:      .venv\Scripts\activate
# Mac / Linux:  source .venv/bin/activate
pip install -r requirements-dev.txt
playwright install chromium

python run.py
```

Open http://127.0.0.1:8000. API docs at http://127.0.0.1:8000/docs.

| User | Password | Role |
|---|---|---|
| `acme` | `Acme@123` | Customer |
| `globex` | `Globex@123` | Customer |
| `admin` | `Admin@123` | Operations admin |

These are test accounts for a local practice app.

### Modes

| Setting | Effect |
|---|---|
| `CARGO_BUGS=0` | Run the fixed version. Your bug tests should fail on the default app and pass here. |
| `CARGO_SLOW=0` | Remove the artificial network delay |
| `CARGO_TOKEN_TTL=5` | Tokens expire after 5 seconds |
| `PORT=8001` | Run on another port, so buggy and fixed versions can run side by side |

Windows PowerShell: `$env:CARGO_BUGS="0"; python run.py`. Mac / Linux: `CARGO_BUGS=0 python run.py`.

Reset all data: `python -m app.seed`, or `POST /api/test/reset` from a test.

## Run the tests

In a second terminal, with the app running:

```bash
pytest                          # everything
pytest -m smoke                 # quick checks
pytest -n 4                     # parallel
pytest --headed --slowmo 300    # watch the browser
pytest --tracing retain-on-failure --screenshot only-on-failure
```

## Project layout

```
app/                the application under test
  main.py           API and pages
  domain.py         AWB check digit and weight rules
  seed.py           repeatable test data
  templates/        UI
docs/
  SPEC.md           requirements, test against these
  LEARNING_PLAN.md  module by module plan
  MY_NOTES.md       my explanations of every concept
sql/PRACTICE.md     15 SQL questions on the app database
scripts/sql.py      run SQL without installing anything
tests/              the test suite
spoilers/           planted bugs and SQL answers, open only after hunting
```

## What I found

*Fill this in as you find each bug: what it is, which layer caught it, why that layer, and the test that proves it.*

| # | Defect | Layer | Severity | Test |
|---|---|---|---|---|
| | | | | |

## Push to GitHub (first time)

```bash
git init
git add .
git commit -m "Cargo QA Lab: application under test and setup check"
git branch -M main
git remote add origin https://github.com/<your-username>/cargo-qa-lab.git
git push -u origin main
```

Create the empty repository on GitHub first, without a README, so the first push does not conflict.

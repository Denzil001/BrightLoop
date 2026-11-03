# Brightloop Subscription Management System

This repository hosts Brightloop, a subscription management web application built for ADMIN, STAFF and CUSTOMER roles.

## Primary evaluation requirements

1. **PostgreSQL relational database design:** First and most important. Primary/foreign keys, unique/check constraints, non-negative monetary rules, consistent decimal scaling, safe historical document snapshots, and migration hygiene.
2. **Backend API design:** Fast, modular, secure, input-validated REST APIs under `/api/v1`.
3. **Local relational persistence:** Final source of truth in PostgreSQL. BaaS and remote cloud DBs outside the agreed approach.
4. **Usability and performance:** Sub-two-second interactive response target under load; clean accessible UI with empty, loading, validation, and error states.
5. **Security:** Argon2id password hashing, secure session lifecycles, role-based access control, CSRF mitigation, and ownership isolation.

## Stack

- **Backend:** FastAPI, Pydantic, SQLAlchemy 2.x, Alembic, PostgreSQL 18
- **Frontend:** Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS, Lucide icons
- **Testing:** Pytest, Playwright, Mailpit (local SMTP capture)

## Database setup (Windows)

Native Windows PostgreSQL 18 operates on `127.0.0.1:5432` with two dedicated databases:
- Development database: `brightloop_dev` (Owner: `brightloop_app`)
- Disposable test database: `brightloop_test` (Owner: `brightloop_test`)

Application credentials reside in `backend/.env` (ignored by Git; see `backend/.env.example`).

For a fresh clone, install PostgreSQL 18 (including `psql`), Python 3.14, Node.js 22.18+ (verified here with 26.12.1), Docker Desktop and Google Chrome. Start the PostgreSQL service. Before creating `backend/.env`, copy the temporary provisioning example and enter the local PostgreSQL administrator password directly in that ignored file:

```powershell
Copy-Item .env.setup.example .env.setup
# Edit .env.setup locally: PGADMIN_USER and PGADMIN_PASSWORD.
python scripts/provision_local_db.py
$sessionKeyForSetup = python -c "import secrets; print(secrets.token_urlsafe(48))"
Add-Content -LiteralPath backend/.env -Value "SESSION_SECRET_KEY=$sessionKeyForSetup"
Remove-Variable sessionKeyForSetup
Copy-Item frontend/.env.example frontend/.env.local
```

Provisioning generates private application/test role passwords, saves their URLs before creating objects, verifies ownership/isolation and clears the temporary administrator password after success. It refuses conflicting existing objects instead of resetting their credentials. Keep existing private files when updating a working checkout. `backend/.env.example` is a configuration reference for optional issuer/SMTP settings; do not replace generated URLs with its placeholders. Continue with the dependency installation, migrations, admin bootstrap and application startup below.

To verify again without administrator credentials:

```powershell
python scripts/provision_local_db.py --check
```

The permission-probe table is rolled back; application tables are managed through reviewed Alembic migrations. The test database is exclusively for disposable test data. These commands verify database connectivity and permissions; application acceptance evidence is recorded in [docs/DEVELOPMENT_STATUS.md](docs/DEVELOPMENT_STATUS.md).

## Local email inbox (Docker)

PostgreSQL continues running through the existing local installation. Docker Compose runs only Mailpit; it does not create a second database or move existing database data. The official Mailpit image is pinned by digest in `compose.yaml`, with a named volume retaining the local inbox across container restarts. Configuration follows the [Mailpit Docker documentation](https://mailpit.axllent.org/docs/install/docker/).

With Docker Desktop running, start/check from the repository root:

```powershell
docker compose config --quiet
docker compose up -d mailpit
docker compose ps
python scripts/check_local_mail.py
```

Open the inbox at [http://127.0.0.1:8025](http://127.0.0.1:8025). The mail check sends a synthetic message to `setup-check@brightloop.test` and verifies it in the local inbox; it does not send to an external recipient. Ports bind to loopback only. Inbox data remains in Docker's `brightloop_mailpit_data` volume, outside Git.

Backend email settings in the ignored `backend/.env` and shareable `backend/.env.example`:

```dotenv
SMTP_HOST=127.0.0.1
SMTP_PORT=1025
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_STARTTLS=false
SMTP_SSL=false
EMAIL_FROM=Brightloop <no-reply@brightloop.test>
```

## Backend setup and test execution (Windows)

The backend and pinned dependencies are verified with Python 3.14 within `backend/.venv`.

1. Create the backend environment if missing and install the pinned dependencies:
```powershell
if (-not (Test-Path backend/.venv/Scripts/python.exe)) { python -m venv backend/.venv }
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
```

2. Run Alembic database migrations on development database (`brightloop_dev`):
```powershell
cd backend
.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
cd ..
```

3. Run backend unit, authentication, catalog, pricing, and PostgreSQL constraint test suite:
```powershell
$env:PYTHONPATH=".;backend"
backend\.venv\Scripts\python.exe -m pytest backend/tests -v
```
The backend test suite executes against the isolated `brightloop_test` database, exercising check constraints, composite unique/foreign keys, partial unique indexes, total identity, payment validation, financial deletion safety, Argon2id password complexity, login/logout, CSRF protection, token expiry, admin bootstrap, staff RBAC/deactivation, customer isolation, Retry-After header preservation, truthful email delivery status handling, products & 560 variant price adjustment, non-negative checks, tax rules and bounds, discount revisions & prospective deactivation with historical cutoff immutability, quotation template final state validation & inactive catalog protection, sanitized database constraint error responses (no raw SQL/internals leaked), and authoritative Decimal pricing calculations (including the ₹2,888.64 worked acceptance case, plan availability windows, rejection of fabricated entitlements or excess included quantities, required override reasons for negotiated prices, revision-aware pinned terms, and integer minor-unit proportional fixed discount allocation).

4. Bootstrap initial system administrator (local CLI):
```powershell
backend\.venv\Scripts\python.exe scripts/bootstrap_admin.py --email admin@brightloop.test --name "System Administrator" --password "Admin@Secure123"
```

5. Install the pinned browser verification dependencies. The runners use the installed Google Chrome channel; install Chrome first if it is absent:
```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-test.txt
```

Run automated Playwright browser journeys after starting the backend and frontend below. Mailpit is mandatory for the core email journeys; no email journey is silently skipped. Run these sequentially. The core runner resets the synthetic admin; do not run it alongside other authenticated runners. Shared authentication protection allows 15 logins per five minutes from one IP; the shared helper reports a confirmed 429 and waits for Retry-After before one retry, preserving form inputs. It does not disable protection or replay ambiguous financial writes:
```powershell
# Phase 2 journeys (registration, Mailpit linking/reset, staff lifecycle, customer CRUD)
backend\.venv\Scripts\python.exe -u scripts/test_browser_journeys.py

# Phase 3 catalog & templates journeys (A02-A09 products, variants, plans, taxes, discounts, templates, live pricing preview)
backend\.venv\Scripts\python.exe -u scripts/test_catalog_journeys.py

# Phase 4 staff quotation acceptance and customer request review
backend\.venv\Scripts\python.exe -u scripts/test_subscription_journeys.py

# Staff pause/resume, add-on, closed-term renewal and closure boundaries
backend\.venv\Scripts\python.exe -u scripts/test_operational_lifecycle.py

# One linked admin/customer/staff evaluation rehearsal, including real Mailpit delivery
backend\.venv\Scripts\python.exe -u scripts/test_evaluator_demo.py

# Phase 5 billing, invoices, real Mailpit attachment and customer PDF/cancellation
backend\.venv\Scripts\python.exe -u scripts/test_billing_journeys.py

# Phase 6 payments, lost-response retry, ledgers and receipts
backend\.venv\Scripts\python.exe -u scripts/test_payment_journeys.py
```

6. Start FastAPI backend server:
```powershell
$env:PYTHONPATH='backend'
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log
```
- Liveness check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Database readiness check: [http://127.0.0.1:8000/ready](http://127.0.0.1:8000/ready)
- Company metadata: [http://127.0.0.1:8000/api/v1/meta](http://127.0.0.1:8000/api/v1/meta)
- OpenAPI interactive docs: [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs)

## Frontend setup and startup (Windows)

The frontend is built with Next.js 15 (App Router), React 19, TypeScript, and Tailwind CSS. Use Node.js 22.18 or newer; this workspace was verified with Node.js 26. Native decimal tests use Node's TypeScript support.

1. Install dependencies:
```powershell
cd frontend
npm ci
```

2. Production build verification:
```powershell
npm run build
```

3. Start the verified production build on loopback:
```powershell
npm run start -- --hostname 127.0.0.1
```
Open [http://localhost:3000](http://localhost:3000) for the application landing page.
Check [backend liveness](http://localhost:8000/api/v1/health) and [database readiness](http://localhost:8000/api/v1/ready) for local startup diagnostics. The frontend follows the 32-page inventory in docs/USER_FLOWS.md.

Evaluation preparation: [walkthrough and team handoff](docs/EVALUATOR_DEMO.md), [accessibility and keyboard evidence](docs/ACCESSIBILITY_VERIFICATION.md), and [final acceptance](docs/FINAL_ACCEPTANCE.md). All phases 0–9 pass their recorded local gates; dated evidence is in docs/DEVELOPMENT_STATUS.md.

Monetary form values remain decimal strings through submission and edit loading. Browser previews use integer minor units; the backend computes authoritative values using Decimal. API money inputs enforce NUMERIC(18,2) and reject JSON numbers to prevent client precision loss. From `frontend`, `npm run test:decimal` runs the exact-decimal regressions using the installed Node runtime's native TypeScript support (verified with Node 26).

From `frontend`, `npm run lint` runs pinned Biome with the recommended rules and React/Next.js domains, and fails on any warning. `npm ci` installs the lockfile-defined tooling. Type checking remains part of `npm run build`; lint runs separately. See [security verification](docs/SECURITY_VERIFICATION.md) for dependency evidence.

`backend/.venv/Scripts/python.exe scripts/verify_fresh_setup.py` verifies every migration against a new schema in the guarded disposable test database, checks model/schema parity and exercises initial API use. It removes only its own temporary schema. Run it separately from Pytest because its preservation check expects existing test records to remain unchanged during verification. This checks empty-schema setup, not a fresh operating-system installation.

## Subscription development status

Phase 4 adds five planned subscription pages for staff/admin and customers. Operational users prepare drafts, preview server-calculated prices, issue/revise quotes, confirm the existing subscription and activate service. Accepted lines, taxes, plan policies, pinned discount revisions (including disjoint product rules) and the displayed quotation estimate remain historical snapshots. A combined save/issue command commits atomically.

Pause/resume, early closure, renewal and add-on changes record dated events. Customer requests require operational review; approval rejects stale versions or changed commercial estimates. Future events leave today's service unchanged. The Phase 5 billing engine invokes the tested event applier chronologically. The separate scheduler worker now invokes that same engine. Invoice, payment and report features are implemented. See docs/DEVELOPMENT_STATUS.md for verified commands, evidence and team handoff.

## Billing and invoice operation

Billing uses accepted line/tax/discount snapshots and the same Decimal calculator as previews. Each period locks its subscription and commits invoice snapshots, discount redemption, cursor and outcome together. Historical terms and pauses remain eligible for recovery after closure/expiry. Runs are bounded to 100 new periods/100 scanned subscriptions per request and expose a continuation cursor; recovery batches link to their preceding run.

Administrators use `/app/billing-runs` or the same service through the CLI:
```powershell
# One bounded batch, today in Asia/Kolkata:
backend/.venv/Scripts/python.exe scripts/run_billing.py
# Continue bounded batches through the full scan; stop and report any failures:
backend/.venv/Scripts/python.exe scripts/run_billing.py --drain
# Limit a diagnostic/recovery run to a known subscription:
backend/.venv/Scripts/python.exe scripts/run_billing.py --subscription-id SUBSCRIPTION_UUID
```

Invoices begin as operational drafts. Staff/admin may correct billing metadata, confirm, cancel only when completely unpaid, and send issued non-cancelled invoices to the snapshotted billing email. Customer pages show only owned issued documents, including their marked historical cancellations. Cancellation preserves the period identity and discount consumption. Zero-total confirmation settles without creating a payment. PDF generation is local through ReportLab; email reuses the configured SMTP adapter and attaches the PDF. Delivery failures are persisted and explicit retries do not pretend delivery was guaranteed.

Phase 5 verification includes independent PostgreSQL races, all four intervals, proration, rollback/retry, PDF text and visual checks, real Mailpit attachment delivery and desktop/mobile browser workflows. Role dashboards and administrator reports are delivered in Phase 7. Scheduled invocation is delivered in Phase 8; final performance evidence remains Phase 9.

## Payments and receipts

Staff/admin record payments from an issued invoice with a positive outstanding balance. Each submission has a persisted request key; the server locks the invoice and computes its balance from the immutable PostgreSQL payment ledger. Same-key/same-payload retries return the original payment, including after settlement; changed intent conflicts. Partial and final payments update invoice status transactionally. Overpayment, non-positive amounts, future dates, blank notes, draft/cancelled invoices and customer writes are rejected.

The browser preserves an unconfirmed submission in per-user/per-invoice session storage so a reload after a lost response can retry the same intent. Customers have read-only owned payment history and receipt downloads. Invoice pages show recent payment history and link to filtered ledgers. A PostgreSQL trigger rejects payment UPDATE/DELETE under the accepted initial no-refund/no-edit policy; no application operation disables it.

`/app/payments` and `/portal/payments` provide filtered/paginated ledgers with read-only drawers. Receipts are generated locally from persisted payment and invoice snapshots and contain no internal actor or request-key metadata for customers.

Phase 7 verification: 126 backend tests passed; production build passed; three reporting browser journeys passed (zero skipped). Run `backend/.venv/Scripts/python.exe -u scripts/test_reporting_journeys.py` against the local servers. Reports use payment-date ranges for receipts and current persisted balances for outstanding/overdue; customer metrics and drill-down lists remain owner-scoped.

## Scheduling and security verification

The scheduler is a separate process, with PostgreSQL advisory ownership locks, bounded continuation and persisted heartbeat/status. Run `backend/.venv/Scripts/python.exe scripts/run_scheduler.py --interval-seconds 60` from the root to keep automatic billing active. It creates draft invoices; it does not automatically issue or email them. The browser verification leaves its scoped worker STOPPED, as the UI truthfully reports. No reboot-persistent operating-system service was installed.

Phase 8 backend verification: 138 passed, including real timer-process replay, orphan/live-run recovery, frozen auto-close policy, parallel shared PostgreSQL authentication limits and password-reset/session races. Production frontend build passed; core browser/Mailpit journeys passed five; hardening browser journeys passed four. Bandit, pinned Python dependency audit and npm runtime audit reported no findings after a PostCSS override. See [operating instructions](docs/OPERATIONS.md), [security scope/evidence](docs/SECURITY_VERIFICATION.md), and [current development status](docs/DEVELOPMENT_STATUS.md). The full dataset, page-load and final requirement audit remain Phase 9.

## Phase 9 checkpoint

The measured browser checkpoint passed all 420 observations across the 32 templates plus ten staff variants at concurrency 1 and 5; maximum 1,463.24 ms over the isolated 5,000-subscription / 50,000-invoice / 100,000-payment dataset. See [performance evidence and reproduction](docs/PERFORMANCE_VERIFICATION.md). The seed never changes public application records.

Navigation, large selectors, frozen term policies and per-line quote estimates were corrected during the source audit. Phase 9 is still in progress: the 300-due mixed billing/retry scenario, complete action/API contract audit, setup/demo/Git review and final integrated rerun remain open in [final acceptance](docs/FINAL_ACCEPTANCE.md). A successful benchmark alone is not complete-project acceptance.

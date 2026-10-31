# Brightloop Subscription Management System

Responsive subscription management application planned for Admin, Staff and Customer roles.

## Planning documents

| Document | Purpose |
|---|---|
| [BUILD_GUIDE.md](BUILD_GUIDE.md) | Phase 0-9 implementation sequence, proposed business rules, dependencies and acceptance gates |
| [User flows and page specifications](docs/USER_FLOWS.md) | All 32 page templates, exact page contents, role permissions, navigation and 15 user journeys |
| [AGENTS.md](AGENTS.md) | Persistent engineering, security, testing and collaboration instructions |
| [Planning verification](docs/PLANNING_VERIFICATION.md) | Source coverage, document consistency checks and pending team decisions |
| [Phase 0 business rules](docs/business-rules.md) | D01-D10 recommendations, state tables and worked financial/date examples |
| [Database design](docs/database-design.md) | Proposed entities, ER diagram, constraints, indexes and historical snapshots |
| [API design](docs/api-design.md) | Proposed routes, inputs, access policies, errors and idempotency |
| [Architecture and Phase 0 handoff](docs/architecture.md) | Service boundaries, transactions, security, test approach and acceptance checklist |

The plan follows the supplied Subscription Management System PDF and the evaluator's emphasis on relational database design, backend APIs, dynamic persisted data, validation, clean UI, security, performance and team ownership.

## Current status

Phase 0 design accepted; Phase 1 (foundation, database models, migrations, and layout) implemented, corrected, and verified. Both development (`brightloop_dev`) and disposable test (`brightloop_test`) databases are migrated to head with the full 36-entity schema, partial unique indexes, and foreign keys. Native PostgreSQL 18 and Docker Mailpit are operational. All 17 backend unit and database constraint tests pass. Frontend App Router builds cleanly with working navigation and connects to backend diagnostics.

Page inventory: **4 public + 10 shared admin/staff + 11 admin-only + 7 customer = 32 templates**. Dialogs, tabs, redirects, error states and document downloads are included in their parent workflows rather than counted as extra pages.

Approved technology direction: Next.js/React/TypeScript/Tailwind frontend; FastAPI/Pydantic backend; local PostgreSQL with SQLAlchemy/Alembic; Pytest and Playwright. Setup/start/migration/test commands will be added when the corresponding implementation exists and has been verified.

## Local database preparation (Windows)

The setup helper uses Python's standard library and the PostgreSQL 18 client at `C:/Program Files/PostgreSQL/18/bin/psql.exe`. PostgreSQL must be running locally. No Python database driver is needed for this preparation step.

1. Copy `.env.setup.example` to `.env.setup` if it does not already exist. Enter the installation administrator password locally in `PGADMIN_PASSWORD`; it is raw text, not a URL-encoded value. Never paste or commit this file.
2. Run from the repository root:

```powershell
python scripts/provision_local_db.py
```

This creates `brightloop_dev` owned by `brightloop_app` and `brightloop_test` owned by `brightloop_test`. The two users have separate generated passwords, no superuser/role-creation/database-creation privileges, and no access to each other's database. The helper refuses to adopt existing named objects without saved project credentials or overwrite databases with different owners. Generated passwords are saved before provisioning to allow recovery after an interrupted run.

Private connections are stored in ignored `backend/.env`; the browser API URL is in ignored `frontend/.env.local`. Share only the placeholder `.env.example` files. These variable names are the configuration contract for the forthcoming application; application loading is not implemented yet.

The helper checks owner login, restricted role flags, table creation/insert followed by rollback, and both directions of cross-database denial. On successful preparation it clears the temporary administrator password from `.env.setup`. Retrying with the cleared password checks existing saved application credentials without rotating them.

To verify again without administrator credentials:

```powershell
python scripts/provision_local_db.py --check
```

The permission-probe table is rolled back; application tables will be created later through reviewed Alembic migrations. The test database is exclusively for disposable test data. These checks do not certify the unbuilt application or satisfy the full Phase 1 gate.

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
EMAIL_FROM=Brightloop <noreply@brightloop.test>
```

These settings are for a backend running on the host and the loopback-only development inbox. No external email account is required. The forthcoming backend will read these settings when authentication/invoice email is implemented; working SMTP alone does not implement those features.

To stop the inbox while retaining its captured messages:

```powershell
docker compose stop mailpit
```

Start it again with `docker compose up -d mailpit`. PostgreSQL's Windows service is managed separately. If ports 1025/8025 conflict, identify the owning process/service before changing mappings and matching local settings; do not stop unrelated services.

## Backend setup, migrations and tests (Windows)

The FastAPI backend runs with Python 3.14+ in a dedicated virtual environment.

1. Create virtual environment and install dependencies:
```powershell
python -m venv backend/.venv
backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

2. Run Alembic database migrations on development database (`brightloop_dev`):
```powershell
cd backend
.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
cd ..
```

3. Run backend unit, authentication, and PostgreSQL constraint test suite:
```powershell
$env:PYTHONPATH='backend'
backend\.venv\Scripts\python.exe -m pytest backend/tests -v
```
All 32 tests execute against the isolated `brightloop_test` database, exercising check constraints, composite unique/foreign keys, partial unique indexes, total identity, payment validation, financial deletion safety, Argon2id password complexity, login/logout, CSRF protection, token expiry, admin bootstrap, staff RBAC/deactivation, and customer isolation.

4. Bootstrap initial system administrator (local CLI):
```powershell
backend\.venv\Scripts\python.exe scripts/bootstrap_admin.py --email admin@brightloop.test --name "System Administrator" --password "Admin@Secure123"
```

5. Run automated Playwright browser journeys (verifies registration, Mailpit linking/reset, staff lifecycle, customer CRUD):
```powershell
backend\.venv\Scripts\python.exe -u scripts/test_browser_journeys.py
```

6. Start FastAPI backend server:
```powershell
$env:PYTHONPATH='backend'
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
- Liveness check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Database readiness check: [http://127.0.0.1:8000/ready](http://127.0.0.1:8000/ready)
- Company metadata: [http://127.0.0.1:8000/api/v1/meta](http://127.0.0.1:8000/api/v1/meta)
- OpenAPI interactive docs: [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs)

## Frontend setup and startup (Windows)

The frontend is built with Next.js 15 (App Router), React 19, TypeScript, and Tailwind CSS.

1. Install dependencies:
```powershell
cd frontend
npm install
```

2. Production build verification:
```powershell
npm run build
```

3. Start Next.js development server:
```powershell
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) for the application landing page.
Visit [http://localhost:3000/health-check](http://localhost:3000/health-check) for the development health and readiness diagnostic dashboard.

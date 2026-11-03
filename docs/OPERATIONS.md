# Local operation and scheduled billing

Run commands from the repository root unless a working directory is stated. PostgreSQL is the single financial source of truth; Docker hosts only Mailpit. Private connection URLs belong in ignored backend/.env. Never copy them into logs or command arguments.

## Start the application

1. Ensure the native PostgreSQL service is running. Run `backend/.venv/Scripts/python.exe scripts/provision_local_db.py --check` to check the configured development and isolated test databases without printing credentials.
2. Start Docker Desktop, then `docker compose up -d mailpit`.
3. From backend, run `.venv/Scripts/python.exe -m alembic upgrade head`.
4. From backend, run `.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log`.
5. From frontend, run `npm ci`, `npm run build`, then `npm run start -- --hostname 127.0.0.1 --port 3000` in a separate terminal. On this Windows machine the roaming npm shim is broken; invoke npm using `& 'C:/Program Files/nodejs/node.exe' 'C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js'` followed by the same arguments.
6. Open http://localhost:3000. Keep localhost consistent for browser cookie/origin handling. The API is http://localhost:8000/api/v1; Mailpit is http://127.0.0.1:8025.

## Start the scheduler

In a separate terminal, from the repository root:

```powershell
backend/.venv/Scripts/python.exe scripts/run_scheduler.py --interval-seconds 60 --max-batches 10
```

Keep the worker running alongside the API. It runs immediately and then waits 60 seconds after each completed tick. Each tick captures the current Asia/Kolkata business date. It uses the same billing implementation as the admin trigger and CLI; invoices remain DRAFT for operational confirmation. Scheduling does not automatically confirm invoices or send email.

A dedicated PostgreSQL connection holds the scheduler advisory lock for each tick. Another worker skips overlapping work. Each billing run also holds a separate advisory ownership lock, allowing recovery to distinguish an abandoned run from a slow live API/CLI/worker run. Subscription locks, global discount locks and invoice-period uniqueness remain the financial race protections, including manual versus scheduler races. Connection pools must allow the worker lock, run ownership lock and financial session concurrently.

One batch scans at most 100 subscriptions and creates at most 100 periods. A default tick performs at most ten batches; persisted continuation resumes remaining work next tick. A failing subscription blocks only its later periods and is retried on a subsequent full scan. Starting again catches eligible historical periods even when a subscription is currently closed. Auto-close uses the frozen latest term policy only after owed periods are reconciled; an open pause prevents auto-close at the old expiry. Disabled auto-close leaves an Ended record without adding service periods.

The admin billing-runs page reads persisted runtime observations: last heartbeat, interval, last run, safe failure status and stale/stopped state. A historical worker observation does not prove a worker is currently running. Graceful termination reports STOPPED; force termination becomes stale after the heartbeat grace period. Check the process and database before restarting. For a deployed application, supervise the worker with the operating system/service manager and restart it on failure; no reboot-persistent Windows service was silently installed by development verification.

For bounded verification:

```powershell
backend/.venv/Scripts/python.exe scripts/run_scheduler.py --interval-seconds 10 --ticks 2
backend/.venv/Scripts/python.exe scripts/run_scheduler.py --once --subscription-id SUBSCRIPTION_UUID
backend/.venv/Scripts/python.exe scripts/run_billing.py --subscription-id SUBSCRIPTION_UUID --drain
```

The first command bills all eligible records in the configured database. Use the scoped command for a synthetic development case. Automated timer verification changes DATABASE_URL only inside a child process to the explicitly separate test database; it never redirects the live application.

## Recover failures

- Inspect A11's safe outcomes and subscription/invoice links. Continue remaining batches or retry failures through the existing controls. A failed or interrupted run is retained and linked to subsequent recovery.
- The next exclusive scheduler tick labels orphaned RUNNING runs INTERRUPTED and reconstructs committed counts. It never infers missing invoices from an uncommitted cursor.
- Invoice email attempts left PENDING for over 15 minutes become UNKNOWN. SMTP may have accepted the message before a process stopped. Review delivery history and Mailpit before an explicit resend; the worker never blindly resends uncertain email.
- Authentication windows are stored under hashed keys in PostgreSQL and serialized per key across workers. Limits count each attempt once and successful login does not erase the window. Expired windows and old pre-auth CSRF challenges are cleaned by the worker.
- Login/session creation serializes against password reset/deactivation. Reset revokes old sessions in the same transaction; changing a password retains only the current session. An already admitted HTTP operation may finish while another request revokes its session; subsequent authentication rejects it.

## Security and deployment boundary

Local HTTP uses non-Secure cookies on loopback; APP_ENV=production sets Secure cookies and API HSTS. A real deployment must terminate HTTPS, configure exact HTTPS FRONTEND_ORIGIN values and protected SMTP/database transport, retain private environments outside Git, and supervise API/frontend/worker. Do not expose Mailpit or native database ports publicly. Configure trusted proxy forwarding explicitly; application rate identifiers use the observed client address and never blindly trust an arbitrary X-Forwarded-For header.

Operational audit events are in PostgreSQL audit_events: authentication/credential changes, financial actions and automatic closure. Payloads exclude passwords and bearer/reset/CSRF tokens. Failed-login targets use a hash. Review repeated authentication failures, unknown email outcomes and failed/interrupted billing runs. No external alerting vendor or security certification is claimed.

See [SECURITY_VERIFICATION.md](SECURITY_VERIFICATION.md) for actual verification scope and remaining deployment checks.

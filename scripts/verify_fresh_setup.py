"""Verify migrations and initial API use in a new disposable PostgreSQL schema.

Uses TEST_DATABASE_URL only, refuses the development database and custom options,
and drops only its own randomly named schema. No credentials enter its report.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from browser_test_errors import install_redaction
install_redaction()

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.api.deps import get_current_db
from app.core.config import get_settings
from app.main import app
from app.models import Base
from bootstrap_admin import bootstrap_admin


def run():
    settings = get_settings()
    if not settings.TEST_DATABASE_URL:
        raise RuntimeError("An explicit disposable test database is required")
    url = make_url(settings.TEST_DATABASE_URL)
    assert url.database == "brightloop_test" and url.database != make_url(settings.DATABASE_URL).database
    assert url.host in {"localhost", "127.0.0.1"} and url.username == "brightloop_test" and not url.query
    schema = "brightloop_setup_" + uuid.uuid4().hex
    assert re.fullmatch(r"brightloop_setup_[a-f0-9]{32}", schema)
    source = create_engine(url)
    isolated = None
    report = {"timestamp": datetime.now(timezone.utc).isoformat(), "database": url.database, "schema": schema,
              "scope": "Empty schema, migration/model parity, initial authenticated API use; not a clean OS install"}
    with source.begin() as conn:
        assert conn.scalar(text("SELECT current_database()")) == "brightloop_test"
        before = {table: conn.scalar(text(f"SELECT count(*) FROM public.{table}"))
                  for table in ("users", "subscriptions", "invoices", "payments")}
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    try:
        isolated_url = url.update_query_dict({"options": f"-csearch_path={schema}"})
        cfg = Config(str(ROOT / "backend/alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", isolated_url.render_as_string(hide_password=False).replace("%", "%%"))
        command.upgrade(cfg, "head")
        isolated = create_engine(isolated_url)
        with isolated.connect() as conn:
            assert conn.scalar(text("SELECT current_schema()")) == schema
            head = conn.scalar(text("SELECT version_num FROM alembic_version"))
            assert head == ScriptDirectory.from_config(cfg).get_current_head()
            tables = set(inspect(conn).get_table_names())
            assert tables == set(Base.metadata.tables) | {"alembic_version"}
            assert all(conn.scalar(text(f"SELECT count(*) FROM {table}")) == 0 for table in Base.metadata.tables)
            report.update(head=head, empty_tables=len(Base.metadata.tables))
        command.check(cfg)
        report["migration_model_parity"] = "PASS"

        def session():
            with Session(isolated) as db:
                yield db

        app.dependency_overrides[get_current_db] = session
        with Session(isolated) as db:
            assert bootstrap_admin("fresh_admin@brightloop.test", "Fresh setup administrator", "Fresh@Secure123", db_session=db) == 0
        with TestClient(app) as client:
            origin = settings.FRONTEND_ORIGIN

            def post(path, payload):
                csrf = client.cookies.get("brightloop_csrf")
                if not csrf:
                    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
                response = client.post("/api/v1" + path, json=payload,
                    headers={"Origin": origin, "X-CSRF-Token": csrf})
                assert response.is_success, f"Initial setup API {path}: HTTP {response.status_code}"
                return response.json()

            assert client.get("/api/v1/health").status_code == 200
            assert client.get("/api/v1/ready").status_code == 200
            post("/auth/register", {"name": "Fresh customer", "email": "fresh_customer@brightloop.test", "password": "Fresh@Secure123"})
            post("/auth/login", {"email": "fresh_admin@brightloop.test", "password": "Fresh@Secure123"})
            post("/staff", {"name": "Fresh staff", "email": "fresh_staff@brightloop.test", "initial_password": "Fresh@Secure123"})
            post("/products", {"name": "Fresh product", "type": "ADDON", "sales_price": "200.00", "cost_price": "80.00"})
            post("/plans", {"name": "Fresh plan", "base_fee": "1000.00", "interval": "MONTHLY"})
            assert client.get("/api/v1/customers").json()["total"] == 1
            report["initial_api"] = "PASS: health/readiness, signup, bootstrap/login, staff, catalog, persisted customer"
        report["status"] = "PASS"
    finally:
        app.dependency_overrides.pop(get_current_db, None)
        if isolated is not None:
            isolated.dispose()
        with source.begin() as conn:
            assert conn.scalar(text("SELECT current_database()")) == "brightloop_test"
            assert conn.scalar(text("SELECT current_schema()")) == "public"
            after = {table: conn.scalar(text(f"SELECT count(*) FROM public.{table}")) for table in before}
            assert after == before, "Fresh setup changed pre-existing public records"
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
            assert conn.scalar(text("SELECT count(*) FROM pg_namespace WHERE nspname=:schema"), {"schema": schema}) == 0
        source.dispose()
    report["cleanup"] = "PASS; own schema removed, existing public record counts unchanged"
    output = ROOT / "test-results/fresh-setup.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    run()

"""Capture actual report/dashboard SQL timings and PostgreSQL execution plans."""
from datetime import date
from pathlib import Path
import argparse
import json
import sys
from time import perf_counter
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
load_dotenv(ROOT / "backend/.env.benchmark", override=True)
from sqlalchemy import event, select, text
from app.db.session import engine, SessionLocal
from app.models.users import User
from app.services.reporting import dashboard, report_details, summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="current")
    args = parser.parse_args()
    if not args.label.isalnum():
        parser.error("Use an alphanumeric report label.")
    observations, section = [], ""
    def before(connection, cursor, statement, parameters, context, many):
        context.brightloop_started = perf_counter()
    def after(connection, cursor, statement, parameters, context, many):
        observations.append({"section": section, "milliseconds": round((perf_counter() - context.brightloop_started) * 1000, 2),
            "statement": statement, "parameters": parameters})
    with SessionLocal() as db:
        assert db.scalar(text("SELECT current_schema()")) == "brightloop_benchmark", "Refusing to profile live records."
        actor = db.scalar(select(User).where(User.email_normalized == "benchmark_admin@brightloop.test"))
        event.listen(engine, "before_cursor_execute", before)
        event.listen(engine, "after_cursor_execute", after)
        try:
            for section in ("dashboard", "summary", "outstanding"):
                if section == "dashboard":
                    dashboard(db, actor)
                elif section == "summary":
                    summary(db, actor, date(2000, 1, 1), date(2099, 1, 1))
                else:
                    report_details(db, actor, "outstanding")
        finally:
            event.remove(engine, "before_cursor_execute", before)
            event.remove(engine, "after_cursor_execute", after)
        for item in sorted(observations, key=lambda item: item["milliseconds"], reverse=True)[:8]:
            item["explain"] = db.connection().exec_driver_sql("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + item["statement"], item["parameters"]).scalar()
        report = {"database_version": db.scalar(text("SELECT version()")), "queries": observations}
        output = ROOT / f"test-results/query-profile-{args.label}.json"
        output.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        for item in observations:
            print(f"{item['section']}: {item['milliseconds']} ms")
        print(f"Profile and plans: {output}")


if __name__ == "__main__":
    main()

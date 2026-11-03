from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import threading
import uuid

from fastapi import HTTPException
import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from conftest import test_engine
from app.core.security import hash_token
from app.models.rate_limits import RateLimitWindow
from app.models.audit import AuditEvent
from app.models.users import AuthChallenge, Session as UserSession, User
from app.services.auth import check_rate_limit, create_user_session, reset_password
from app.services.calendar import boundary
from test_billing_concurrency import committed_case


def test_parallel_rate_limit_is_shared_and_exact_across_postgresql_connections():
    identifier = uuid.uuid4().hex
    def attempt(_):
        with Session(test_engine) as db:
            try:
                check_rate_limit("parallel_probe", identifier, 10, 300, db)
                return 200
            except HTTPException as exc:
                assert exc.status_code == 429
                assert int(exc.headers["Retry-After"]) > 0
                return 429
    try:
        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(attempt, range(40)))
        assert results.count(200) == 10
        assert results.count(429) == 30
    finally:
        with Session(test_engine) as db:
            db.execute(delete(RateLimitWindow).where(RateLimitWindow.key_hash == hash_token(f"parallel_probe:{identifier}")))
            db.commit()


def test_password_reset_racing_session_creation_revokes_or_rejects_every_old_credential():
    with committed_case(0) as ids:
        raw_reset = uuid.uuid4().hex
        barrier = threading.Barrier(9)
        with Session(test_engine) as db:
            actor = db.get(User, ids["actor"])
            verified_hash = actor.password_hash
            db.add(AuthChallenge(purpose="RESET", token_hash=hash_token(raw_reset), user_id=actor.id,
                email_normalized=actor.email_normalized, expires_at=datetime.now(timezone.utc) + timedelta(minutes=5)))
            db.commit()
        def login(_):
            with Session(test_engine) as db:
                actor = db.get(User, ids["actor"])
                barrier.wait(timeout=10)
                try:
                    session, _, _ = create_user_session(db, actor, expected_password_hash=verified_hash)
                    return session.id
                except HTTPException as exc:
                    assert exc.status_code == 401
                    return None
        def reset():
            with Session(test_engine) as db:
                barrier.wait(timeout=10)
                reset_password(db, raw_reset, "Reset@Racing123")
        try:
            with ThreadPoolExecutor(max_workers=9) as pool:
                logins = [pool.submit(login, index) for index in range(8)]
                reset_future = pool.submit(reset)
                issued = [future.result(timeout=20) for future in logins]
                reset_future.result(timeout=20)
            with Session(test_engine) as db:
                sessions = list(db.scalars(select(UserSession).where(UserSession.user_id == ids["actor"])))
                assert all(session.revoked_at is not None for session in sessions)
                assert len(sessions) == sum(item is not None for item in issued)
                actor = db.get(User, ids["actor"])
                with pytest.raises(HTTPException) as denied:
                    create_user_session(db, actor, expected_password_hash=verified_hash)
                assert denied.value.status_code == 401
        finally:
            with Session(test_engine) as db:
                db.execute(delete(AuthChallenge).where(AuthChallenge.user_id == ids["actor"]))
                db.execute(delete(UserSession).where(UserSession.user_id == ids["actor"]))
                db.commit()


def test_expired_session_csrf_binding_and_security_headers(db, client, admin_auth):
    actor = admin_auth["user"]
    first, raw, csrf = create_user_session(db, actor)
    _, _, foreign_csrf = create_user_session(db, actor)
    audit = list(db.scalars(select(AuditEvent).where(AuditEvent.actor_id == actor.id)))
    assert any(event.action == "AUTH_LOGIN" for event in audit)
    persisted = str([(event.action, event.target_id, event.payload) for event in audit])
    assert all(secret not in persisted for secret in (raw, csrf, foreign_csrf, actor.password_hash))
    client.cookies.set("brightloop_session", raw)
    client.cookies.set("brightloop_csrf", csrf)
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": foreign_csrf}).status_code == 403
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    for key, value in {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
                       "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY"}.items():
        assert response.headers[key] == value
    first.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 401


def test_business_calendar_dst_and_month_end_use_dates_not_elapsed_hours(db):
    from datetime import date
    assert [boundary(date(2024, 1, 31), "MONTHLY", n) for n in range(4)] == [
        date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 31), date(2024, 4, 30)]
    assert boundary(date(2024, 2, 29), "YEARLY", 4) == date(2028, 2, 29)
    # India has no DST; transitions elsewhere do not alter local date periods.
    assert boundary(date(2026, 3, 7), "DAILY", 2) == date(2026, 3, 9)
    assert boundary(date(2026, 10, 31), "WEEKLY", 1) == date(2026, 11, 7)
    assert db.scalar(text("SHOW transaction_isolation")) == "read committed"

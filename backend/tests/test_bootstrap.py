from sqlalchemy import select
from app.core.security import verify_password
from app.models.users import User
from scripts.bootstrap_admin import bootstrap_admin


def test_controlled_admin_bootstrap(db):
    # Ensure no admin exists for this test email
    email = "bootstrap_tester@brightloop.test"
    existing = db.scalar(select(User).where(User.email_normalized == email))
    if existing:
        db.delete(existing)
        db.commit()

    # 1. Invalid password rejected
    ret_invalid = bootstrap_admin(email, "Bootstrap Admin", "weak_pwd", db_session=db)
    assert ret_invalid == 1

    # 2. First bootstrap succeeds
    ret_success = bootstrap_admin(email, "Bootstrap Admin", "Valid@Admin123", force=True, db_session=db)
    assert ret_success == 0

    user = db.scalar(select(User).where(User.email_normalized == email))
    assert user is not None
    assert user.role == "ADMIN"
    assert verify_password("Valid@Admin123", user.password_hash)

    # 3. Repeated bootstrap without force should fail if admin exists
    ret_dup = bootstrap_admin("another_admin@brightloop.test", "Another Admin", "Valid@Admin123", force=False, db_session=db)
    assert ret_dup == 1

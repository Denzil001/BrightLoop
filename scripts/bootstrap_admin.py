"""Controlled first-admin bootstrap CLI for Brightloop."""

import argparse
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.core.security import (
    hash_password,
    normalize_email,
    validate_password_complexity,
)
from app.db.session import SessionLocal
from app.models.users import User


def bootstrap_admin(email: str, name: str, password: str, force: bool = False, db_session=None) -> int:
    email_norm = normalize_email(email)

    valid, err = validate_password_complexity(password)
    if not valid:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    db = db_session or SessionLocal()
    should_close = db_session is None
    try:
        # Check if an admin already exists
        existing_admins = db.scalars(select(User).where(User.role == "ADMIN")).all()
        if existing_admins and not force:
            print(
                f"Error: An administrator account already exists ({len(existing_admins)} found). "
                "Use --force if you specifically intend to create an additional administrator.",
                file=sys.stderr,
            )
            return 1

        # Check if user with this email already exists
        user = db.scalar(select(User).where(User.email_normalized == email_norm))
        if user:
            if not force:
                print(
                    f"Error: A user with email {email_norm} already exists with role '{user.role}'. "
                    "Use --force to update this user to an administrator.",
                    file=sys.stderr,
                )
                return 1
            user.name = name
            user.password_hash = hash_password(password)
            user.role = "ADMIN"
            user.active = True
            user.version += 1
            db.commit()
            print(f"Successfully updated user {email_norm} as active administrator.")
            return 0

        # Create new admin user
        new_admin = User(
            email_normalized=email_norm,
            name=name,
            password_hash=hash_password(password),
            role="ADMIN",
            active=True,
        )
        db.add(new_admin)
        db.commit()
        print(f"Successfully bootstrapped first administrator: {email_norm} ({name})")
        return 0
    finally:
        if should_close:
            db.close()


def main():
    parser = argparse.ArgumentParser(description="Bootstrap Brightloop administrator account.")
    parser.add_argument("--email", required=True, help="Administrator email address")
    parser.add_argument("--name", default="System Administrator", help="Administrator full name")
    parser.add_argument("--password", required=True, help="Password (min 9 chars, upper, lower, special)")
    parser.add_argument("--force", action="store_true", help="Force creation even if admin exists")

    args = parser.parse_args()
    return bootstrap_admin(args.email, args.name, args.password, args.force)


if __name__ == "__main__":
    sys.exit(main())

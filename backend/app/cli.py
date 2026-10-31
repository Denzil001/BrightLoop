"""Brightloop CLI commands."""

import argparse
import sys
from app.core.security import (
    hash_password,
    normalize_email,
    validate_password_complexity,
)
from app.db.session import SessionLocal
from app.models.users import User
from sqlalchemy import select


def bootstrap_admin_cmd(email: str, name: str, password: str, force: bool = False) -> int:
    email_norm = normalize_email(email)
    valid, err = validate_password_complexity(password)
    if not valid:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        existing_admins = db.scalars(select(User).where(User.role == "ADMIN")).all()
        if existing_admins and not force:
            print(
                f"Error: An administrator account already exists ({len(existing_admins)} found). "
                "Use --force to create an additional administrator.",
                file=sys.stderr,
            )
            return 1

        user = db.scalar(select(User).where(User.email_normalized == email_norm))
        if user:
            if not force:
                print(
                    f"Error: User {email_norm} already exists with role '{user.role}'. Use --force.",
                    file=sys.stderr,
                )
                return 1
            user.name = name
            user.password_hash = hash_password(password)
            user.role = "ADMIN"
            user.active = True
            user.version += 1
            db.commit()
            print(f"Updated user {email_norm} to administrator.")
            return 0

        new_admin = User(
            email_normalized=email_norm,
            name=name,
            password_hash=hash_password(password),
            role="ADMIN",
            active=True,
        )
        db.add(new_admin)
        db.commit()
        print(f"Bootstrapped administrator: {email_norm}")
        return 0
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(prog="brightloop-cli")
    subparsers = parser.add_subparsers(dest="command")

    admin_parser = subparsers.add_parser("bootstrap-admin", help="Bootstrap initial administrator")
    admin_parser.add_argument("--email", required=True, help="Admin email")
    admin_parser.add_argument("--name", default="System Administrator", help="Admin name")
    admin_parser.add_argument("--password", required=True, help="Admin password")
    admin_parser.add_argument("--force", action="store_true", help="Force bootstrap")

    args = parser.parse_args()
    if args.command == "bootstrap-admin":
        return bootstrap_admin_cmd(args.email, args.name, args.password, args.force)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

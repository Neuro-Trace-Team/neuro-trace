import argparse
import getpass
import sys

from sqlalchemy import select

from src.core.security import hash_password
from src.db.sessions import AuthSession
from src.models.auth import User


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create the first NeuroTrace administrator.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--first-name", required=True)
    parser.add_argument("--last-name", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    password = getpass.getpass("Administrator password: ")
    if len(password) < 12:
        print("Password must contain at least 12 characters.", file=sys.stderr)
        return 2

    with AuthSession() as session:
        if session.scalar(select(User.id).limit(1)) is not None:
            print("An auth_db user already exists; bootstrap is intentionally refused.", file=sys.stderr)
            return 1
        session.add(
            User(
                email=args.email.strip().lower(),
                password_hash=hash_password(password),
                first_name=args.first_name.strip(),
                last_name=args.last_name.strip(),
                role="ADMIN",
                is_active=True,
            )
        )
        session.commit()
    print("Initial administrator created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

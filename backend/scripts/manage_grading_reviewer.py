"""Server-only reviewer provisioning; signup cannot grant reviewer privileges."""
import argparse
import asyncio
from sqlalchemy import select
from app.db.session import async_session_factory
from app.models.user import User


async def provision(email: str, grant: bool) -> bool:
    async with async_session_factory() as db:
        user = (await db.execute(select(User).where(User.email == email.strip().lower())
                                 .with_for_update())).scalar_one_or_none()
        if user is None:
            return False
        user.role = "interviewer" if grant else "candidate"
        from app.services.interview.analytics import track_event
        await track_event(db, event_name="grading_reviewer_role_changed", user_id=user.id,
                          properties={"role": user.role, "source": "server_operator_cli"})
        await db.commit()
        return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email", help="Existing account to grant or revoke")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--grant", action="store_true")
    action.add_argument("--revoke", action="store_true")
    args = parser.parse_args()
    if not asyncio.run(provision(args.email, args.grant)):
        parser.exit(1, "Account not found. Create the account before provisioning.\n")
    print("Reviewer role updated and audited.")


if __name__ == "__main__":
    main()

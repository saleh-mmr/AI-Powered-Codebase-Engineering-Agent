from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session, User


class AuthRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def find_user(self, email: str) -> User | None:
        return (await self.db.scalars(select(User).where(User.email == email))).one_or_none()

    async def find_session(self, digest: str) -> tuple[User, Session] | None:
        row = (
            await self.db.execute(
                select(User, Session)
                .join(Session, Session.user_id == User.id)
                .where(
                    Session.token_hash == digest,
                    Session.expires_at > datetime.now(UTC),
                )
            )
        ).first()
        return (row[0], row[1]) if row else None

    async def delete_session(self, digest: str) -> None:
        await self.db.execute(delete(Session).where(Session.token_hash == digest))

    async def delete_expired_sessions(self) -> None:
        await self.db.execute(delete(Session).where(Session.expires_at <= datetime.now(UTC)))

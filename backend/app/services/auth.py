from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password, needs_rehash, verify_password
from app.auth.tokens import new_token, token_hash, valid_token
from app.core.errors import AppError
from app.models import Session, User
from app.repositories.auth import AuthRepository
from app.schemas.auth import LoginRequest, RegisterRequest


@dataclass(frozen=True)
class Identity:
    user: User
    session: Session
    token: str = field(repr=False)


class AuthService:
    def __init__(self, db: AsyncSession, lifetime_hours: int, dummy_hash: str) -> None:
        self.db = db
        self.repo = AuthRepository(db)
        self.lifetime_hours = lifetime_hours
        self.dummy_hash = dummy_hash

    async def register(self, data: RegisterRequest, previous_token: str | None) -> Identity:
        user = User(
            email=str(data.email),
            name=data.name,
            password_hash=await hash_password(data.password.get_secret_value()),
        )
        self.db.add(user)
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            if await self.repo.find_user(str(data.email)) is not None:
                raise AppError(
                    "account_unavailable", "Unable to create an account with this email.", 409
                ) from None
            raise
        identity = await self._new_session(user, previous_token)
        await self.db.commit()
        return identity

    async def login(self, data: LoginRequest, previous_token: str | None) -> Identity:
        user = await self.repo.find_user(str(data.email))
        stored_hash = user.password_hash if user else self.dummy_hash
        verified = await verify_password(stored_hash, data.password.get_secret_value())
        if user is None or not verified:
            raise AppError("invalid_credentials", "Email or password is incorrect.", 401)
        if needs_rehash(user.password_hash):
            user.password_hash = await hash_password(data.password.get_secret_value())
        identity = await self._new_session(user, previous_token)
        await self.db.commit()
        return identity

    async def _new_session(self, user: User, previous_token: str | None) -> Identity:
        if valid_token(previous_token) and previous_token is not None:
            await self.repo.delete_session(token_hash(previous_token))
        await self.repo.delete_expired_sessions()
        raw = new_token()
        session = Session(
            token_hash=token_hash(raw),
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(hours=self.lifetime_hours),
        )
        self.db.add(session)
        return Identity(user=user, session=session, token=raw)

    async def authenticate(self, raw: str | None) -> Identity:
        if not valid_token(raw) or raw is None:
            raise AppError("unauthenticated", "Please sign in to continue.", 401)
        result = await self.repo.find_session(token_hash(raw))
        if result is None:
            raise AppError("unauthenticated", "Please sign in to continue.", 401)
        return Identity(user=result[0], session=result[1], token=raw)

    async def logout(self, identity: Identity) -> None:
        await self.repo.delete_session(token_hash(identity.token))
        await self.db.commit()

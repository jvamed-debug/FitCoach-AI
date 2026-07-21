import asyncio
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.admin import AdminUser
from app.models.athlete import Athlete
from app.models.lgpd import LGPDConsent

# ── In-memory SQLite for tests ────────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Fixture: admin user ───────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> AdminUser:
    admin = AdminUser(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Dr. Test Admin",
        email="admin@test.com",
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


# ── Fixture: athlete user ─────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def athlete_user(db_session: AsyncSession, admin_user: AdminUser) -> Athlete:
    athlete = Athlete(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        admin_id=admin_user.id,
        name="Test Athlete",
        email="athlete@test.com",
        is_active=True,
        onboarding_complete=False,
    )
    db_session.add(athlete)
    await db_session.commit()
    await db_session.refresh(athlete)
    return athlete


# ── Fixture: athlete with LGPD consent ───────────────────────────────────────
@pytest_asyncio.fixture
async def athlete_with_consent(db_session: AsyncSession, athlete_user: Athlete) -> Athlete:
    from datetime import datetime, timezone
    consent = LGPDConsent(
        athlete_id=athlete_user.id,
        consent_version="1.0",
        consented_at=datetime.now(timezone.utc),
        ip_address="127.0.0.1",
    )
    db_session.add(consent)
    athlete_user.onboarding_complete = True
    db_session.add(athlete_user)
    await db_session.commit()
    return athlete_user


# ── JWT token helpers ─────────────────────────────────────────────────────────
def make_jwt(user_id: str, secret: str = None) -> str:
    from jose import jwt as jose_jwt
    from datetime import datetime, timezone, timedelta
    from app.config import settings

    payload = {
        "sub": user_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "role": "authenticated",
    }
    return jose_jwt.encode(payload, secret or settings.supabase_jwt_secret, algorithm="HS256")

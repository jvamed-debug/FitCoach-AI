from sqlalchemy import ARRAY, JSON, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


# JSONB no PostgreSQL (produção) e JSON no SQLite (testes). O compilador do
# SQLite não sabe renderizar JSONB, o que quebrava a criação das tabelas na
# suíte. A representação em produção permanece JSONB — nada muda no schema.
JSONVariant = JSON().with_variant(JSONB(), "postgresql")

# ARRAY(String) no PostgreSQL e JSON no SQLite — o SQLite não tem tipo array.
# Em ambos os casos o valor em Python continua sendo uma lista de strings.
StringArrayVariant = ARRAY(String()).with_variant(JSON(), "sqlite")


# SQLite (usado nos testes) usa StaticPool e rejeita pool_size/max_overflow —
# esses ajustes de pool só valem para backends servidos, como o PostgreSQL.
_engine_kwargs: dict = {"echo": settings.app_env == "development"}
if not settings.database_url.startswith("sqlite"):
    _engine_kwargs.update(pool_size=10, max_overflow=20, pool_pre_ping=True)

engine = create_async_engine(settings.database_url, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

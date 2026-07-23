import uuid as _uuid

from sqlalchemy import ARRAY, JSON, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator
from app.config import settings


class GUID(TypeDecorator):
    """
    UUID portátil: tipo UUID nativo no PostgreSQL, CHAR(32) no SQLite.

    Aceita tanto `uuid.UUID` quanto `str` no bind. Várias camadas do app passam
    `str(athlete.id)`; o driver do PostgreSQL coage a string automaticamente,
    mas o SQLite não — o que fazia esses caminhos falharem só nos testes.
    """

    impl = Uuid(as_uuid=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None or isinstance(value, _uuid.UUID):
            return value
        return _uuid.UUID(str(value))


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

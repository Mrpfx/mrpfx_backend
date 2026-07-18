from sqlalchemy.ext.asyncio.engine import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import SQLModel

from app.core.config import settings


# SQLite doesn't support pool_size, so we handle it conditionally
if settings.USE_SQLITE:
    engine = create_async_engine(
        url=settings.DATABASE_URL,
        echo=settings.DEBUG,
        future=True,
        # SQLite needs this for proper async support
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_async_engine(
        url=settings.DATABASE_URL,
        max_overflow=10,
        future=True,
        pool_size=20,
        pool_pre_ping=False,  # Disabled due to aiomysql signature mismatch
        pool_recycle=1800,    # Added recycle to compensate for disabled pre_ping
        echo=settings.DEBUG,
    )


# WordPress MySQL engine (connects to the WP database)
wp_engine = create_async_engine(
    url=settings.WP_DATABASE_URL,
    max_overflow=10,
    future=True,
    pool_size=10,
    pool_pre_ping=False,      # Disabled due to aiomysql signature mismatch
    pool_recycle=1800,
    echo=settings.DEBUG,
)


async def get_session() -> AsyncSession:
    """
    An asynchronous session factory for the main app database.
    """
    async with AsyncSession(engine) as session:
        yield session


async def get_wp_session() -> AsyncSession:
    """
    An asynchronous session factory for the WordPress MySQL database.
    """
    async with AsyncSession(wp_engine) as session:
        yield session


async def ini_db():
    """
    Initialize all database tables.
    """
    # Import models here to avoid circular imports and ensure registration
    import app.model.wordpress
    import app.model.crypto_payment
    import app.model.services
    import app.model.traders
    import app.model.user

    # 1. Main database
    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
    except Exception:
        pass # Handle errors gracefully if one DB fails

    # 2. WordPress database
    async with wp_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.config.logging import get_logger
from app.config.settings import Settings, get_settings

db_logger = get_logger("database")


def build_engine(settings: Settings | None = None):
    runtime_settings = settings or get_settings()
    connect_args = {"check_same_thread": False} if runtime_settings.database_url.startswith("sqlite") else {}
    return create_engine(runtime_settings.database_url, connect_args=connect_args, future=True, hide_parameters=True)


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    try:
        db = SessionLocal()
    except Exception:
        db_logger.error("Database session creation failed", exc_info=True)
        raise
    try:
        yield db
    finally:
        try:
            db.close()
        except Exception:
            db_logger.error("Database session close failed", exc_info=True)


def session_scope() -> Session:
    """Return a regular session for startup tasks that are not request-scoped."""
    return SessionLocal()


def init_db() -> None:
    from app.models import Base

    try:
        Base.metadata.create_all(bind=engine)
        _apply_lightweight_dev_migrations()
        db_logger.info("Database initialized url_scheme=%s", engine.url.drivername)
    except Exception:
        db_logger.critical("Database initialization failed", exc_info=True)
        raise


def _apply_lightweight_dev_migrations() -> None:
    """Apply small additive SQLite changes without introducing a migration service."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if "admin_users" in tables and "auth_version" not in {column["name"] for column in inspector.get_columns("admin_users")}:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE admin_users ADD COLUMN auth_version INTEGER NOT NULL DEFAULT 1"))
        db_logger.info("Admin session version migration completed")
    if "emails" in tables:
        columns = {column["name"] for column in inspector.get_columns("emails")}
        if "message_date" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE emails ADD COLUMN message_date DATETIME"))

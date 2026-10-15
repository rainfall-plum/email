from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class ImportUsername(TimestampMixin, Base):
    """Usernames waiting in the import pool for a later batch generation."""

    __tablename__ = "import_usernames"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

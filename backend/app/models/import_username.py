from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class ImportUsername(TimestampMixin, Base):
    """Complete imported usernames; deliberately separate from first/last names."""

    __tablename__ = "import_usernames"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

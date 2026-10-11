from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.admin_user import AdminUser


class MailGenerationRecord(Base):
    __tablename__ = "mail_generation_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_user_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    requested_count: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="batch", nullable=False)
    admin_user: Mapped["AdminUser | None"] = relationship(back_populates="generation_records")

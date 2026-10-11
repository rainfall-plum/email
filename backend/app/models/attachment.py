from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.email import Email


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id", ondelete="CASCADE"), index=True, nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255))
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    email: Mapped["Email"] = relationship(back_populates="attachments")

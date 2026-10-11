from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.attachment import Attachment
    from app.models.mailbox import Mailbox


class Email(Base):
    __tablename__ = "emails"
    __table_args__ = (Index("ix_emails_mailbox_received_at", "mailbox_id", "received_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    mailbox_id: Mapped[int] = mapped_column(ForeignKey("mailboxes.id", ondelete="CASCADE"), index=True, nullable=False)
    sender: Mapped[str] = mapped_column(String(254), nullable=False)
    receiver: Mapped[str] = mapped_column(String(254), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(998))
    body_text: Mapped[str | None] = mapped_column(Text)
    body_html: Mapped[str | None] = mapped_column(Text)
    verification_code: Mapped[str | None] = mapped_column(String(8))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    eml_path: Mapped[str | None] = mapped_column(String(1024))
    message_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    mailbox: Mapped["Mailbox"] = relationship(back_populates="emails")
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="email", cascade="all, delete-orphan", passive_deletes=True
    )

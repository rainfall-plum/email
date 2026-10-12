from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class OutboundEmail(TimestampMixin, Base):
    __tablename__ = "outbound_emails"
    __table_args__ = (
        CheckConstraint("status IN ('queued','sending','sent','retrying','failed')"),
        CheckConstraint("attempt_count >= 0 AND attempt_count <= max_attempts AND max_attempts = 5"),
        Index("ix_outbound_due", "status", "next_attempt_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Keep history after mailbox deletion; validate the ID and snapshot again before sending.
    sender_mailbox_id: Mapped[int] = mapped_column(nullable=False)
    sender: Mapped[str] = mapped_column(String(254))
    recipient: Mapped[str] = mapped_column(String(254))
    subject: Mapped[str] = mapped_column(String(200))
    body_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    attempt_count: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=5)
    last_error: Mapped[str | None] = mapped_column(String(256))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime)
    message_id: Mapped[str] = mapped_column(String(254), unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(36), unique=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime)

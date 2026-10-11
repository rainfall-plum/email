from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.email import Email
    from app.models.tag import Tag


mailbox_tags = Table(
    "mailbox_tags",
    Base.metadata,
    Column("mailbox_id", ForeignKey("mailboxes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Mailbox(TimestampMixin, Base):
    __tablename__ = "mailboxes"

    id: Mapped[int] = mapped_column(primary_key=True)
    email_address: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    local_part: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)

    emails: Mapped[list["Email"]] = relationship(
        back_populates="mailbox", cascade="all, delete-orphan", passive_deletes=True
    )
    tags: Mapped[list["Tag"]] = relationship(secondary=mailbox_tags, back_populates="mailboxes")

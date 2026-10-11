from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.mailbox import mailbox_tags

if TYPE_CHECKING:
    from app.models.mailbox import Mailbox


class Tag(TimestampMixin, Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    mailboxes: Mapped[list["Mailbox"]] = relationship(secondary=mailbox_tags, back_populates="tags")

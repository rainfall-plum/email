from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from email_validator import validate_email, EmailNotValidError
from pydantic import BaseModel, ConfigDict, Field, field_validator

OutboundStatus = Literal["queued", "sending", "sent", "retrying", "failed"]


class OutboundCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sender_mailbox_id: int = Field(gt=0)
    recipient: str = Field(min_length=3, max_length=254)
    subject: str = Field(min_length=1, max_length=200)
    body_text: str = Field(min_length=1, max_length=100000)
    idempotency_key: UUID

    @field_validator("recipient")
    @classmethod
    def recipient_valid(cls, value: str) -> str:
        try:
            return validate_email(value, check_deliverability=False, allow_smtputf8=False).normalized
        except EmailNotValidError:
            raise ValueError("请输入单个有效收件邮箱") from None

    @field_validator("subject", "body_text")
    @classmethod
    def text_valid(cls, value: str, info):
        if not value.strip() or any(ord(c) < 32 and c not in "\n\r\t" for c in value):
            raise ValueError("文本不能为空或包含控制字符")
        if info.field_name == "subject" and any(c in value for c in "\r\n\t"):
            raise ValueError("主题不能包含换行")
        # Markup characters are literal text, never interpreted as HTML.
        return value


class OutboundSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sender_mailbox_id: int
    sender: str
    recipient: str
    subject: str
    status: OutboundStatus
    attempt_count: int
    max_attempts: int
    last_error: str | None
    next_attempt_at: datetime | None
    message_id: str
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None
    failed_at: datetime | None

    @field_validator("next_attempt_at", "created_at", "updated_at", "sent_at", "failed_at", mode="after")
    @classmethod
    def utc_dates(cls, value):
        return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


class OutboundDetail(OutboundSummary):
    body_text: str


class OutboundPage(BaseModel):
    items: list[OutboundSummary]
    total: int
    page: int
    page_size: int
    pages: int

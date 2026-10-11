from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_name: str
    stored_name: str
    mime_type: str | None
    file_size: int


class EmailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mailbox_id: int
    sender: str
    receiver: str
    subject: str | None
    body_text: str | None
    body_html: str | None
    verification_code: str | None
    is_read: bool
    message_date: datetime | None
    received_at: datetime
    attachments: list[AttachmentResponse] = Field(default_factory=list)

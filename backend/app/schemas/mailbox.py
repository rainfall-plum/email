from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MailboxCreateRequest(BaseModel):
    local_part: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9]+$")
    display_name: str | None = Field(default=None, max_length=128)
    expires_at: datetime | None = None
    tag_ids: list[int] = Field(default_factory=list)


class MailboxUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=128)
    enabled: bool | None = None
    expires_at: datetime | None = None
    tag_ids: list[int] | None = None


class MailboxResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email_address: str
    local_part: str
    display_name: str | None
    enabled: bool
    expires_at: datetime | None
    created_source: str
    tag_ids: list[int] = Field(default_factory=list)
    email_count: int = 0
    unread_count: int = 0
    latest_email_at: datetime | None = None


class MailboxPageResponse(BaseModel):
    items: list[MailboxResponse]
    total: int
    page: int
    page_size: int
    pages: int


class BatchMailboxCreateRequest(BaseModel):
    count: int = Field(ge=1, le=1000)
    tag_ids: list[int] = Field(default_factory=list)


class BatchMailboxCreateResponse(BaseModel):
    requested_count: int
    generated_count: int
    mailboxes: list[MailboxResponse]


class TagCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class TagUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class TagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str

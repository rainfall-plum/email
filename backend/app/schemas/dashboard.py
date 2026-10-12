from pydantic import BaseModel


class DashboardStatsResponse(BaseModel):
    mailbox_count: int
    email_count: int
    unread_email_count: int
    tag_count: int

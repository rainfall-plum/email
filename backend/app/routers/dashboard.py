from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models import AdminUser, Email, Mailbox, Tag
from app.routers.auth import get_current_admin
from app.schemas.dashboard import DashboardStatsResponse

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats(
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> DashboardStatsResponse:
    return DashboardStatsResponse(
        mailbox_count=db.scalar(select(func.count(Mailbox.id))) or 0,
        email_count=db.scalar(select(func.count(Email.id))) or 0,
        unread_email_count=db.scalar(
            select(func.count(Email.id)).where(Email.is_read.is_(False))
        ) or 0,
        tag_count=db.scalar(select(func.count(Tag.id))) or 0,
    )

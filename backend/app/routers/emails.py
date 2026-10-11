from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.database.session import get_db
from app.models import AdminUser, Attachment, Email, Mailbox
from app.routers.auth import get_current_admin
from app.schemas.email import EmailResponse

router = APIRouter(prefix="/api", tags=["emails"])
email_logger = get_logger("email_api")


@router.get("/mailboxes/{mailbox_id}/emails", response_model=list[EmailResponse])
def list_mailbox_emails(
    mailbox_id: int,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> list[EmailResponse]:
    if db.get(Mailbox, mailbox_id) is None:
        raise HTTPException(status_code=404, detail="邮箱不存在")
    emails = db.scalars(
        select(Email)
        .options(selectinload(Email.attachments))
        .where(Email.mailbox_id == mailbox_id)
        .order_by(Email.received_at.desc(), Email.id.desc())
    )
    return list(emails)


@router.get("/emails/{email_id}", response_model=EmailResponse)
def get_email(
    email_id: int,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> EmailResponse:
    email = db.scalar(select(Email).options(selectinload(Email.attachments)).where(Email.id == email_id))
    if email is None:
        raise HTTPException(status_code=404, detail="邮件不存在")
    if not email.is_read:
        email.is_read = True
        db.commit()
        email_logger.info("Email marked read id=%s", email_id)
    return email


@router.get("/attachments/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    attachment = db.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="附件不存在")
    file_path = Path(attachment.file_path)
    if not file_path.is_file():
        email_logger.error("Attachment file missing id=%s path=%s", attachment_id, file_path)
        raise HTTPException(status_code=404, detail="附件文件不存在")
    return FileResponse(
        path=file_path,
        media_type=attachment.mime_type or "application/octet-stream",
        filename=attachment.original_name,
    )

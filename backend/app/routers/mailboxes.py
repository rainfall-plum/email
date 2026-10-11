from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.config.settings import get_settings
from app.database.session import get_db
from app.models import AdminUser
from app.routers.auth import get_current_admin
from app.schemas.mailbox import (
    BatchMailboxCreateRequest,
    BatchMailboxCreateResponse,
    MailboxCreateRequest,
    MailboxResponse,
    MailboxUpdateRequest,
)
from app.services.mailbox_service import (
    MailboxServiceError,
    create_mailbox,
    delete_mailbox,
    generate_mailboxes,
    get_mailbox,
    list_mailboxes,
    update_mailbox,
)
from app.utils.name_library import NameLibraryError

router = APIRouter(prefix="/api/mailboxes", tags=["mailboxes"])
route_logger = get_logger("mailbox_api")


def _response(mailbox) -> MailboxResponse:
    return MailboxResponse(
        id=mailbox.id,
        email_address=mailbox.email_address,
        local_part=mailbox.local_part,
        display_name=mailbox.display_name,
        enabled=mailbox.enabled,
        expires_at=mailbox.expires_at,
        created_source=mailbox.created_source,
        tag_ids=[tag.id for tag in mailbox.tags],
    )


@router.get("", response_model=list[MailboxResponse])
def get_mailboxes(
    _: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)
) -> list[MailboxResponse]:
    return [_response(mailbox) for mailbox in list_mailboxes(db)]


@router.post("", response_model=MailboxResponse, status_code=status.HTTP_201_CREATED)
def post_mailbox(
    payload: MailboxCreateRequest,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> MailboxResponse:
    try:
        mailbox = create_mailbox(
            db,
            get_settings(),
            payload.local_part,
            payload.display_name,
            payload.expires_at,
            payload.tag_ids,
        )
        return _response(mailbox)
    except MailboxServiceError as exc:
        raise HTTPException(status_code=409 if "存在" in str(exc) else 400, detail=str(exc)) from None


@router.post("/batch", response_model=BatchMailboxCreateResponse, status_code=status.HTTP_201_CREATED)
def post_batch_mailboxes(
    payload: BatchMailboxCreateRequest,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> BatchMailboxCreateResponse:
    try:
        mailboxes = generate_mailboxes(db, get_settings(), payload.count, payload.tag_ids)
    except NameLibraryError as exc:
        route_logger.warning("Batch generation rejected reason=%s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except MailboxServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return BatchMailboxCreateResponse(
        requested_count=payload.count,
        generated_count=len(mailboxes),
        mailboxes=[_response(mailbox) for mailbox in mailboxes],
    )


@router.put("/{mailbox_id}", response_model=MailboxResponse)
def put_mailbox(
    mailbox_id: int,
    payload: MailboxUpdateRequest,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> MailboxResponse:
    try:
        mailbox = get_mailbox(db, mailbox_id)
        return _response(update_mailbox(db, mailbox, payload.model_dump(exclude_unset=True)))
    except MailboxServiceError as exc:
        raise HTTPException(status_code=404 if "不存在" in str(exc) else 400, detail=str(exc)) from None


@router.delete("/{mailbox_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_mailbox(
    mailbox_id: int,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_mailbox(db, get_mailbox(db, mailbox_id))
    except MailboxServiceError as exc:
        raise HTTPException(status_code=404 if "不存在" in str(exc) else 400, detail=str(exc)) from None

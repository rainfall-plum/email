import math

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
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
    MailboxPageResponse,
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
from app.services.username_import_service import MAX_IMPORT_BYTES, UsernameImportError, import_usernames, parse_username_file

router = APIRouter(prefix="/api/mailboxes", tags=["mailboxes"])
route_logger = get_logger("mailbox_api")


@router.post("/import-usernames")
async def post_import_usernames(
    file: UploadFile = File(...),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    try:
        content = await file.read(MAX_IMPORT_BYTES + 1)
        usernames = parse_username_file(file.filename, content)
        return import_usernames(db, get_settings(), usernames, admin.id)
    except UsernameImportError as exc:
        route_logger.error("Username upload rejected actor_id=%s code=%s", admin.id, exc.code)
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}) from None
    except Exception as exc:
        db.rollback()
        route_logger.error("Username upload failed actor_id=%s type=%s", admin.id, type(exc).__name__)
        raise HTTPException(status_code=500, detail={"code": "import_failed", "message": "文件上传失败，请稍后重试"}) from None
    finally:
        await file.close()


def _response(mailbox, metrics: tuple[int, int, object | None] | None = None) -> MailboxResponse:
    email_count, unread_count, latest_email_at = metrics or (0, 0, None)
    return MailboxResponse(
        id=mailbox.id,
        email_address=mailbox.email_address,
        local_part=mailbox.local_part,
        display_name=mailbox.display_name,
        enabled=mailbox.enabled,
        expires_at=mailbox.expires_at,
        created_source=mailbox.created_source,
        tag_ids=[tag.id for tag in mailbox.tags],
        email_count=email_count,
        unread_count=unread_count,
        latest_email_at=latest_email_at,
    )


@router.get("", response_model=MailboxPageResponse)
def get_mailboxes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tag_ids: list[int] | None = Query(default=None),
    tag_mode: str = Query("any"),
    untagged: bool = Query(False),
    sort_by: str = Query("created_desc"),
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> MailboxPageResponse:
    try:
        mailboxes, total, metrics = list_mailboxes(
            db,
            page=page,
            page_size=page_size,
            tag_ids=tag_ids,
            tag_mode=tag_mode,
            untagged=untagged,
            sort_by=sort_by,
        )
    except MailboxServiceError as exc:
        route_logger.warning("Mailbox list rejected reason=%s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return MailboxPageResponse(
        items=[_response(mailbox, metrics.get(mailbox.id)) for mailbox in mailboxes],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/{mailbox_id}", response_model=MailboxResponse)
def get_mailbox_detail(
    mailbox_id: int,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> MailboxResponse:
    try:
        return _response(get_mailbox(db, mailbox_id))
    except MailboxServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


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

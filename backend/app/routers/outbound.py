from functools import wraps
from math import ceil
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.config.settings import get_settings
from app.database.session import get_db
from app.models import Mailbox, OutboundEmail
from app.routers.auth import get_current_admin
from app.schemas.outbound import OutboundCreate, OutboundDetail, OutboundPage, OutboundStatus
from app.services.outbound_service import OutboundError, create_outbound, retry_outbound

router = APIRouter(prefix="/api/outbound-emails", tags=["outbound"], dependencies=[Depends(get_current_admin)])
logger = get_logger("outbound_api")


def safe_errors(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except HTTPException:
            raise
        except OutboundError as exc:
            logger.warning("Outbound API rejected operation=%s", function.__name__)
            raise HTTPException(409, str(exc)) from None
        except Exception as exc:
            logger.error("Outbound API exception operation=%s type=%s", function.__name__, type(exc).__name__)
            raise HTTPException(500, "发送服务暂时不可用，请稍后重试") from None
    return wrapped


def find(db, task_id):
    row = db.get(OutboundEmail, task_id)
    if row is None:
        raise HTTPException(404, "发送记录不存在")
    return row


@router.get("/options")
@safe_errors
def options(db: Session = Depends(get_db)):
    rows = db.scalars(select(Mailbox).order_by(Mailbox.email_address))
    domain = get_settings().allowed_domain
    return [{"id": row.id, "email_address": row.email_address} for row in rows
            if row.email_address == f"{row.local_part}@{domain}"]


@router.post("", response_model=OutboundDetail, status_code=201)
@safe_errors
def create(payload: OutboundCreate, db: Session = Depends(get_db)):
    return OutboundDetail.model_validate(create_outbound(db, get_settings(), payload))


@router.get("", response_model=OutboundPage)
@safe_errors
def listing(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
            status: OutboundStatus | None = None, sort: Literal["created_desc", "created_asc"] = "created_desc",
            db: Session = Depends(get_db)):
    query = select(OutboundEmail)
    if status:
        query = query.where(OutboundEmail.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    query = query.order_by(OutboundEmail.id.desc() if sort == "created_desc" else OutboundEmail.id.asc())
    return OutboundPage(items=list(db.scalars(query.offset((page - 1) * page_size).limit(page_size))),
                        total=total, page=page, page_size=page_size, pages=ceil(total / page_size))


@router.get("/{task_id}", response_model=OutboundDetail)
@safe_errors
def detail(task_id: int, db: Session = Depends(get_db)):
    return OutboundDetail.model_validate(find(db, task_id))


@router.post("/{task_id}/retry", response_model=OutboundDetail)
@safe_errors
def retry(task_id: int, db: Session = Depends(get_db)):
    return OutboundDetail.model_validate(retry_outbound(db, find(db, task_id), get_settings()))

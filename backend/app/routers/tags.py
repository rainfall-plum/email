from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.database.session import get_db
from app.models import AdminUser, Tag
from app.routers.auth import get_current_admin
from app.schemas.mailbox import TagCreateRequest, TagResponse, TagUpdateRequest

router = APIRouter(prefix="/api/tags", tags=["tags"])
tag_logger = get_logger("tags")


@router.get("", response_model=list[TagResponse])
def get_tags(_: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    tags = list(db.scalars(select(Tag).order_by(Tag.name)))
    for tag in tags:
        tag.mailbox_count = len(tag.mailboxes)  # type: ignore[attr-defined]
    return tags


@router.post("", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
def post_tag(
    payload: TagCreateRequest,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    tag = Tag(name=payload.name.strip())
    if not tag.name:
        raise HTTPException(status_code=400, detail="标签名称不能为空")
    db.add(tag)
    try:
        db.commit()
        db.refresh(tag)
    except IntegrityError:
        db.rollback()
        tag_logger.warning("Duplicate tag name=%s", tag.name)
        raise HTTPException(status_code=409, detail="标签名称已存在") from None
    tag_logger.info("Tag created name=%s", tag.name)
    return tag


@router.put("/{tag_id}", response_model=TagResponse)
def put_tag(
    tag_id: int,
    payload: TagUpdateRequest,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="标签不存在")
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="标签名称不能为空")
    tag.name = name
    try:
        db.commit()
        db.refresh(tag)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="标签名称已存在") from None
    tag_logger.info("Tag updated id=%s", tag_id)
    return tag


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_tag(
    tag_id: int,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> None:
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="标签不存在")
    db.delete(tag)
    db.commit()
    tag_logger.info("Tag deleted id=%s", tag_id)

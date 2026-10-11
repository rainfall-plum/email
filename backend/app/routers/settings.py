from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.database.session import get_db
from app.models import AdminUser
from app.routers.auth import get_current_admin
from app.schemas.settings import SystemSettingResponse, SystemSettingUpdateRequest
from app.services.system_settings_service import list_system_settings, update_system_setting

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=list[SystemSettingResponse])
def get_system_settings(
    _: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)
) -> list[dict]:
    return list_system_settings(db, get_settings())


@router.put("/{key}", response_model=SystemSettingResponse)
def put_system_setting(
    key: str,
    payload: SystemSettingUpdateRequest,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    try:
        update_system_setting(db, key, payload.value.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    setting = next(item for item in list_system_settings(db, get_settings()) if item["key"] == key)
    return setting

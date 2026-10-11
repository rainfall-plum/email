from pydantic import BaseModel, Field


class SystemSettingResponse(BaseModel):
    key: str
    label: str
    value: str
    editable: bool
    requires_restart: bool


class SystemSettingUpdateRequest(BaseModel):
    value: str = Field(min_length=1, max_length=128)

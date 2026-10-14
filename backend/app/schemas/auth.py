from pydantic import BaseModel, ConfigDict, Field, model_validator


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128, repr=False)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminResponse(BaseModel):
    id: int
    username: str


class CredentialsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=128, repr=False)
    new_username: str | None = Field(default=None, min_length=3, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    new_password: str | None = Field(default=None, min_length=4, max_length=128, repr=False)
    confirm_new_password: str | None = Field(default=None, max_length=128, repr=False)

    @model_validator(mode="after")
    def validate_changes(self):
        if self.new_username is None and self.new_password is None:
            raise ValueError("至少提供新用户名或新密码")
        if self.confirm_new_password is not None and self.confirm_new_password != self.new_password:
            raise ValueError("两次输入的新密码不一致")
        return self


class CredentialsResponse(BaseModel):
    code: str = "ADMIN_CREDENTIALS_CHANGED"
    message: str = "管理员信息已修改，请使用新用户名和密码登录"


class VerifyPasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128, repr=False)


class VerifyPasswordResponse(BaseModel):
    valid: bool = True

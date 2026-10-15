import json
import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.config.settings import Settings
from app.models import ImportUsername, Mailbox, MailGenerationRecord

MAX_IMPORT_BYTES = 1024 * 1024
MAX_IMPORT_USERNAMES = 1000
MAX_USERNAME_LENGTH = 64
USERNAME_PATTERN = re.compile(r"[a-z0-9]+")
logger = get_logger("username_import")

MESSAGES = {
    "duplicate_in_file": "文件内用户名重复",
    "already_available": "用户名已在可用名字池中",
    "already_used": "用户名已在已用名字池中",
    "already_exists": "邮箱用户名已存在",
    "invalid_format": "用户名只能包含小写字母和数字",
    "empty_username": "用户名不能为空",
    "too_long": "用户名最多 64 个字符",
}


class UsernameImportError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code, self.message, self.status_code = code, message, status_code


def parse_username_file(filename: str | None, content: bytes) -> list:
    if not filename or not filename.lower().endswith(".json"):
        raise UsernameImportError("invalid_extension", "请选择 .json 文件")
    if len(content) > MAX_IMPORT_BYTES:
        raise UsernameImportError("file_too_large", "JSON 文件不能超过 1 MiB", 413)
    try:
        # Reject ambiguous duplicate object keys and non-standard NaN/Infinity.
        def object_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate key")
                result[key] = value
            return result

        def invalid_constant(_):
            raise ValueError("non-standard JSON")

        payload = json.loads(content.decode("utf-8"), object_pairs_hook=object_pairs, parse_constant=invalid_constant)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        logger.error("JSON import parse failed type=%s", type(exc).__name__)
        raise UsernameImportError("invalid_json", "JSON 解析失败，请使用有效的 UTF-8 JSON 文件") from None
    if not isinstance(payload, dict) or set(payload) != {"usernames"} or not isinstance(payload["usernames"], list):
        raise UsernameImportError("unsupported_structure", "JSON 必须只包含 usernames 数组字段")
    usernames = payload["usernames"]
    if not usernames:
        raise UsernameImportError("unsupported_structure", "usernames 数组不能为空")
    if len(usernames) > MAX_IMPORT_USERNAMES:
        raise UsernameImportError("too_many_usernames", "每次最多导入 1000 个用户名")
    return usernames


def import_usernames(db: Session, settings: Settings, usernames: list, admin_id: int) -> dict:
    logger.info("Username import started actor_id=%s total=%s", admin_id, len(usernames))
    try:
        candidates = {value for value in usernames if isinstance(value, str) and len(value) <= MAX_USERNAME_LENGTH}
        existing = set(db.scalars(select(Mailbox.local_part).where(Mailbox.local_part.in_(candidates))))
        imported = set(db.scalars(select(ImportUsername.username).where(ImportUsername.username.in_(candidates))))
        seen: set[str] = set()
        rejected = []
        counts = {"duplicate_count": 0, "invalid_count": 0, "existing_count": 0}
        for username in usernames:
            reason = None
            if not isinstance(username, str):
                reason = "invalid_format"
            elif not username:
                reason = "empty_username"
            elif len(username) > MAX_USERNAME_LENGTH:
                reason = "too_long"
            elif not USERNAME_PATTERN.fullmatch(username):
                reason = "invalid_format"
            elif username in seen:
                reason = "duplicate_in_file"
            else:
                seen.add(username)
                if username in existing:
                    reason = "already_exists"
                elif username in imported:
                    reason = "already_available"
            if reason:
                # Return the submitted string only, never stringify nested objects.
                rejected.append({"username": username if isinstance(username, str) else None,
                                 "reason": reason, "message": MESSAGES[reason]})
                category = "invalid_count" if reason in {"invalid_format", "empty_username", "too_long"} else (
                    "duplicate_count" if reason == "duplicate_in_file" else "existing_count")
                counts[category] += 1
                continue
            db.add(ImportUsername(username=username))
        db.add(MailGenerationRecord(admin_user_id=admin_id, requested_count=len(usernames), generated_count=0, source="import_pool"))
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Username import rolled back actor_id=%s type=%s", admin_id, type(exc).__name__)
        if isinstance(exc, IntegrityError):
            raise UsernameImportError("import_conflict", "用户名发生并发冲突，本次导入已回滚，请重新上传", 409) from None
        raise UsernameImportError("import_failed", "导入失败，本次导入已回滚，请稍后重试", 500) from None
    result = {"total": len(usernames), "success_count": len(usernames) - len(rejected), **counts,
              "created_mailboxes": [], "rejected_usernames": rejected}
    logger.info("Username import finished actor_id=%s total=%s added=%s duplicate=%s invalid=%s existing=%s",
                admin_id, len(usernames), result["success_count"], counts["duplicate_count"], counts["invalid_count"], counts["existing_count"])
    return result

import os
import re
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.config.settings import Settings
from app.models import Attachment, Email
from app.services.code_service import KEYWORD_PATTERN
from app.services.parser_service import ParsedAttachment

attachment_logger = get_logger("attachment")
SAFE_NAME_PATTERN = re.compile(r"[^a-zA-Z0-9._-]+")


def _has_keyword(value: str | None) -> bool:
    return bool(value and KEYWORD_PATTERN.search(value))


def is_verification_attachment(
    attachment: ParsedAttachment,
    subject: str | None,
    body_text: str | None,
    body_html: str | None,
) -> bool:
    """Keep an attachment only when its name or mail context signals verification use."""
    return any(
        (
            _has_keyword(attachment.original_name),
            _has_keyword(subject),
            _has_keyword(body_text),
            _has_keyword(body_html),
        )
    )


def _safe_original_name(name: str) -> str:
    name = Path(name).name.strip()
    name = SAFE_NAME_PATTERN.sub("_", name)
    return name[:255] or "attachment.bin"


def save_relevant_attachments(
    db: Session,
    settings: Settings,
    email: Email,
    parsed_attachments: list[ParsedAttachment],
) -> list[Attachment]:
    saved: list[Attachment] = []
    attachment_dir = settings.data_dir / "attachments" / str(email.id)
    try:
        for item in parsed_attachments:
            if not is_verification_attachment(item, email.subject, email.body_text, email.body_html):
                attachment_logger.info("Discard ordinary attachment name=%s email_id=%s", item.original_name, email.id)
                continue
            original_name = _safe_original_name(item.original_name)
            stored_name = f"{uuid.uuid4().hex}_{original_name}"
            final_path = attachment_dir / stored_name
            temp_path = attachment_dir / f".{stored_name}.tmp"
            try:
                attachment_dir.mkdir(parents=True, exist_ok=True)
                temp_path.write_bytes(item.content)
                os.replace(temp_path, final_path)
                record = Attachment(
                    email_id=email.id,
                    original_name=original_name,
                    stored_name=stored_name,
                    file_path=str(final_path),
                    mime_type=item.mime_type,
                    file_size=len(item.content),
                )
                db.add(record)
                saved.append(record)
                attachment_logger.info("Save verification attachment name=%s email_id=%s", original_name, email.id)
            except OSError as exc:
                temp_path.unlink(missing_ok=True)
                attachment_logger.error("Attachment file save failed name=%s email_id=%s", original_name, email.id, exc_info=True)
                raise OSError("附件保存失败") from exc
    except Exception:
        for record in saved:
            Path(record.file_path).unlink(missing_ok=True)
        attachment_logger.error("Attachment transaction cleanup completed email_id=%s", email.id, exc_info=True)
        raise
    return saved

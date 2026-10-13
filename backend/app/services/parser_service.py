from dataclasses import dataclass
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from html.parser import HTMLParser
import re

from app.config.logging import get_logger

parser_logger = get_logger("parser")


class MailParseError(Exception):
    pass


@dataclass(slots=True)
class ParsedAttachment:
    original_name: str
    mime_type: str
    content: bytes


@dataclass(slots=True)
class ParsedMail:
    sender: str
    receiver: str
    subject: str | None
    message_date: datetime | None
    received_at: datetime
    body_text: str | None
    body_html: str | None
    attachments: list[ParsedAttachment]


def _header_address(message, names: tuple[str, ...]) -> str | None:
    for name in names:
        value = message.get(name)
        if not value:
            continue
        addresses = getaddresses([value])
        if addresses and addresses[0][1]:
            return addresses[0][1].strip().lower()
    return None


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed is None:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError):
        parser_logger.warning("Invalid mail Date header")
        return None


def _part_content(part) -> str:
    try:
        content = part.get_content()
        return content if isinstance(content, str) else str(content)
    except (LookupError, UnicodeError, ValueError):
        payload = part.get_payload(decode=True)
        if payload is None:
            return ""
        charset = part.get_content_charset() or "utf-8"
        try:
            return payload.decode(charset, errors="replace")
        except LookupError:
            return payload.decode("utf-8", errors="replace")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0
    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"script", "style", "noscript"}: self.skip += 1
        elif tag.lower() in {"br", "p", "div", "li", "tr"}: self.parts.append("\n")
    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self.skip: self.skip -= 1
    def handle_data(self, data: str) -> None:
        if not self.skip: self.parts.append(data)


def _html_to_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", "".join(parser.parts))).strip()


def parse_email(raw_message: bytes) -> ParsedMail:
    if not raw_message:
        raise MailParseError("邮件内容为空")
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw_message)
        sender = _header_address(message, ("From",))
        receiver = _header_address(message, ("X-Original-To", "Delivered-To", "To"))
        if not sender or not receiver:
            raise MailParseError("邮件缺少有效的发件人或收件人")

        body_text: str | None = None
        body_html: str | None = None
        attachments: list[ParsedAttachment] = []
        if message.is_multipart():
            parts = message.walk()
        else:
            parts = (message,)
        for part in parts:
            if part.is_multipart():
                continue
            filename = part.get_filename()
            disposition = part.get_content_disposition()
            if disposition == "attachment" or filename:
                payload = part.get_payload(decode=True)
                if payload is None:
                    parser_logger.warning("Attachment payload is empty filename=%s", filename)
                    continue
                attachments.append(
                    ParsedAttachment(
                        original_name=filename or "unnamed-attachment",
                        mime_type=part.get_content_type(),
                        content=payload,
                    )
                )
                continue
            content_type = part.get_content_type().lower()
            if content_type == "text/plain" and body_text is None:
                body_text = _part_content(part)
            elif content_type == "text/html" and body_html is None:
                body_html = _part_content(part)

        if not body_text and body_html:
            body_text = _html_to_text(body_html) or None
        if body_text:
            body_text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", body_text).strip() or None
        parsed = ParsedMail(
            sender=sender,
            receiver=receiver,
            subject=str(message.get("Subject")) if message.get("Subject") else None,
            message_date=_parse_date(message.get("Date")),
            received_at=datetime.now(timezone.utc),
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
        )
        parser_logger.debug(
            "Parsed mail sender=%s receiver=%s subject=%s has_text=%s has_html=%s attachments=%s",
            parsed.sender,
            parsed.receiver,
            parsed.subject,
            parsed.body_text is not None,
            parsed.body_html is not None,
            len(parsed.attachments),
        )
        return parsed
    except MailParseError:
        raise
    except Exception as exc:
        parser_logger.error("MIME parsing failed", exc_info=True)
        raise MailParseError("邮件解析失败") from exc

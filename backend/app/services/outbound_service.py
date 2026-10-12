from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import format_datetime, make_msgid
import smtplib
import socket
import re

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError

from app.config.logging import get_logger
from app.models import Mailbox, OutboundEmail

logger = get_logger("mail.outbound")
RETRY_SECONDS = (60, 300, 900, 1800)


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class OutboundError(ValueError):
    pass


def sender_mailbox(db, settings, mailbox_id):
    mailbox = db.get(Mailbox, mailbox_id)
    if mailbox is None or not re.fullmatch(r"[a-z0-9]{1,64}", mailbox.local_part) or mailbox.email_address != f"{mailbox.local_part}@{settings.allowed_domain}":
        raise OutboundError("发件邮箱不存在或不属于系统域名")
    return mailbox


def create_outbound(db, settings, payload):
    key = str(payload.idempotency_key)

    def existing():
        row = db.scalar(select(OutboundEmail).where(OutboundEmail.idempotency_key == key))
        if row and any(getattr(row, name) != getattr(payload, name) for name in
                       ("sender_mailbox_id", "recipient", "subject", "body_text")):
            raise OutboundError("提交标识已使用，请刷新后重新创建")
        return row

    row = existing()
    if row:
        return row
    mailbox = sender_mailbox(db, settings, payload.sender_mailbox_id)
    row = OutboundEmail(**payload.model_dump(exclude={"idempotency_key"}), sender=mailbox.email_address,
                        idempotency_key=key, message_id=make_msgid(domain=settings.allowed_domain))
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        row = existing()
        if row is None:
            raise
    logger.info("Outbound created id=%s status=%s", row.id, row.status)
    return row


def retry_outbound(db, row, settings):
    sender_mailbox(db, settings, row.sender_mailbox_id)
    result = db.execute(update(OutboundEmail).where(
        OutboundEmail.id == row.id, OutboundEmail.status == "failed",
        OutboundEmail.attempt_count < OutboundEmail.max_attempts,
    ).values(status="queued", next_attempt_at=None, failed_at=None, updated_at=utcnow()))
    if result.rowcount != 1:
        db.rollback()
        raise OutboundError("仅可重试未满5次的失败邮件")
    db.commit()
    db.refresh(row)
    logger.info("Outbound manual_retry id=%s status=queued attempts=%s", row.id, row.attempt_count)
    return row


def build_message(row):
    message = EmailMessage(policy=SMTP)
    message["From"] = row.sender
    message["To"] = row.recipient
    message["Subject"] = row.subject
    message["Date"] = format_datetime(row.created_at.replace(tzinfo=timezone.utc))
    message["Message-ID"] = row.message_id
    message.set_content(row.body_text, subtype="plain", charset="utf-8")
    return message


def smtp_send(row):
    # No authentication or credentials: the local Postfix owns external delivery/retries.
    client = smtplib.SMTP("127.0.0.1", 25, timeout=10)
    try:
        refused = client.send_message(build_message(row), from_addr=row.sender, to_addrs=[row.recipient])
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
    finally:
        # A failed QUIT after DATA acceptance must never cause a duplicate submission.
        client.close()


def classify_error(exc):
    code = None
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        code = next(iter(exc.recipients.values()))[0]
    elif isinstance(exc, smtplib.SMTPResponseException):
        code = exc.smtp_code
    if code is not None:
        if 400 <= code < 500:
            return True, "邮件服务暂时不可用，将自动重试", "4xx"
        return False, "邮件服务拒绝接收，请检查地址或联系管理员", "5xx" if 500 <= code < 600 else "protocol"
    if isinstance(exc, socket.gaierror):
        return exc.errno == socket.EAI_AGAIN, "邮件服务域名解析失败", "dns"
    if isinstance(exc, (TimeoutError, ConnectionError, OSError, smtplib.SMTPServerDisconnected)):
        return True, "连接邮件服务失败或超时，将自动重试", "network"
    if isinstance(exc, OutboundError):
        return False, "发件邮箱不存在或不属于系统域名", "validation"
    return False, "发送处理失败，请联系管理员", "internal"


def recover_sending(db):
    # Only called with the exclusive process lock, after any former owner has exited.
    for row in db.scalars(select(OutboundEmail).where(OutboundEmail.status == "sending")):
        row.status = "retrying" if row.attempt_count < row.max_attempts else "failed"
        row.next_attempt_at = utcnow() if row.status == "retrying" else None
        row.failed_at = utcnow() if row.status == "failed" else None
        row.last_error = "发送进程中断，投递结果待确认；恢复后可能重复投递"
        logger.warning("Outbound recovered id=%s status=%s attempts=%s", row.id, row.status, row.attempt_count)
    db.commit()


def process_one(factory, settings, send=smtp_send, now=None):
    now = now or utcnow()
    with factory() as db:
        eligible = (OutboundEmail.attempt_count < OutboundEmail.max_attempts) & or_(
            OutboundEmail.status == "queued",
            (OutboundEmail.status == "retrying") & (OutboundEmail.next_attempt_at <= now),
        )
        task_id = db.scalar(select(OutboundEmail.id).where(eligible).order_by(OutboundEmail.id).limit(1))
        if task_id is None:
            return False
        claimed = db.execute(update(OutboundEmail).where(OutboundEmail.id == task_id, eligible).values(
            status="sending", attempt_count=OutboundEmail.attempt_count + 1,
            next_attempt_at=None, updated_at=now))
        db.commit()
        if claimed.rowcount != 1:
            return True
        row = db.get(OutboundEmail, task_id)
        logger.info("Outbound start id=%s status=sending sender_domain=%s recipient_domain=%s attempts=%s message_id=%s",
                    row.id, row.sender.rsplit("@", 1)[-1], row.recipient.rsplit("@", 1)[-1], row.attempt_count, row.message_id)
        try:
            mailbox = sender_mailbox(db, settings, row.sender_mailbox_id)
            if mailbox.email_address != row.sender:
                raise OutboundError("sender changed")
            send(row)
        except Exception as exc:
            retryable, message, category = classify_error(exc)
            row.status = "retrying" if retryable and row.attempt_count < row.max_attempts else "failed"
            row.last_error = message if row.status == "retrying" or not retryable else "已达到5次尝试上限，请联系管理员"
            row.next_attempt_at = utcnow() + timedelta(seconds=RETRY_SECONDS[row.attempt_count - 1]) if row.status == "retrying" else None
            row.failed_at = utcnow() if row.status == "failed" else None
            # Never log exception messages/tracebacks: SMTP and SQL errors can contain body/parameters.
            logger.error("Outbound exception id=%s type=%s smtp_category=%s status=%s attempts=%s",
                         row.id, type(exc).__name__, category, row.status, row.attempt_count)
        else:
            category = "2xx"
            row.status, row.last_error, row.sent_at = "sent", None, utcnow()
            row.failed_at = None
        db.commit()
        logger.info("Outbound result id=%s status=%s smtp_category=%s attempts=%s message_id=%s",
                    row.id, row.status, category, row.attempt_count, row.message_id)
    return True

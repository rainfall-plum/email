import argparse
import sys
from uuid import uuid4

from app.config.logging import configure_logging, get_logger, reset_request_id, set_request_id
from app.config.settings import get_settings
from app.database.session import SessionLocal
from app.services.mail_receive_service import MailReceiveError, store_received_mail
from app.services.parser_service import MailParseError, parse_email

worker_logger = get_logger("worker")


def process_message(raw_message: bytes, recipient: str | None = None) -> int:
    settings = get_settings()
    configure_logging(settings.log_dir)
    context_token = set_request_id(f"worker-{uuid4().hex}")
    worker_logger.info("Mail worker started bytes=%s recipient_arg=%s", len(raw_message), bool(recipient))
    if recipient:
        raw_message = (
            f"X-Original-To: {recipient}\r\n".encode("utf-8") + raw_message
        )
    try:
        parsed = parse_email(raw_message)
        db = SessionLocal()
        try:
            store_received_mail(db, settings, parsed, raw_message)
        finally:
            db.close()
        worker_logger.info("Mail worker completed receiver=%s", parsed.receiver)
        return 0
    except (MailParseError, MailReceiveError) as exc:
        worker_logger.error("Mail worker rejected message reason=%s", exc)
        return 75
    except Exception:
        worker_logger.critical("Mail worker failed unexpectedly", exc_info=True)
        return _tempfail_code()
    finally:
        reset_request_id(context_token)


def _tempfail_code() -> int:
    return 75


def main() -> int:
    parser = argparse.ArgumentParser(description="Read one RFC822 message from stdin")
    parser.add_argument("--recipient", help="Envelope recipient supplied by the MTA")
    args = parser.parse_args()
    return process_message(sys.stdin.buffer.read(), args.recipient)


if __name__ == "__main__":
    raise SystemExit(main())

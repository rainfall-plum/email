from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from tests.test_parser_service import build_test_message


def build_attachment_message(recipient="alicewang@example.test"):
    from email.message import EmailMessage
    from email.policy import SMTP

    message = EmailMessage(policy=SMTP)
    message["From"] = "sender@example.net"
    message["To"] = recipient
    message["Subject"] = "普通通知"
    message.set_content("这里有两个附件")
    message.add_attachment(b"verification-content", maintype="text", subtype="plain", filename="verification-code.txt")
    message.add_attachment(b"ordinary-content", maintype="text", subtype="plain", filename="readme.txt")
    return message.as_bytes()


def test_only_verification_attachment_is_saved(tmp_path):
    from app.config.settings import Settings
    from app.database.base import Base
    from app.models import Attachment, Mailbox
    from app.services.mail_receive_service import store_received_mail
    from app.services.parser_service import parse_email

    engine = create_engine(f"sqlite:///{(tmp_path / 'attachment.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    settings = Settings(data_dir=tmp_path / "data", names_dir=tmp_path / "names")
    db.add(Mailbox(email_address="alicewang@example.test", local_part="alicewang"))
    db.commit()
    raw = build_attachment_message()
    email = store_received_mail(db, settings, parse_email(raw), raw)

    attachments = list(db.scalars(select(Attachment).where(Attachment.email_id == email.id)))
    assert len(attachments) == 1
    assert attachments[0].original_name == "verification-code.txt"
    assert Path(attachments[0].file_path).is_file()
    assert not list((settings.data_dir / "attachments" / str(email.id)).glob("*readme*"))
    db.close()


def test_store_mail_and_keep_only_latest_10(tmp_path):
    from app.config.settings import Settings
    from app.database.base import Base
    from app.models import Email, Mailbox
    from app.services.mail_receive_service import store_received_mail
    from app.services.parser_service import parse_email

    engine = create_engine(f"sqlite:///{(tmp_path / 'receive.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    settings = Settings(
        allowed_domain="example.test",
        data_dir=tmp_path / "data",
        names_dir=tmp_path / "names",
        max_emails_per_mailbox=10,
    )
    db.add(Mailbox(email_address="alicewang@example.test", local_part="alicewang"))
    db.commit()

    for number in range(11):
        raw = build_test_message()
        parsed = parse_email(raw)
        parsed.received_at = datetime.now(timezone.utc) + timedelta(seconds=number)
        store_received_mail(db, settings, parsed, raw)

    emails = list(db.scalars(select(Email).order_by(Email.received_at.asc())))
    assert len(emails) == 10
    assert not Path(emails[0].eml_path).name.startswith("missing")
    eml_files = list((settings.data_dir / "eml").glob("*.eml"))
    assert len(eml_files) == 10
    db.close()


def test_unknown_recipient_is_rejected_without_file(tmp_path):
    from app.config.settings import Settings
    from app.database.base import Base
    from app.services.mail_receive_service import MailReceiveError, store_received_mail
    from app.services.parser_service import parse_email

    engine = create_engine(f"sqlite:///{(tmp_path / 'unknown.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    settings = Settings(data_dir=tmp_path / "data", names_dir=tmp_path / "names")

    with pytest.raises(MailReceiveError, match="不存在"):
        store_received_mail(db, settings, parse_email(build_test_message("unknown@example.test")), build_test_message("unknown@example.test"))
    assert not (settings.data_dir / "eml").exists()
    db.close()

from email.message import EmailMessage
from email.policy import SMTP


def build_test_message(recipient="alicewang@example.test") -> bytes:
    message = EmailMessage(policy=SMTP)
    message["From"] = "测试发送者 <sender@example.net>"
    message["To"] = recipient
    message["Subject"] = "登录验证码"
    message["Date"] = "Wed, 11 Oct 2026 12:00:00 +0000"
    message.set_content("您的验证码是 829301")
    message.add_alternative("<html><body><p>验证码：<b>829301</b></p></body></html>", subtype="html")
    message.add_attachment(b"ordinary attachment", maintype="text", subtype="plain", filename="readme.txt")
    return message.as_bytes()


def test_parser_supports_chinese_english_html_and_attachments():
    from app.services.parser_service import parse_email

    parsed = parse_email(build_test_message())

    assert parsed.sender == "sender@example.net"
    assert parsed.receiver == "alicewang@example.test"
    assert parsed.subject == "登录验证码"
    assert "829301" in parsed.body_text
    assert "829301" in parsed.body_html
    assert parsed.message_date is not None
    assert len(parsed.attachments) == 1
    assert parsed.attachments[0].original_name == "readme.txt"


def test_parser_rejects_empty_message():
    import pytest

    from app.services.parser_service import MailParseError, parse_email

    with pytest.raises(MailParseError):
        parse_email(b"")

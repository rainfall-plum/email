from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def test_email_list_and_detail_marks_unread_as_read(tmp_path, monkeypatch):
    monkeypatch.setenv("EMAIL_JWT_SECRET_KEY", "email-api-test-secret-32-bytes")
    database_path = tmp_path / "email-api.sqlite"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}", connect_args={"check_same_thread": False}
    )
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    from app.main import app
    from app.models import AdminUser, Attachment, Base, Email, Mailbox
    from app.routers.auth import get_db
    from app.utils.security import hash_password

    Base.metadata.create_all(engine)
    db = TestSession()
    admin = AdminUser(username="email-admin", password_hash=hash_password("email-password"))
    mailbox = Mailbox(email_address="alicewang@example.test", local_part="alicewang")
    db.add_all([admin, mailbox])
    db.flush()
    mailbox_id = mailbox.id
    email = Email(
            mailbox_id=mailbox.id,
            sender="sender@example.net",
            receiver=mailbox.email_address,
            subject="验证码",
            body_text="829301",
            body_html="<p>829301</p>",
            is_read=False,
            received_at=datetime.now(timezone.utc),
        )
    db.add(email)
    db.flush()
    attachment_path = tmp_path / "verification.txt"
    attachment_path.write_text("829301", encoding="utf-8")
    db.add(
        Attachment(
            email_id=email.id,
            original_name="verification.txt",
            stored_name="stored-verification.txt",
            file_path=str(attachment_path),
            mime_type="text/plain",
            file_size=6,
        )
    )
    db.commit()
    db.close()

    def override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            login = client.post(
                "/api/login", json={"username": "email-admin", "password": "email-password"}
            )
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            listing = client.get(f"/api/mailboxes/{mailbox_id}/emails", headers=headers)
            assert listing.status_code == 200
            email_id = listing.json()[0]["id"]
            assert listing.json()[0]["is_read"] is False

            detail = client.get(f"/api/emails/{email_id}", headers=headers)
            assert detail.status_code == 200
            assert detail.json()["is_read"] is True
            assert detail.json()["body_html"] == "<p>829301</p>"
            assert detail.json()["attachments"][0]["original_name"] == "verification.txt"
            download = client.get(
                f"/api/attachments/{detail.json()['attachments'][0]['id']}/download",
                headers=headers,
            )
            assert download.status_code == 200
            assert download.content == b"829301"
    finally:
        app.dependency_overrides.clear()

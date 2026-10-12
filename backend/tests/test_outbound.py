from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from email import policy
from email.parser import BytesParser
import smtplib
import socket
from uuid import uuid4
from threading import Event

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config.settings import Settings
from app.models import Base, Mailbox, OutboundEmail
from app.schemas.outbound import OutboundCreate
from app.services import outbound_service as service


@pytest.fixture
def queue(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'queue.sqlite'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    settings = Settings(allowed_domain="example.test", data_dir=tmp_path)
    with factory() as db:
        db.add_all([Mailbox(local_part="sender", email_address="sender@example.test"),
                    Mailbox(local_part="other", email_address="other@other.test")])
        db.commit()
    yield factory, settings
    engine.dispose()


def payload(**kwargs):
    return OutboundCreate(**({"sender_mailbox_id": 1, "recipient": "recipient@example.com",
                            "subject": "中文测试", "body_text": "纯文本内容\n第二行", "idempotency_key": uuid4()} | kwargs))


def enqueue(queue, **kwargs):
    factory, settings = queue
    with factory() as db:
        return service.create_outbound(db, settings, payload(**kwargs))


def get(queue, task_id):
    with queue[0]() as db:
        return db.get(OutboundEmail, task_id)


def test_message_is_utf8_plain_text(queue):
    row = enqueue(queue, body_text="中文正文 <b>literal</b>")
    msg = BytesParser(policy=policy.default).parsebytes(service.build_message(row).as_bytes())
    assert msg.get_content_type() == "text/plain"
    assert msg.get_content_charset() == "utf-8"
    assert msg["Subject"] == "中文测试"
    assert msg["From"] == row.sender and msg["To"] == row.recipient
    assert msg["Date"] and msg["Message-ID"] == row.message_id
    assert "中文正文" in msg.get_content()
    assert not msg.is_multipart() and list(msg.iter_attachments()) == []
    assert not any(part.get_content_type() == "text/html" for part in msg.walk())


@pytest.mark.parametrize("change", [{"recipient": "bad"}, {"recipient": "a@example.com,b@example.com"},
    {"recipient": "User <a@example.com>"}, {"recipient": "a@example.com\r\nBcc: x@example.com"},
    {"subject": ""}, {"subject": " "}, {"subject": "x" * 201}, {"subject": "x\nbcc"},
    {"body_text": ""}, {"body_text": " \n"}, {"body_text": "x" * 100001},
    {"body_text": "\x00"}, {"html": "<p>x</p>"}, {"attachments": []}, {"cc": "a@example.com"},
    {"bcc": "a@example.com"}, {"sender_mailbox_id": 0}])
def test_validation(change):
    with pytest.raises(ValueError):
        payload(**change)


@pytest.mark.parametrize("address", ["a@qq.com", "a@163.com", "a@gmail.com", "name+tag@example.com"])
def test_valid_recipient(address):
    assert payload(recipient=address).recipient == address


@pytest.mark.parametrize("mailbox_id", [2, 999])
def test_sender_must_exist_and_match_domain(queue, mailbox_id):
    with pytest.raises(service.OutboundError):
        enqueue(queue, sender_mailbox_id=mailbox_id)


def test_idempotency_and_concurrent_claim(queue):
    key = uuid4()
    row = enqueue(queue, idempotency_key=key)
    assert enqueue(queue, idempotency_key=key).id == row.id
    with pytest.raises(service.OutboundError):
        enqueue(queue, idempotency_key=key, subject="different")
    sent = []
    def send(task):
        assert get(queue, task.id).status == "sending"
        sent.append(task.id)
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda _: service.process_one(*queue, send=send), range(2)))
    assert sent == [row.id]
    assert get(queue, row.id).status == "sent"
    assert service.process_one(*queue, send=send) is False


@pytest.mark.parametrize("exc,retryable", [
    (smtplib.SMTPDataError(451, b"temporary"), True),
    (smtplib.SMTPRecipientsRefused({"a@example.com": (450, b"temporary")}), True),
    (TimeoutError(), True), (ConnectionRefusedError(), True),
    (smtplib.SMTPServerDisconnected(), True), (socket.gaierror(socket.EAI_AGAIN, "dns"), True),
    (socket.gaierror(socket.EAI_NONAME, "dns"), False),
    (smtplib.SMTPDataError(550, b"permanent"), False),
    (smtplib.SMTPRecipientsRefused({"a@example.com": (550, b"permanent")}), False),
    (ValueError("sensitive body"), False),
])
def test_failure_classification(queue, exc, retryable, monkeypatch):
    row = enqueue(queue)
    now = service.utcnow()
    monkeypatch.setattr(service, "utcnow", lambda: now)
    def fail(_):
        raise exc
    assert service.process_one(*queue, send=fail)
    saved = get(queue, row.id)
    assert saved.attempt_count == 1
    assert saved.status == ("retrying" if retryable else "failed")
    assert saved.next_attempt_at == (now + timedelta(seconds=60) if retryable else None)
    assert "sensitive" not in saved.last_error


def test_retry_schedule_and_limit(queue, monkeypatch):
    row = enqueue(queue)
    now = service.utcnow()
    def fail(_):
        raise smtplib.SMTPDataError(451, b"temporary")
    for attempt, seconds in enumerate([60, 300, 900, 1800, None], 1):
        monkeypatch.setattr(service, "utcnow", lambda: now)
        service.process_one(*queue, send=fail, now=now)
        saved = get(queue, row.id)
        assert saved.attempt_count == attempt
        if seconds:
            assert saved.status == "retrying" and saved.next_attempt_at == now + timedelta(seconds=seconds)
            assert not service.process_one(*queue, send=fail, now=now)
            now = saved.next_attempt_at
        else:
            assert saved.status == "failed" and saved.failed_at and saved.next_attempt_at is None
    with queue[0]() as db, pytest.raises(service.OutboundError):
        service.retry_outbound(db, db.get(OutboundEmail, row.id), queue[1])


def test_manual_retry_and_restart_recovery(queue):
    row = enqueue(queue)
    with queue[0]() as db:
        saved = db.get(OutboundEmail, row.id)
        for state in ["queued", "sending", "retrying", "sent"]:
            saved.status = state
            db.commit()
            with pytest.raises(service.OutboundError):
                service.retry_outbound(db, saved, queue[1])
        saved.status, saved.attempt_count = "sending", 1
        db.commit()
        service.recover_sending(db)
        db.refresh(saved)
        assert saved.status == "retrying" and saved.next_attempt_at
        saved.status = "failed"
        db.commit()
        service.retry_outbound(db, saved, queue[1])
        assert saved.status == "queued" and saved.attempt_count == 1
        saved.status, saved.attempt_count = "sending", 5
        db.commit()
        service.recover_sending(db)
        db.refresh(saved)
        assert saved.status == "failed" and saved.next_attempt_at is None


def test_deleted_sender_and_single_failure_do_not_stop_queue(queue):
    first = enqueue(queue)
    second = enqueue(queue)
    calls = []
    def send(row):
        calls.append(row.id)
        if row.id == first.id:
            raise ValueError("failure")
    service.process_one(*queue, send=send)
    service.process_one(*queue, send=send)
    assert calls == [first.id, second.id]
    third = enqueue(queue)
    with queue[0]() as db:
        db.delete(db.get(Mailbox, 1)); db.commit()
    service.process_one(*queue, send=send)
    assert get(queue, third.id).status == "failed" and third.id not in calls


def test_retry_eventually_succeeds_and_message_id_is_stable(queue):
    row = enqueue(queue)
    def fail(_):
        raise TimeoutError()
    service.process_one(*queue, send=fail)
    due = get(queue, row.id).next_attempt_at
    service.process_one(*queue, send=lambda task: None, now=due)
    saved = get(queue, row.id)
    assert saved.status == "sent" and saved.attempt_count == 2
    assert saved.message_id == row.message_id and saved.last_error is None


def test_local_smtp_envelope_and_close_without_quit(queue, monkeypatch):
    row = enqueue(queue)
    calls = []
    class SMTP:
        def __init__(self, host, port, timeout):
            assert (host, port, timeout) == ("127.0.0.1", 25, 10)
        def send_message(self, message, from_addr, to_addrs):
            assert from_addr == row.sender and to_addrs == [row.recipient]
            assert message.get_content_type() == "text/plain"
            calls.append("accepted")
            return {}
        def close(self):
            calls.append("closed")
    monkeypatch.setattr(service.smtplib, "SMTP", SMTP)
    service.smtp_send(row)
    assert calls == ["accepted", "closed"]


def test_worker_recovers_restart_and_releases_exclusive_lock(queue, monkeypatch):
    from app.workers import outbound_worker
    row = enqueue(queue)
    with queue[0]() as db:
        saved = db.get(OutboundEmail, row.id)
        saved.status, saved.attempt_count = "sending", 1
        db.commit()
    entered, release = Event(), Event()
    def process(factory, settings):
        entered.set()
        release.wait(3)
        return False
    monkeypatch.setattr(outbound_worker, "process_one", process)
    worker = outbound_worker.OutboundWorker(*queue)
    worker.start()
    try:
        assert entered.wait(3)
        assert get(queue, row.id).status == "retrying"
        # A second live worker must wait for ownership instead of resetting active work.
        second = outbound_worker.OutboundWorker(*queue)
        second.start()
        second.stop()
    finally:
        release.set()
        worker.stop()
    entered.clear()
    successor = outbound_worker.OutboundWorker(*queue)
    successor.start()
    try:
        assert entered.wait(3)
    finally:
        successor.stop()


def test_api_auth_pagination_retry_and_safe_errors(queue, monkeypatch):
    from app.main import app
    from app.database.session import get_db
    from app.routers.auth import get_current_admin
    from app.config.settings import get_settings
    from app.routers import outbound

    def database():
        with queue[0]() as db:
            yield db
    app.dependency_overrides[get_db] = database
    monkeypatch.setattr(outbound, "get_settings", lambda: queue[1])
    try:
        with TestClient(app) as client:
            for method, path in [("get", ""), ("post", ""), ("get", "/options"), ("get", "/1"), ("post", "/1/retry")]:
                assert getattr(client, method)("/api/outbound-emails" + path).status_code == 401
            app.dependency_overrides[get_current_admin] = lambda: object()
            request = payload().model_dump(mode="json")
            created = client.post("/api/outbound-emails", json=request)
            assert created.status_code == 201
            task_id = created.json()["id"]
            assert created.json()["created_at"].endswith("Z")
            assert client.post("/api/outbound-emails", json=request).json()["id"] == task_id
            assert len(client.get("/api/outbound-emails/options").json()) == 1
            assert client.get(f"/api/outbound-emails/{task_id}").json()["body_text"] == request["body_text"]
            for _ in range(2):
                client.post("/api/outbound-emails", json=payload().model_dump(mode="json"))
            page = client.get("/api/outbound-emails?page=2&page_size=1&status=queued&sort=created_asc").json()
            assert page["total"] == 3 and page["pages"] == 3 and len(page["items"]) == 1
            assert "body_text" not in page["items"][0]
            assert client.get("/api/outbound-emails?status=failed").json()["total"] == 0
            assert client.get("/api/outbound-emails?status=unknown").status_code == 422
            assert client.get("/api/outbound-emails/999").status_code == 404
            assert client.post(f"/api/outbound-emails/{task_id}/retry").status_code == 409
            with queue[0]() as db:
                row = db.get(OutboundEmail, task_id); row.status = "failed"; row.attempt_count = 1; db.commit()
            assert client.post(f"/api/outbound-emails/{task_id}/retry").json()["status"] == "queued"
            assert client.post("/api/outbound-emails", json=request | {"html": "private"}).json() == {"detail": "请求参数无效"}
            def explode(*args):
                raise RuntimeError("SQL /private/ secret body")
            monkeypatch.setattr(outbound, "create_outbound", explode)
            response = client.post("/api/outbound-emails", json=request)
            assert response.status_code == 500 and "private" not in response.text and "SQL" not in response.text
    finally:
        app.dependency_overrides.clear()

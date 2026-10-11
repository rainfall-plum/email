import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _write_names(names_dir, available_first, available_last):
    names_dir.mkdir(parents=True, exist_ok=True)
    (names_dir / "available_first_names.json").write_text(
        json.dumps(available_first), encoding="utf-8"
    )
    (names_dir / "available_last_names.json").write_text(
        json.dumps(available_last), encoding="utf-8"
    )
    (names_dir / "used_first_names.json").write_text("[]", encoding="utf-8")
    (names_dir / "used_last_names.json").write_text("[]", encoding="utf-8")


def test_manual_mailbox_duplicate_and_format(tmp_path):
    from app.config.settings import Settings
    from app.database.base import Base
    from app.models import Mailbox
    from app.services.mailbox_service import MailboxServiceError, create_mailbox

    engine = create_engine(f"sqlite:///{(tmp_path / 'mailboxes.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    settings = Settings(allowed_domain="example.test", names_dir=tmp_path / "names")

    mailbox = create_mailbox(db, settings, "alicewang")
    assert mailbox.email_address == "alicewang@example.test"

    with pytest.raises(MailboxServiceError, match="已存在"):
        create_mailbox(db, settings, "alicewang")
    with pytest.raises(MailboxServiceError, match="只允许"):
        create_mailbox(db, settings, "alice.wang")
    assert db.query(Mailbox).count() == 1
    db.close()


def test_batch_generation_consumes_json_and_resolves_conflict(tmp_path):
    from app.config.settings import Settings
    from app.database.base import Base
    from app.services.mailbox_service import create_mailbox, generate_mailboxes

    names_dir = tmp_path / "names"
    _write_names(names_dir, ["alice", "bob"], ["wang", "li"])
    engine = create_engine(f"sqlite:///{(tmp_path / 'batch.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    settings = Settings(allowed_domain="example.test", names_dir=names_dir)

    create_mailbox(db, settings, "alicewang")
    generated = generate_mailboxes(db, settings, 2, [])

    assert [mailbox.local_part for mailbox in generated] == ["alicewang1", "bobli"]
    assert json.loads((names_dir / "available_first_names.json").read_text()) == []
    assert json.loads((names_dir / "available_last_names.json").read_text()) == []
    assert json.loads((names_dir / "used_first_names.json").read_text()) == ["alice", "bob"]
    assert json.loads((names_dir / "used_last_names.json").read_text()) == ["wang", "li"]
    db.close()


def test_batch_generation_supports_100_local_test_mailboxes(tmp_path):
    from app.config.settings import Settings
    from app.database.base import Base
    from app.services.mailbox_service import generate_mailboxes

    names_dir = tmp_path / "names"
    _write_names(
        names_dir,
        [f"first{i:03d}" for i in range(1, 101)],
        [f"last{i:03d}" for i in range(1, 101)],
    )
    engine = create_engine(f"sqlite:///{(tmp_path / 'hundred.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    settings = Settings(allowed_domain="example.test", names_dir=names_dir)

    generated = generate_mailboxes(db, settings, 100, [])

    assert len(generated) == 100
    assert len({mailbox.email_address for mailbox in generated}) == 100
    db.close()

import os
import subprocess
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from tests.test_parser_service import build_test_message


def test_worker_pipe_to_sqlite(tmp_path):
    from app.database.base import Base
    from app.models import Email, Mailbox

    database_path = tmp_path / "worker.sqlite"
    data_dir = tmp_path / "data"
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Mailbox(email_address="alicewang@example.test", local_part="alicewang"))
        db.commit()

    environment = os.environ.copy()
    environment.update(
        {
            "EMAIL_DATABASE_URL": f"sqlite:///{database_path.as_posix()}",
            "EMAIL_DATA_DIR": str(data_dir),
            "EMAIL_LOG_DIR": str(tmp_path / "logs"),
            "EMAIL_ALLOWED_DOMAIN": "example.test",
        }
    )
    result = subprocess.run(
        [sys.executable, "-m", "app.workers.mail_worker", "--recipient", "alicewang@example.test"],
        input=build_test_message(),
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[1]),
        env=environment,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr.decode(errors="replace")
    with Session(engine) as db:
        saved = db.scalar(select(Email))
        assert saved is not None
        assert saved.receiver == "alicewang@example.test"
        assert saved.body_html is not None
        assert saved.verification_code == "829301"
        assert saved.is_read is False
    assert len(list((data_dir / "eml").glob("*.eml"))) == 1


def test_worker_returns_permanent_failure_for_unknown_recipient(tmp_path):
    from app.database.base import Base

    database_path = tmp_path / "worker-unknown.sqlite"
    data_dir = tmp_path / "data"
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)

    environment = os.environ.copy()
    environment.update(
        {
            "EMAIL_DATABASE_URL": f"sqlite:///{database_path.as_posix()}",
            "EMAIL_DATA_DIR": str(data_dir),
            "EMAIL_LOG_DIR": str(tmp_path / "logs"),
            "EMAIL_ALLOWED_DOMAIN": "example.test",
        }
    )
    result = subprocess.run(
        [sys.executable, "-m", "app.workers.mail_worker", "--recipient", "unknown@example.test"],
        input=build_test_message("unknown@example.test"),
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[1]),
        env=environment,
        capture_output=True,
    )

    assert result.returncode == 67
    assert not (data_dir / "eml").exists()

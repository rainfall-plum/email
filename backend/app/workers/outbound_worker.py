import os
from threading import Event, Thread

from app.config.logging import get_logger
from app.services.outbound_service import process_one, recover_sending

logger = get_logger("worker.outbound")


class OutboundWorker:
    """One local owner per SQLite installation; OS releases its lock even after a crash."""

    def __init__(self, factory, settings):
        self.factory, self.settings = factory, settings
        self.stop_event = Event()
        self.thread = Thread(target=self.run, name="outbound-worker", daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join()

    def run(self):
        logger.info("Outbound worker started")
        try:
            self.settings.data_dir.mkdir(parents=True, exist_ok=True)
            with (self.settings.data_dir / "outbound-worker.lock").open("a+b") as lock:
                while not self.stop_event.is_set():
                    try:
                        if os.name == "nt":
                            import msvcrt
                            lock.seek(0)
                            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                        else:
                            import fcntl
                            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except OSError:
                        self.stop_event.wait(2)
                else:
                    return
                needs_recovery = True
                while not self.stop_event.is_set():
                    try:
                        if needs_recovery:
                            with self.factory() as db:
                                recover_sending(db)
                            needs_recovery = False
                        if not process_one(self.factory, self.settings):
                            self.stop_event.wait(2)
                    except Exception as exc:
                        logger.error("Outbound worker/database/recovery exception type=%s", type(exc).__name__)
                        needs_recovery = True
                        self.stop_event.wait(5)
        except Exception as exc:
            logger.error("Outbound worker configuration/file exception type=%s", type(exc).__name__)
        finally:
            logger.info("Outbound worker stopped")

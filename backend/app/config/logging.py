import logging
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path


APP_LOGGER_NAME = "email_platform"
_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def set_request_id(value: str):
    return _request_id.set(value)


def reset_request_id(token) -> None:
    _request_id.reset(token)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


class PrefixFilter(logging.Filter):
    def __init__(self, prefixes: tuple[str, ...]) -> None:
        super().__init__()
        self.prefixes = prefixes

    def filter(self, record: logging.LogRecord) -> bool:
        return record.name in self.prefixes or record.name.startswith(
            tuple(f"{prefix}." for prefix in self.prefixes)
        )


def _file_handler(path: Path, level: int, formatter: logging.Formatter) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())
    return handler


def configure_logging(log_dir: Path) -> logging.Logger:
    """Configure separate application, mail, error and access log streams."""
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(APP_LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s request_id=%(request_id)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    app_handler = _file_handler(log_dir / "app.log", logging.DEBUG, formatter)
    mail_handler = _file_handler(log_dir / "mail.log", logging.INFO, formatter)
    mail_handler.addFilter(
        PrefixFilter(
            (
                f"{APP_LOGGER_NAME}.mail",
                f"{APP_LOGGER_NAME}.parser",
                f"{APP_LOGGER_NAME}.code",
                f"{APP_LOGGER_NAME}.attachment",
                f"{APP_LOGGER_NAME}.worker",
            )
        )
    )
    error_handler = _file_handler(log_dir / "error.log", logging.ERROR, formatter)
    access_handler = _file_handler(log_dir / "access.log", logging.INFO, formatter)
    access_handler.addFilter(PrefixFilter((f"{APP_LOGGER_NAME}.access",)))

    logger.addHandler(app_handler)
    logger.addHandler(mail_handler)
    logger.addHandler(error_handler)
    logger.addHandler(access_handler)
    return logger


def get_logger(name: str = "app") -> logging.Logger:
    return logging.getLogger(f"{APP_LOGGER_NAME}.{name}")

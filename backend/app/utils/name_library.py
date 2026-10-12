import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock

from app.config.logging import get_logger

name_logger = get_logger("names")
NAME_LIBRARY_LOCK = RLock()


class NameLibraryError(Exception):
    pass


class NameLibrary:
    def __init__(self, names_dir: Path) -> None:
        self.names_dir = names_dir
        self.names_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, state: str, kind: str) -> Path:
        return self.names_dir / f"{state}_{kind}_names.json"

    def _read(self, state: str, kind: str, *, create_missing: bool = True) -> list[str]:
        path = self._path(state, kind)
        if not path.exists():
            if create_missing:
                path.write_text("[]\n", encoding="utf-8")
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            name_logger.error("Name library read failed type=%s", type(exc).__name__)
            raise NameLibraryError("名字库读取失败") from exc
        if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
            name_logger.error("Name library format invalid")
            raise NameLibraryError("名字库格式无效")
        return data

    def _write(self, state: str, kind: str, values: list[str]) -> None:
        path = self._path(state, kind)
        try:
            with NamedTemporaryFile("w", encoding="utf-8", dir=self.names_dir, delete=False) as temp:
                json.dump(values, temp, ensure_ascii=False, indent=2)
                temp.write("\n")
                temp_path = Path(temp.name)
            os.replace(temp_path, path)
        except OSError as exc:
            if "temp_path" in locals() and temp_path.exists():
                temp_path.unlink(missing_ok=True)
            name_logger.error("Name library write failed type=%s", type(exc).__name__)
            raise NameLibraryError("名字库保存失败") from exc

    def take_pair(self) -> tuple[str, str]:
        pairs = self.reserve_pairs(1)
        self.consume_pairs(pairs)
        return pairs[0]

    def reserve_pairs(self, count: int) -> list[tuple[str, str]]:
        if count < 1:
            raise NameLibraryError("名字数量无效")
        first_names = self._read("available", "first")
        last_names = self._read("available", "last")
        if len(first_names) < count or len(last_names) < count:
            raise NameLibraryError("可用名字库不足")
        return list(zip(first_names[:count], last_names[:count], strict=True))

    def consume_pairs(self, pairs: list[tuple[str, str]]) -> None:
        if not pairs:
            return
        count = len(pairs)
        first_names = self._read("available", "first")
        last_names = self._read("available", "last")
        expected = list(zip(first_names[:count], last_names[:count], strict=True))
        if expected != pairs:
            raise NameLibraryError("名字库已发生变化，请重试")
        used_first = self._read("used", "first")
        used_last = self._read("used", "last")
        snapshot = self.snapshot()
        for first, last in pairs:
            if first not in used_first:
                used_first.append(first)
            if last not in used_last:
                used_last.append(last)
        try:
            self._write("available", "first", first_names[count:])
            self._write("available", "last", last_names[count:])
            self._write("used", "first", used_first)
            self._write("used", "last", used_last)
        except Exception:
            self.restore(snapshot)
            raise
        name_logger.debug("Name pairs consumed count=%s", count)

    def snapshot(self) -> dict[tuple[str, str], list[str]]:
        return {(state, kind): self._read(state, kind)
                for state in ("available", "used") for kind in ("first", "last")}

    def restore(self, snapshot: dict[tuple[str, str], list[str]]) -> None:
        failed = False
        for (state, kind), values in snapshot.items():
            try:
                self._write(state, kind, values)
            except Exception as exc:
                failed = True
                name_logger.error("Name pool recovery failed type=%s", type(exc).__name__)
        if failed:
            raise NameLibraryError("名字库恢复失败，请联系管理员")

    def _append_used(self, kind: str, value: str) -> None:
        used = self._read("used", kind)
        if value not in used:
            used.append(value)
        self._write("used", kind, used)

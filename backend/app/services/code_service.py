import re
from html.parser import HTMLParser

from app.config.logging import get_logger

code_logger = get_logger("code")

KEYWORD_PATTERN = re.compile(
    r"验证码|动态码|安全码|校验码|verification|verify|code|otp|security",
    re.IGNORECASE,
)
CODE_PATTERN = re.compile(r"(?<!\d)(\d{4,8})(?!\d)")
KEYWORD_WINDOW = 96


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._hidden_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript"}:
            self._hidden_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript"} and self._hidden_depth:
            self._hidden_depth -= 1

    def handle_data(self, data):
        if not self._hidden_depth:
            self.parts.append(data)


def _html_visible_text(value: str | None) -> str:
    if not value:
        return ""
    parser = _VisibleTextParser()
    try:
        parser.feed(value)
        parser.close()
        return " ".join(parser.parts)
    except (ValueError, TypeError):
        code_logger.warning("HTML text extraction failed")
        return value


def _keyword_near_code(text: str, code_start: int, code_end: int) -> tuple[int, str] | None:
    start = max(0, code_start - KEYWORD_WINDOW)
    end = min(len(text), code_end + KEYWORD_WINDOW)
    nearest: tuple[int, str] | None = None
    for match in KEYWORD_PATTERN.finditer(text, start, end):
        distance = min(abs(match.end() - code_start), abs(match.start() - code_end))
        if nearest is None or distance < nearest[0]:
            nearest = (distance, match.group(0))
    return nearest


def extract_verification_code(
    subject: str | None,
    body_text: str | None,
    body_html: str | None,
) -> str | None:
    """Extract the closest 4–8 digit number to a supported verification keyword."""
    sources = (
        ("subject", subject or ""),
        ("body_text", body_text or ""),
        ("body_html", _html_visible_text(body_html)),
    )
    subject_keyword = KEYWORD_PATTERN.search(sources[0][1])
    matches: list[tuple[int, int, str, str, str]] = []
    for source_index, (source_name, text) in enumerate(sources):
        for candidate in CODE_PATTERN.finditer(text):
            nearby = _keyword_near_code(text, candidate.start(), candidate.end())
            if nearby is None and source_name != "subject" and subject_keyword is not None:
                nearby = (KEYWORD_WINDOW + source_index, subject_keyword.group(0))
            code_logger.debug(
                "Code candidate source=%s length=%s keyword=%s",
                source_name,
                len(candidate.group(1)),
                nearby[1] if nearby else None,
            )
            if nearby is not None:
                matches.append((nearby[0], source_index, candidate.start(), candidate.group(1), source_name))
    if not matches:
        code_logger.warning("Verification code not recognized")
        return None
    matches.sort(key=lambda item: (item[0], item[1], item[2]))
    selected = matches[0]
    code_logger.info(
        "Verification code recognized source=%s length=%s",
        selected[4],
        len(selected[3]),
    )
    return selected[3]

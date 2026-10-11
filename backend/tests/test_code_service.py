import pytest


@pytest.mark.parametrize(
    ("subject", "body_text", "body_html", "expected"),
    [
        ("登录验证码", "您的验证码是 829301", None, "829301"),
        ("Your verification code", "Use 4821 to continue", None, "4821"),
        (None, None, "<p>安全码：<strong>12345678</strong></p>", "12345678"),
    ],
)
def test_extract_verification_code(subject, body_text, body_html, expected):
    from app.services.code_service import extract_verification_code

    assert extract_verification_code(subject, body_text, body_html) == expected


@pytest.mark.parametrize(
    ("subject", "body_text"),
    [
        ("订单号", "请保存订单号 123456789"),
        ("验证码", "数字 123"),
        ("通知", "普通数字 829301"),
    ],
)
def test_code_requires_keyword_and_4_to_8_digit_boundary(subject, body_text):
    from app.services.code_service import extract_verification_code

    assert extract_verification_code(subject, body_text, None) is None


def test_code_prefers_nearest_keyword_and_ignores_script_html():
    from app.services.code_service import extract_verification_code

    body_html = "<script>验证码 1111</script><p>动态码：<b>7777</b></p>"
    assert extract_verification_code(None, None, body_html) == "7777"

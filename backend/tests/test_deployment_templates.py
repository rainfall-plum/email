from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_deployment_templates_are_present_and_do_not_contain_private_keys():
    required = [
        "deploy/README.md",
        "deploy/env/app.env.example",
        "deploy/systemd/email-platform.service",
        "deploy/nginx/email-platform.conf.example",
        "deploy/postfix/main.cf.example",
        "deploy/postfix/master.cf.example",
        "deploy/postfix/transport.example",
        "deploy/backup/backup.sh",
        "deploy/firewall/ufw.example",
        "deploy/firewall/fail2ban-jail.local.example",
    ]
    for relative_path in required:
        content = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        assert "BEGIN PRIVATE KEY" not in content
    for relative_path in (
        "deploy/env/app.env.example",
        "deploy/nginx/email-platform.conf.example",
        "deploy/postfix/main.cf.example",
        "deploy/postfix/transport.example",
    ):
        assert "REPLACE_WITH" in (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_backup_script_has_safe_path_checks():
    script = (PROJECT_ROOT / "deploy/backup/backup.sh").read_text(encoding="utf-8")
    assert "set -Eeuo pipefail" in script
    assert "[[ \"$APP_DATA_DIR\" = /*" in script
    assert "RETENTION_DAYS" in script

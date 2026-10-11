# Postfix pipe 配置说明

本目录只提供审核模板，不包含真实域名、服务器地址或生产配置。

Worker 从 stdin 读取一封 RFC822 邮件：

```text
python -m app.workers.mail_worker --recipient alicewang@example.test
```

Postfix 的本地开发 pipe 可以将收件人作为参数传入：

```text
email-platform unix - n n - - pipe flags= user=mailworker argv=/path/to/backend/.venv/bin/python /path/to/backend/app/workers/mail_worker.py --recipient ${recipient}
```

正式部署前需要根据 Ubuntu、Postfix 用户权限和 systemd 运行目录重新审核，不能直接把本示例当作生产配置。

部署步骤：

1. 将 `transport.example` 中的占位域名替换为单一域名，执行 `postmap /etc/postfix/transport`。
2. 将 `master.cf.example` 的 service block 加入 `/etc/postfix/master.cf`。
3. 将 `main.cf.example` 中的参数合并到 `/etc/postfix/main.cf`。
4. 执行 `postfix check && systemctl reload postfix`。
5. 使用测试邮件检查 `journalctl`、`mail.log`、Worker 和 SQLite。

Postfix 只负责接收和 pipe 投递；未知邮箱由 Python Worker 拒绝，不会自动创建邮箱。

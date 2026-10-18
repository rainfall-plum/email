# Docker 部署

Windows 可以使用 Docker Desktop 的 WSL2 后端构建和运行本项目；生产环境建议使用 Linux Docker Engine。项目中的 Postfix 收件链路仍建议运行在 Linux 主机或独立邮件服务器上，容器默认关闭应用内发件 Worker，避免把外部邮件服务误配置进容器。

1. 复制 `.env.example` 为 `.env`，设置 `EMAIL_JWT_SECRET_KEY`、`EMAIL_BOOTSTRAP_ADMIN_PASSWORD` 和 `EMAIL_ALLOWED_DOMAIN`。
2. 执行 `docker compose up -d --build`。
3. 访问 `http://localhost:8080`，端口可通过 `EMAIL_HTTP_PORT` 调整。
4. 数据和日志分别保存在 Docker volumes `email-data` 与 `email-logs`。

不要把 `.env`、生产数据库或邮件正文放入镜像或 Git。首次迁移生产数据前，应先备份 SQLite 数据库，并确认外部 Postfix 已将 API 所需的收件链路配置好。

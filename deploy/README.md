# Ubuntu 部署说明（模板）

本目录只包含部署模板。模板中的域名、路径和账号均为占位符，执行前必须由部署人员替换并审核；开发阶段不要填写真实生产密钥到仓库。

## 推荐目录

```text
/opt/email-platform/              # 代码和 Python 虚拟环境
/var/lib/email-platform/          # SQLite、eml、attachments、names、backup
/var/log/email-platform/          # app、mail、error、access 日志
/etc/email-platform/app.env       # 生产环境变量，权限 600
```

## 部署顺序

1. 安装 Python 3.12、Node.js、Nginx、Postfix、UFW 和 Fail2ban。
2. 创建专用用户 `emailplatform`，将代码部署到 `/opt/email-platform`。
3. 创建 Python 虚拟环境并安装 `backend/requirements.txt`。
4. 构建前端：`cd frontend && npm ci && npm run build`。
5. 复制 `env/app.env.example` 为 `/etc/email-platform/app.env`，填写真实部署值并设置 `chmod 600`。
6. 安装并审核 `systemd/email-platform.service`。
7. 安装并审核 `nginx/email-platform.conf.example`，再配置证书。
8. 按 `postfix/README.md` 配置单域名 pipe 路由。
9. 启动服务并检查：

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now email-platform
   curl -fsS http://127.0.0.1:8000/api/health
   sudo journalctl -u email-platform -n 100 --no-pager
   ```

10. 配置每日备份，并定期执行恢复演练。

## 生产安全要求

- `EMAIL_JWT_SECRET_KEY` 必须使用至少 32 字节随机值。
- 管理员密码只通过受保护的环境文件或初始化流程提供。
- SQLite、附件、eml 和日志目录只授予服务用户权限。
- Nginx 对外只开放 80/443；SMTP 25 仅由 Postfix 接收。
- 不要把 `.env`、私钥、数据库、附件或日志提交到 Git。
- 上线前替换全部 `REPLACE_WITH_*` 占位符。

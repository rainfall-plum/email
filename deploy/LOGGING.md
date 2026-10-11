# 生产日志排障速查

日志目录由 `EMAIL_LOG_DIR` 控制，默认文件为：

| 文件 | 主要内容 | 首先用于排查 |
| --- | --- | --- |
| `access.log` | 请求方法、路径、状态码、耗时、客户端、`request_id` | 前端/API 是否到达后端 |
| `app.log` | 启动、数据库、认证、业务和完整异常堆栈 | 后端异常和跨模块排查 |
| `mail.log` | Worker、MIME、验证码、附件、邮件入库和清理 | SMTP 到 SQLite 的邮件闭环 |
| `error.log` | ERROR/CRITICAL 及异常堆栈 | 严重错误和服务故障 |

## 关联一次 API 请求

每个请求响应带有 `X-Request-ID`，并在 `access.log`、`app.log` 中以如下格式出现：

```text
request_id=... method=POST path=/api/login status=200
```

```bash
grep 'request_id=<ID>' /var/log/email-platform/access.log /var/log/email-platform/app.log
```

## 关联一封邮件

Worker 会生成 `worker-<uuid>` ID。按以下顺序排查：

1. `mail.log`：Worker started。
2. `app.log`：MIME parsing、recipient、验证码和附件判断。
3. `mail.log`：Receive mail 或拒绝原因。
4. `mail.log`：Delete old mail（若触发 10 封上限）。
5. API 的 `access.log`：后台是否成功读取邮件。

## 常见结论

- 没有 `Worker started`：Postfix 没有调用 Worker，检查 Postfix pipe/journal。
- 有 `Worker started`，没有 `Parsed mail`：MIME 输入为空或解析失败，查 `mail.log`/`error.log`。
- 有 `Recipient mailbox not found`：邮箱不存在、已停用或域名/收件人不一致。
- 有 `EML file save failed`：检查 `EMAIL_DATA_DIR` 权限和磁盘空间。
- 有 `Mail database save failed`：检查 SQLite 路径权限、数据库锁和 `error.log` 堆栈。
- 有 `Verification code not recognized`：邮件已接收，但关键词/4–8 位数字规则未匹配。
- 有 `Attachment file missing`：数据库有附件记录，但文件已被外部删除，需要从备份恢复。

日志中不会记录管理员密码、JWT 明文或验证码明文；验证码只记录来源和长度。邮件地址、附件名称和错误堆栈属于运维敏感信息，应限制日志文件权限。

# 备份与恢复

备份内容：

- SQLite 数据库
- `eml/`
- `attachments/`
- 名字库 `names/`

执行前确认 `APP_DATA_DIR` 和 `BACKUP_ROOT` 均为明确的绝对路径。脚本默认保留 14 天备份；生产环境应使用 cron 或 systemd timer，并将备份目录同步到独立存储。

恢复时先停止 backend，校验备份文件，再恢复数据库和目录，最后启动服务并调用 `/api/health`。

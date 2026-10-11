# Nginx/HTTPS 模板

1. 将 `email-platform.conf.example` 复制到 `/etc/nginx/sites-available/`。
2. 替换单域名和证书路径占位符。
3. 使用 `nginx -t` 检查配置，再建立 `sites-enabled` 链接。
4. 使用 Certbot 或企业证书管理流程申请证书。
5. 证书更新后执行 `systemctl reload nginx`。

开发环境可以使用自签名证书或 HTTP 本地测试，但不应把自签名证书用于生产。

# API接口设计

## 登录

POST /api/login

## 邮箱

GET /api/mailboxes

POST /api/mailboxes

POST /api/mailboxes/batch

PUT /api/mailboxes/{id}

DELETE /api/mailboxes/{id}

## 标签

GET /api/tags

POST /api/tags

PUT /api/tags/{id}

DELETE /api/tags/{id}

## 邮件

GET /api/mailboxes/{id}/emails

GET /api/emails/{id}

## 已读状态

PUT /api/emails/{id}/read

## 附件

GET /api/attachments/{id}/download

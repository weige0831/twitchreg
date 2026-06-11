# Twitch CDK 挂宝管理系统 API 完整文档

## 概述

- 基础 URL: `http://{HOST}:5000`
- 统一返回格式: `{"code": 0, "message": "success", "data": {...}}`
  - `code: 0` 成功，`code: 1` 失败
- 所有时间戳: UTC+8 (CST, ISO 8601)
- CORS: 全开放
- 版本: Rust (Actix-web + PostgreSQL) / FastAPI (async SQLAlchemy + SQLite) / Flask (同步 SQLAlchemy + SQLite)

---

## 认证方式

### JWT (管理员)
```
Authorization: Bearer <jwt_token>
```
- 管理员登录后获得，用于 Web UI 操作
- 默认管理员: `Admin` / `Au1125.`

### API Token (客户端)
```
Authorization: Bearer twitch-cdk-api-token-2024
```
- 用于 CDK 挖掘客户端、注册客户端
- 固定 token，不区分用户

### X-Worker-Id (可选)
```
X-Worker-Id: cdk_worker_http
```
- 部分接口需要，标识工作线程

---

## 1. 认证 Auth

### POST /api/auth/login
**认证**: 无  
**请求**:
```json
{"username": "Admin", "password": "Au1125."}
```
**响应**:
```json
{
  "code": 0, "message": "success",
  "data": {
    "access_token": "eyJ...",
    "username": "Admin",
    "expires_in": 86400
  }
}
```
**错误**: 401 `{"code": 1, "message": "Invalid credentials", "data": null}`

### POST /api/auth/register
**认证**: 无  
**请求**:
```json
{"username": "newuser", "password": "password123"}
```
**响应**:
```json
{"code": 0, "message": "User registered", "data": {"username": "newuser"}}
```

---

## 2. 账号 Accounts

### Account 对象
```json
{
  "id": 1,
  "username": "twitch_user",
  "password": "pass123",
  "email": "email@example.com",
  "auth_token": "abc123",
  "cookies": "[{...}]",
  "status": "idle|working|success|failed",
  "register_time": "2026-06-11T10:00:00+08:00",
  "last_claim_time": null,
  "current_cdk": null,
  "worker_id": null,
  "last_heartbeat": "2026-06-11T10:05:00+08:00",
  "created_at": "2026-06-10T12:00:00+08:00"
}
```

### GET /api/accounts
**认证**: JWT (admin)  
**参数**: `page`(1), `per_page`(50), `search`, `status`(idle/working/success/failed)  
**响应**:
```json
{
  "code": 0, "message": "success",
  "data": {
    "items": [{...}],
    "total": 100,
    "page": 1,
    "per_page": 50
  }
}
```

### DELETE /api/accounts
**认证**: JWT (admin)  
**请求**: `{"ids": [1, 2, 3]}`  
**响应**: `{"code": 0, "message": "success", "data": {"deleted": 3}}`

### GET /api/accounts/export
**认证**: JWT (admin)  
**返回**: CSV 文件下载 (accounts_export.csv)

### POST /api/accounts/upload
**认证**: API Token  
**请求**:
```json
{
  "username": "twitch_user",
  "password": "pass123",
  "email": "email@example.com",
  "auth_token": "oauth_token",
  "cookies": "[{\"name\":\"auth-token\",\"value\":\"xxx\",...}]"
}
```
**响应** (新增): `{"code": 0, "message": "Account created", "data": {...}}`  
**响应** (更新): `{"code": 0, "message": "Account updated", "data": {...}}`  
**注意**: 如果 username 已存在则更新密码/cookie/email，状态重置为 idle

### GET /api/accounts/get_idle
**认证**: API Token  
**Header 可选**: `X-Worker-Id`  
**逻辑**: 取状态为 idle 的最早一条，事务锁定 (BEGIN IMMEDIATE / FOR UPDATE SKIP LOCKED)，状态改为 working  
**成功响应**: `{"code": 0, "message": "success", "data": {...}}`  
**无可用**: 404 `{"code": 1, "message": "No idle accounts available", "data": null}`

### POST /api/accounts/update_status
**认证**: API Token  
**请求**:
```json
{
  "account_id": 1,
  "status": "success|working|idle|failed",
  "cdk": "XXXX-XXXX-XXXX"  // 可选
}
```
**注意**: status 传 "failed" 时自动转为 "idle"（服务器端转换）  
**响应**: `{"code": 0, "message": "success", "data": {...}}`

### POST /api/accounts/heartbeat
**认证**: API Token  
**请求**:
```json
{
  "account_id": 1,
  "worker_id": "cdk_worker_http"  // 可选
}
```
**响应**: `{"code": 0, "message": "success", "data": {"account_id": 1, "timestamp": "..."}}`

### DELETE /api/accounts/{account_id}
**认证**: JWT (admin)  
**响应**: `{"code": 0, "message": "success", "data": {"deleted": 1}}`  
**注意**: 物理删除，如果 CDK 外键无 CASCADE 则账号有 CDK 关联时删除失败

### POST /api/accounts/{account_id}/remove
**认证**: API Token  
**响应**: `{"code": 0, "message": "success", "data": {"deleted": 1}}`  
**用途**: 客户端在 Cookie 失效时调用，物理删除账号

---

## 3. CDK / 挂宝

### CDK 对象
```json
{
  "id": 1,
  "cdk_code": "XXXX-XXXX-XXXX",
  "game_name": "Minecraft",
  "status": "unused|claimed|expired",
  "claimed_by": 5,
  "claimed_time": "2026-06-11T10:30:00+08:00",
  "claimed_username": "twitch_user",
  "created_at": "2026-06-11T10:00:00+08:00"
}
```

### GET /api/cdks
**认证**: JWT (admin)  
**参数**: `page`(1), `per_page`(50), `search`, `status`(unused/claimed/expired)  
**响应**:
```json
{
  "code": 0, "message": "success",
  "data": {
    "items": [{...}],
    "total": 500,
    "page": 1,
    "per_page": 50
  }
}
```
**注意**: `claimed_username` 来自 LEFT JOIN accounts

### DELETE /api/cdks
**认证**: JWT (admin)  
**请求**: `{"ids": [1, 2, 3]}`  
**响应**: `{"code": 0, "message": "success", "data": {"deleted": 3}}`

### POST /api/cdks/import
**认证**: JWT (admin)  
**请求**:
```json
{
  "items": [
    {"cdk_code": "XXXX-XXXX-XXXX", "game_name": "Minecraft"},
    {"cdk_code": "YYYY-YYYY-YYYY", "game_name": "Minecraft"}
  ]
}
```
**响应**: `{"code": 0, "message": "success", "data": {"imported": 2}}`  
**注意**: 已存在的 cdk_code 自动跳过

### POST /api/cdks/claim
**认证**: API Token  
**请求**:
```json
{
  "cdk_code": "XXXX-XXXX-XXXX",
  "game_name": "Minecraft",
  "account_id": 1
}
```
**逻辑**:
- 如果 cdk_code 已存在 → 直接返回已有记录
- 如果不存在 → 插入新 CDK (status=claimed)，同时更新 account 的 current_cdk 和 last_claim_time
**响应**: `{"code": 0, "message": "success", "data": {...}}`
**错误**: cdk_code 为空时 400

### POST /api/cdks/dedup
**认证**: JWT (admin)  
**逻辑**: 按 cdk_code 分组，保留最早的一条，删除其余重复  
**响应**: `{"code": 0, "message": "success", "data": {"removed": 10}}`

### PUT /api/cdks/{cdk_id}/status
**认证**: JWT (admin)  
**请求**: `{"status": "expired"}` (unused/claimed/expired)  
**响应**: `{"code": 0, "message": "success", "data": {...}}`

### GET /api/cdks/export
**认证**: JWT (admin)  
**参数**: `count` (必填，1 <= count <= 10000)  
**行为**: 删除最新的 count 条 CDK，同时删除关联的 accounts，返回 TXT 文件  
**返回**: `Content-Type: text/plain`，文件名 `cdks_{N}.txt`  
**内容**: 每行一个 cdk_code  
**错误**: count <= 0 时 400  
**重要**: 此接口会物理删除 CDK 和关联账号

---

## 4. Workers 工作线程

### Worker 对象
```json
{
  "id": 1,
  "worker_name": "w1_abc12345",
  "worker_type": "cdk",
  "status": "online|offline",
  "last_heartbeat": "2026-06-11T10:05:00+08:00",
  "created_at": "2026-06-11T09:00:00+08:00"
}
```

### GET /api/workers
**认证**: JWT (admin)  
**参数**: `page`(1), `per_page`(50)  
**排序**: last_heartbeat DESC  
**响应**:
```json
{
  "code": 0, "message": "success",
  "data": {
    "items": [{...}],
    "total": 10,
    "page": 1,
    "per_page": 50
  }
}
```

### POST /api/workers/heartbeat
**认证**: 无（Rust 版）/ API Token（FastAPI 版）  
**请求**:
```json
{
  "worker_name": "w1_abc12345",
  "worker_type": "cdk"
}
```
**逻辑**: worker_name 已存在则更新 last_heartbeat 和 status=online，不存在则插入  
**响应**: `{"code": 0, "message": "success", "data": {...}}`

---

## 5. Dashboard 仪表盘

### GET /api/dashboard/stats
**认证**: JWT (admin)  
**响应**:
```json
{
  "code": 0, "message": "success",
  "data": {
    "accounts": {
      "total": 1500,
      "idle": 200,
      "working": 50,
      "success": 1100,
      "failed": 150
    },
    "cdks": {
      "total": 500,
      "claimed": 480,
      "unused": 20
    },
    "workers": {
      "total": 5,
      "online": 3
    }
  }
}
```

---

## 6. 页面路由 (HTML)

| 路径 | 方法 | 返回 |
|------|------|------|
| `/` | GET | 登录页 |
| `/dashboard` | GET | 仪表盘（ECharts 饼图） |
| `/cdks` | GET | CDK 管理页（导入/导出/列表/去重） |
| `/workers` | GET | Worker 管理页 |
| `/static/*` | GET | 静态资源 (JS/CSS/图标) |

---

## 7. 后台调度器

| 机制 | 间隔 | 行为 |
|------|------|------|
| 账号恢复 | 60s | status=working 且 last_heartbeat 超过 600s → 重置为 idle, worker_id=NULL |
| Worker 标记 | 60s | Worker last_heartbeat 超过 300s → status=offline |

---

## 8. 典型客户端流程

```
1. POST /api/workers/heartbeat                    # 注册 worker
2. GET  /api/accounts/get_idle                     # 获取空闲账号
      (循环，直到没有空闲账号)
3. POST /api/accounts/update_status               # 更新状态 (failed → idle 复用)
4. POST /api/cdks/claim                           # 上报领取到的 CDK
      (cdk_code, account_id → 自动创建/返回 CDK)
5. 回到步骤 2
```

**Cookie 失效时**: 应调用 `POST /api/accounts/update_status {"account_id": X, "status": "failed"}` 标记为 idle 等待新 Cookie，**不要调用 remove 物理删除**。

---

## 9. 错误码汇总

| HTTP | code | 场景 |
|------|------|------|
| 200 | 0 | 成功 |
| 400 | 1 | 参数缺失/无效 |
| 401 | 1 | 认证失败/未登录 |
| 404 | 1 | 资源不存在 |
| 500 | 1 | 服务器错误 |

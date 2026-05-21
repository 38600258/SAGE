# 变更日志 (Changelog)

> 只增不改。按版本号组织。遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/) 格式。

## [Unreleased]

### Added
- T-002: 订单列表 Cursor 分页 API（开发中）

---

## [0.2.0] - 2026-05-18

### Added
- T-001: 用户注册接口（`POST /api/v1/auth/register`）
- T-001: 用户登录接口（`POST /api/v1/auth/login`）
- T-001: JWT 认证中间件（Access Token 15min + Refresh Token 7d）
- T-001: 统一错误响应格式 `{ code, data, message }`
- T-001: ESLint + Prettier 代码规范配置

### Security
- T-001: 密码使用 bcrypt (cost=12) 哈希存储
- T-001: Refresh Token 使用 httpOnly + Secure Cookie

---

## [0.1.0] - 2026-05-10

### Added
- 项目初始化：Express.js + TypeScript + Prisma 脚手架
- PostgreSQL 数据库连接与基础配置
- Docker Compose 开发环境配置
- 基础目录结构（Controller / Service / Repository 分层）

# 变更日志 (Changelog)

> 只增不改。按版本号组织。遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/) 格式。
> 注：历史条目原本只记录日期，迁移到单行标题格式时用 `00:00:00` 作为回溯补齐时间。

## [0.2.1] 📝 Process 沉淀跨项目 SAGE 实战经验 (T-002) - 2026-05-23 20:22:40
- 沉淀跨项目 SAGE 实战经验：版本号判定规则、完整时间戳记录、独立盲审绝对路径规则、收尾补丁版本归属。
- 更新任务模板，要求任务元数据和各阶段标题记录带时区的完整时间戳。
- 更新 reviewer/closer 提示词，明确盲审必须使用 `REPO_ROOT` / `TASK_PATH` 绝对路径，版本号以独立交付物为边界。
- 将 `docs/project/HANDOVER-GUIDE.md` 去业务化，改为 SAGE 通用项目交接指南。
- 修复 `scripts/sage_linter.py` 对带时间阶段标题、标题括号和盲审小标题的兼容性。
- 新增 `--allow-template-changes`，允许模板/流程规范任务显式放行模板变更。

---

## [0.2.0] ✨ Feature 用户认证与基础工程规范 (T-001) - 2026-05-18 00:00:00
- T-001: 用户注册接口（`POST /api/v1/auth/register`）
- T-001: 用户登录接口（`POST /api/v1/auth/login`）
- T-001: JWT 认证中间件（Access Token 15min + Refresh Token 7d）
- T-001: 统一错误响应格式 `{ code, data, message }`
- T-001: ESLint + Prettier 代码规范配置
- T-001: 密码使用 bcrypt (cost=12) 哈希存储
- T-001: Refresh Token 使用 httpOnly + Secure Cookie

---

## [0.1.0] ✨ Feature 项目初始化与基础脚手架 (INIT) - 2026-05-10 00:00:00
- 项目初始化：Express.js + TypeScript + Prisma 脚手架
- PostgreSQL 数据库连接与基础配置
- Docker Compose 开发环境配置
- 基础目录结构（Controller / Service / Repository 分层）

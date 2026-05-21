# 架构总览

> 本文件提供项目的顶层架构地图。
> 详细规范参见 [development-standards.md](docs/guides/development-standards.md) 第二章。

## 1. 系统架构

```
                        ┌─────────────┐
                        │   Nginx     │
                        │  (反向代理)  │
                        └──────┬──────┘
                               │
                        ┌──────▼──────┐
                        │  Express.js │
                        │  API Server │
                        │  :3000      │
                        └──────┬──────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
       ┌──────▼──────┐ ┌──────▼──────┐ ┌───────▼──────┐
       │ PostgreSQL  │ │   Redis     │ │  外部服务     │
       │ (主数据库)   │ │ (缓存/会话) │ │ (支付网关等)  │
       │ :5432       │ │ :6379      │ │              │
       └─────────────┘ └────────────┘ └──────────────┘
```

## 2. 目录结构与职责

| 路径 | 类型 | 职责 |
|------|------|------|
| `src/controllers/` | 入口层 | 接收 HTTP 请求，参数校验，调用 Service，返回响应 |
| `src/services/` | 业务层 | 核心业务逻辑编排，事务管理 |
| `src/repositories/` | 数据层 | 数据库 CRUD 操作，Prisma 查询封装 |
| `src/models/` | 类型层 | Prisma Schema、DTO 定义 |
| `src/middlewares/` | 中间件 | 认证、错误处理、日志、限流 |
| `src/utils/` | 工具 | 通用工具函数（加密、日期、分页等） |
| `src/types/` | 类型 | TypeScript 类型定义、错误码枚举 |
| `tests/` | 测试 | 单元测试 + 集成测试 |

**SAGE 工作流目录**（项目管理层，非业务代码）：

| 路径 | 类型 | 职责 |
|------|------|------|
| `AGENTS.md` | 导航 | 智能体入口（≤50行），指向各领域文档 |
| `ARCHITECTURE.md` | 文档 | 本文件，顶层架构地图 |
| `CHANGELOG.md` | 文档 | 变更日志（只增不改） |
| `templates/` | 模板 | 任务/ADR/PRD 模板（神圣不可侵犯） |
| `docs/guides/` | 规范 | 开发规范、设计原则 |
| `docs/project/` | 项目 | 看板、模式库、决策日志、交接指南 |
| `docs/product/` | 产品 | PRD（产品需求文档） |
| `docs/references/` | 参考 | 业务规则、API 参考、外部资料 |
| `scripts/` | 工具 | sage_linter 等验证脚本 |

## 3. 分层架构

```
┌──────────────────────────────────────┐
│     Controller 层 (路由 + 参数校验)   │  ← HTTP 请求入口
├──────────────────────────────────────┤
│     Middleware 层 (认证/日志/限流)     │  ← 横切关注点
├──────────────────────────────────────┤
│     Service 层 (业务逻辑编排)         │  ← 核心业务
├──────────────────────────────────────┤
│     Repository 层 (数据访问)          │  ← Prisma ORM
├──────────────────────────────────────┤
│     Types / Config 层 (类型与配置)    │  ← 基础设施
└──────────────────────────────────────┘
      ↑ 依赖方向：自上而下，禁止反向
```

**依赖规则**：
- Controller → Service → Repository → Types ✅
- Repository → Service ❌ **禁止反向依赖**
- Service → Controller ❌ **禁止反向依赖**
- 任何层 → Utils/Types ✅ **工具层可被任何层引用**

## 4. 数据流

以「用户注册」为例：

```
1. POST /api/v1/auth/register (JSON body)
      │
      ▼
2. AuthController.register()
   - 参数校验 (express-validator)
   - 调用 AuthService
      │
      ▼
3. AuthService.register()
   - 检查邮箱唯一性 (UserRepository)
   - bcrypt 哈希密码
   - 创建用户 (UserRepository)
   - 生成 JWT + Refresh Token
      │
      ▼
4. UserRepository.create()
   - Prisma: INSERT INTO users
      │
      ▼
5. 返回 { code: 0, data: { accessToken, user }, message: "注册成功" }
```

## 5. 已知局限

- 🔴 订单表缺少索引，全表扫描在数据量增长后会成为瓶颈（TD-002）
- 🟡 缺少统一错误码枚举，各模块自行定义（TD-003，已排入 T-003）
- 🟡 尚未接入 Redis 缓存，高频查询直接打数据库
- 🟡 尚未实现 API 限流（Rate Limiting）

> 详细技术债追踪参见 [PROJECT_BOARD.md](docs/project/PROJECT_BOARD.md)

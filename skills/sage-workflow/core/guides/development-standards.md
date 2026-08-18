# 开发规范 (Development Standards)

> 状态：[CURRENT]
> 适用对象：智能体 / AI Agent / 人类工程师
> 核心原则：安全优先、防御性编程、测试驱动

---

## 一、核心理念

### 1.1 文档驱动开发

所有开发必须遵循文档驱动流程：

```
1. 任务挂载 → 读取任务看板，物理复制任务模板创建 ACTIVE_TASK_T-XXX.md
2. 证据先行 → 先写失败测试，再实现代码
3. 精准实现 → 关联任务编号，代码简洁
4. 真理同步 → 更新 CHANGELOG、任务看板、相关文档
```

---

## 二、项目架构

### 2.1 技术栈

<!-- CUSTOMIZE: 填写项目使用的技术栈 -->

| 层级 | 技术 | 版本 |
|------|------|------|
| 语言 | <!-- e.g. Python / TypeScript --> | <!-- e.g. 3.12 --> |
| 框架 | <!-- e.g. FastAPI / Next.js --> | <!-- e.g. 0.115 --> |
| 数据库 | <!-- e.g. PostgreSQL / SQLite --> | <!-- e.g. 16 --> |
| 包管理 | <!-- e.g. uv / pnpm --> | <!-- e.g. latest --> |
| 代码检查 | <!-- e.g. ruff / eslint --> | <!-- e.g. latest --> |
| 测试框架 | <!-- e.g. pytest / vitest --> | <!-- e.g. latest --> |

### 2.2 项目结构

<!-- CUSTOMIZE: 填写项目目录结构 -->

```
project-root/
├── src/                  # 源代码
│   ├── ...               # <!-- 按项目实际结构填写 -->
│   └── ...
├── tests/                # 测试
├── scripts/              # 工具脚本
├── docs/                 # 项目文档（遵循方法论目录布局）
├── templates/            # 文档模板
└── ...
```

### 2.3 分层架构与依赖方向

<!-- CUSTOMIZE: 填写项目的分层架构约束 -->

```
Types → Config → Repository → Service → UI/API
          ↓ 依赖方向（单向，禁止反向引用）
```

> 跨层反向依赖直接报错。如有检查脚本，填写运行方式：
> ```bash
> # <!-- e.g. python scripts/check_deps.py -->
> ```

### 2.4 构建与运行

<!-- CUSTOMIZE: 填写项目的构建和运行命令 -->

```bash
# 安装依赖
# <!-- e.g. uv sync / pnpm install -->

# 开发模式运行
# <!-- e.g. uv run python -m app / pnpm dev -->

# 生产构建
# <!-- e.g. uv run python -m build / pnpm build -->
```

---

## 三、代码规范

### 2.1 Python 风格

- 遵循 PEP 8
- 使用 4 空格缩进
- 使用类型注解
- 编写文档字符串

```python
def get_inventory(product_id: int) -> dict[str, Any]:
    """获取指定商品的库存信息。
    
    Args:
        product_id: 商品 ID
        
    Returns:
        包含库存信息的字典
    """
    ...
```

### 2.2 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块 | 小写下划线 | `task_service.py` |
| 类 | 大驼峰 | `TaskService` |
| 函数/方法 | 小写下划线 | `create_task()` |
| 常量 | 全大写下划线 | `MAX_RETRIES` |
| 变量 | 小写下划线 | `task_id` |

### 2.3 代码检查

```bash
# 检查
ruff check .

# 自动修复
ruff check . --fix

# 格式化
ruff format .
```

---

## 三、脚本规范

### 3.1 结构模板

```python
#!/usr/bin/env python3
"""脚本功能简述。

Usage:
    python scripts/xxx.py --param value
"""

import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(description="功能描述")
    parser.add_argument("--param", required=True, help="参数说明")
    args = parser.parse_args()
    
    # 实现
    result = {"status": "success", "data": {}}
    
    # 输出
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

### 3.2 输出规范

- **数据输出**：JSON 格式，便于程序解析
- **展示输出**：Markdown 格式，便于用户阅读
- **错误输出**：写入 stderr，退出码非 0

```python
# 成功
print(json.dumps({"status": "success", "data": {...}}))

# 失败
print(json.dumps({"status": "error", "message": "..."}), file=sys.stderr)
sys.exit(1)
```

### 3.3 原子性

- 每个脚本职责单一
- 幂等执行（可重复运行）
- 无副作用或明确声明副作用

---

## 五、测试规范

### 4.1 测试结构

```
tests/
├── conftest.py           # 共享 fixtures
├── test_<module>.py      # 按模块组织
└── ...
```

### 4.2 测试命名

- 文件：`test_<module>.py`
- 类：`Test<Feature>`
- 方法：`test_<behavior>()`

### 4.3 运行测试

```bash
# 运行单个模块测试
pytest tests/test_<module>.py

# 全量测试（排除慢速集成测试）
pytest -k "not integration"

# 详细输出
pytest -v
```

---

## 六、Git 规范

### 5.1 提交格式

```
<类型>(<范围>): <描述>

类型: feat | fix | docs | refactor | test | chore
```

**示例**：

```
feat(auth): 添加 OAuth2 认证流程
fix(api): 修复超时重试逻辑
docs: 更新架构设计文档
refactor(service): 重构状态转换逻辑
```

提交标题必须满足以下硬约束：

- 标题首行必须符合 Conventional Commit 格式：`type(scope): 中文描述` 或 `type: 中文描述`。
- 描述部分必须包含至少一个中文字符（CJK U+4E00-9FFF）；`type` 和 `scope` 可保留英文。
- `Merge` / `Revert` / `fixup!` / `squash!` 等系统或整理类提交可豁免。
- 该规则由 `.githooks/commit-msg` 与 `python scripts/sage_linter.py --check-commit-msg <提交信息文件>` 物理拦截。

### 5.2 提交整洁度与原子性

- **合并同类项**：同一个需求或同一个逻辑修复产生的多次零散修改，在推送合并前应当使用 `git commit --amend` 补充提交，或通过 Squash 将其压缩为一次完整提交。禁止在主分支历史中堆砌诸如 "fix typo", "update again" 等毫无语义的细碎补丁。

### 5.3 分支命名

| 类型 | 格式 |
|------|------|
| L0 修复/文档/整理 | `fix/l0-name` / `docs/l0-name` / `chore/l0-name` / `style/l0-name` |
| 功能（推荐） | `feat/t-XXX-name` |
| 功能（兼容旧模板） | `feature/T-XXX-name` |
| 修复 | `fix/t-XXX-name` |
| 文档 | `docs/t-XXX-name` |
| 整理 | `chore/t-XXX-name` |
| 重构 | `refactor/t-XXX-name` |

---

## 七、文档规范

### 6.1 文档目录

| 目录 | 内容 |
|------|------|
| `docs/architecture/` | 架构设计、能力全景图 |
| `docs/product/` | PRD、用户故事 |
| `docs/project/` | 任务看板、活跃任务、模式库 |
| `docs/guides/` | 开发规范、安全规范 |
| `docs/references/` | 业务规则参考、API 参考 |
| `templates/` | 文档模板（神圣不可侵犯） |

### 6.2 文档格式

- 使用 Markdown 格式
- 标题层级不跳级
- 代码块指定语言
- 表格对齐

### 6.3 版本控制与变更日志

- **主版本号 (Major)**：大架构升级、破坏性变更时更新。
- **次版本号 (Minor)**：新功能添加时更新。
- **修订号 (Patch)**：Bug 修复和小更新时更新。
- 所有变更均必须记录到 `CHANGELOG.md`。
- 一个独立功能、修复、流程规则或文档口径修改必须对应一次独立版本号递增；禁止把多个相互独立的变更堆叠在同一个版本号下。
- 同一任务内的计划修正、审查 BLOCK 修复、收尾补丁或纯格式修正不单独增加版本号，应合入该任务已有版本条目。
- 版本标题建议使用单行二级标题承载版本号、变更类型、标题、任务号和完整时间，格式为 `## [X.Y.Z] ✨ Feature 功能提炼标题 (T-XXX) - YYYY-MM-DD HH:mm:ss`。
- 任务文档中的开始时间、结束时间、阶段标题时间必须使用带时区的完整时间戳，格式为 `YYYY-MM-DDTHH:mm:ss+08:00`；禁止只记录到日期。

**版本号判定规则**：

| 场景 | 是否递增版本号 | 记录方式 |
|------|----------------|----------|
| 新任务交付一个独立功能、修复、流程规则或文档口径修改 | 是 | 新增一个版本条目，标题包含任务号 |
| 同一任务内的计划修正、审查 BLOCK 修复、收尾补丁 | 否 | 合入该任务当前版本条目，并在 TASK 中记录修正时间与原因 |
| 同一任务执行中发现另一个独立问题，且需要扩大目标或新增交付物 | 是，且应新建/拆分任务 | 新任务使用下一个任务号和下一个版本号 |
| 事后拆分历史堆叠版本 | 按独立变更补正 | 在 `CHANGELOG.md` 注明为回溯补正，不改 Git 历史 |
| 纯错别字、格式、链接修正且不改变事实或规则 | 否 | 合入当前任务或最近相关版本条目 |

**递增流程**：

1. 先判断变更是否是“独立交付物”，而不是当前任务的返工、审查修复或收尾补丁。
2. 若是独立交付物，选择下一个语义化版本号，并在 `CHANGELOG.md` 顶部新增条目。
3. 若不是独立交付物，将说明合入当前任务对应版本条目，不新增版本号。
4. 在 TASK `5.4 自检清单` 的“版本号已更新”项写明使用的版本号，若未递增则说明合入原因。

**CHANGELOG 格式规范**：

```markdown
## [X.Y.Z] ✨ Feature 功能提炼标题 (T-XXX) - YYYY-MM-DD HH:mm:ss
- **变更点**：描述具体变更...

## [X.Y.Z] 🐛 BugFix 问题修复标题 (T-XXX) - YYYY-MM-DD HH:mm:ss
- **修复内容**：描述修复...
```

---

## 八、安全规范

### 7.1 敏感信息

- 禁止在代码中硬编码密钥、密码
- 使用环境变量或 `.env` 文件
- `.env` 已在 `.gitignore` 中

### 7.2 操作边界

| 限制 | 策略 |
|------|------|
| 文件访问 | 仅限项目目录 |
| 脚本执行 | 仅限 `scripts/` 下 |
| 敏感信息 | 禁止输出 |

### 7.3 高危操作确认

对于以下类型的操作，智能体必须获得人类的明确确认后方可执行：

- 数据删除（不可逆操作）
- 生产环境部署
- 外部 API 调用（涉及费用或副作用）
- 数据库 Schema 变更

---

## 九、部署与环境规范

### 9.1 环境隔离

<!-- CUSTOMIZE: 填写项目的环境分层 -->

| 环境 | 用途 | 地址/路径 |
|------|------|-----------|
| 开发 (Dev) | 本地开发与调试 | <!-- e.g. localhost:3000 --> |
| 测试 (Staging) | 集成测试与预发布 | <!-- e.g. staging.example.com --> |
| 生产 (Production) | 正式用户环境 | <!-- e.g. app.example.com --> |

### 9.2 部署命令

<!-- CUSTOMIZE: 填写项目的部署命令 -->

```bash
# 部署到测试环境
# <!-- e.g. ./deploy.sh staging -->

# 部署到生产环境（必须获得人类授权）
# <!-- e.g. ./deploy.sh production -->
```

### 9.3 部署红线

- 🛑 禁止将本地数据库文件上传到生产环境
- 🛑 禁止将 `.env` 文件提交到版本控制
- 🛑 禁止在生产环境直接执行数据库迁移（须通过迁移脚本）
- 🛑 部署必须获得人类明确授权

<!-- CUSTOMIZE: 补充项目特有的部署红线 -->

---

## 十、框架集成规范

<!-- CUSTOMIZE: 填写项目使用的 Agent 框架集成规范 -->
<!-- 如果使用 Antigravity 2.0，填写 Skills/Rules/Hooks 规范 -->
<!-- 如果使用 Cursor，填写 .cursorrules 规范 -->
<!-- 如果使用其他框架，填写对应规范 -->

### 10.1 智能体指令文件

| 框架 | 指令文件 | 位置 |
|------|---------|------|
| <!-- e.g. Antigravity --> | <!-- e.g. AGENTS.md --> | <!-- e.g. 项目根目录 --> |

### 10.2 渐进式加载

| 层级 | 内容 | 大小建议 |
|------|------|----------|
| T1 入口 | 项目概述 + 构建命令 + 指向细分文档的路径 | ≤ 50 行 |
| T2 领域 | 各领域规范文件 | ≤ 500 行/文件 |
| T3 细节 | API 参考、Schema 定义、历史归档 | 按需加载 |

---

## 十一、检查清单

### 发布前检查

- [ ] 代码通过静态检查（<!-- e.g. ruff check / eslint -->）
- [ ] 核心模块测试通过
- [ ] 相关文档已同步更新
- [ ] CHANGELOG 已更新
- [ ] 任务看板状态已更新
- [ ] 版本号已更新

### 代码提交检查

- [ ] 提交信息格式正确
- [ ] 关联任务编号
- [ ] 无敏感信息泄露

---

## 十二、工作流状态标记

任务在六阶段流水线中的状态标记规范：

```
⚪ 待命        — 任务已创建未启动
📋 初始化中    — 阶段一执行中
🔍 评审中      — 阶段二执行中
🔴 Red Phase  — 编写失败测试中（阶段三）
🟢 Green Phase — 实现代码中（阶段三）
🔵 代码审查中  — 阶段四执行中
📦 收尾中      — 阶段五执行中
🚀 部署中      — 阶段六执行中
✅ 已完成      — 任务关闭
🔙 回滚至 XXX  — 流程回退（必须注明目标阶段）
```

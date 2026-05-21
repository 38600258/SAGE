---
description: 生产服务器部署 (Production Deployment)
---

> **核心目标**：安全、可靠地将经过充分验证的 `dev` 分支代码合并至主分支（`main`），并部署到正式的云端生产环境。
> ⚠️ **高危警告**：生产环境部署必须获得用户的**明确祈使句授权**。绝不允许 AI 私自触发发版流程。

### 步骤 1：部署前置检查 (Pre-Deploy Checklist)
1. 确认当前 `dev` 分支工作区干净，无任何未提交的代码变更。
2. 运行最后一次静态检查与测试，确保安全防线未被破坏：
   - `uv run ruff check .`
   - `uv run pytest -k "not perf" -v` （日常发布跳过极度耗时的压测和全量集成测试）
3. 确认所有即将发布的变更均已记录在 `CHANGELOG.md` 中，且版本号已通过 `bump_version.py` 完成了层级升级。
4. 确认在先前的开发验证阶段，代码已经通过了 WSL 子系统环境的跨平台兼容性验证。

### 步骤 2：合并主分支 (Merge to Main)
1. 切换到主干分支（`main`）：`git checkout main`
2. 将 `dev` 分支的修改合并入主分支：`git merge dev --no-ff -m "chore(deploy): 合并 dev 至 main 准备发版"`
   - *注意：如果在主分支产生冲突，应立即停止，并向用户报告要求介入解决。*
3. **(可选)** 按照当前新版本号，为主分支打上版本标签（例：`git tag -a v7.8.2 -m "Release v7.8.2"`）。
   - *说明：合并完成后，继续保持在 `main` 分支进行打包发版，确保投递给服务器的代码包与主干发布版本完全一致。*

### 步骤 3：打包与隔离防线自检 (Safety & Isolation Check)
> 🛑 **红线自检**：在执行部署命令前，必须在思考过程中再次进行最后确认：接下来的操作**绝对不会**将本地 `db/` 目录（尤其是 `memory.db`）打包上传至生产服务器。一旦覆盖将造成灾难性的客户数据丢失！
- 确认将使用的是官方白名单部署流水线工具：`.\dev\scripts\deploy.ps1 -Target prod`（该工具已硬编码排除 `db/`）。

### 步骤 4：正式发版上云 (Deploy to Production)
1. 再次确认已获得用户的上线授权口令（如：“请发到生产区”、“同意发版”）。
2. 执行一键生产部署流：
   ```powershell
   .\dev\scripts\deploy.ps1 -Target prod
   ```
   *说明：此脚本内嵌了打包、白名单过滤、免密 `scp` 跨平台推流以及云端强制执行 `uv sync` 进行依赖重装的过程。*
3. **客观证据**：必须向用户展示部署脚本运行成功并退出（Exit Code 0）的终端日志截图/输出信息。

### 步骤 5：云端数据库版本迁移 (Database Migration)
> ⚠️ **触发条件**：仅当本次发布包含对 `db/schema.sql` 的修改，或业务需求要求更改数据库结构时执行。否则跳过此步。
1. **提取增量**：梳理出自上次部署以来新增的 SQL 表结构变更或数据迁移语句。
2. **单独授权**：向用户展示即将对生产数据库执行的增量 SQL，并获取明确的“同意执行数据库变更”授权。
3. **远端备份**：在执行任何 SQL 变更前，**必须**通过 SSH 在生产服务器上对数据库文件进行物理备份，附加时间戳（例如 `ssh root@115.190.15.128 "cp /root/.openclaw/workspace/skills/cj-claw/db/memory.db /root/.openclaw/workspace/skills/cj-claw/db/memory_backup_$(date +%Y%m%d%H%M%S).db"`）。
4. **远端执行**：使用 SSH 在远端生产服务器上独立执行 SQL（如通过标准流输入或调用云端专用迁移脚本）。**绝对禁止通过上传覆盖本地 `.db` 文件来升级数据库。**
   *(示例：`ssh root@115.190.15.128 "sqlite3 /root/.openclaw/workspace/skills/cj-claw/db/memory.db < /tmp/migration.sql"`)*
5. **完整性校验**：执行完成后，必须在远端探明数据库的完整性并确认新表结构已生效（例如查询 `PRAGMA integrity_check;` 或验证新字段）。**如果查出损坏，立即用刚刚的备份文件覆盖还原。**

### 步骤 6：部署后拨测与生效 (Post-Deploy Validation)
1. 探针拨测：在生产服务器中执行只读的健康检查探针，验证连通性：
   ```powershell
   ssh root@115.190.15.128 "cd /root/.openclaw/workspace/skills/cj-claw && uv run python scripts/healthcheck.py"
   ```
2. **强制生效**：明确提醒用户触发**配置重载红线**。更新不是即时生效的，必须在数字员工交互端（企微/微信/CLI）发送 `/new` 指令，强制销毁旧记忆并建立新会话，以便引擎挂载刚上线的最新 `SKILL.md` 和底层业务代码。
3. **切回开发主干**：确认发版流程及拨测全部顺利结束后，**必须执行 `git checkout dev`** 将本地工作区切回开发分支，以维持环境干净并准备承接下一个任务。

### 🔙 回滚规则
- **触发条件**：拨测阶段发现生产服务器大量报错、服务瘫痪，或部署文件损毁。
- **回滚动作**：
  1. 立即使用 Git 撤回主分支的合并操作：`git reset --hard HEAD~1`。
  2. 使用相同部署通道将上一个已知稳定版本的代码包回滚至服务器。
  3. 报告灾难详情，锁定生产区，要求退回 `/3dev` 和 `/4codereview` 审查防线彻查原因。

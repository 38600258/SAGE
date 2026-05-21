#!/bin/bash
# Gemini CLI Worker — 桥接 Hermes Kanban 与 Gemini CLI
#
# 原理：
#   1. 轮询 Kanban 中 assignee=gemini 且 status=ready 的任务
#   2. 提取任务上下文（task_doc, branch, test_cmd 等）
#   3. 构造 prompt 并启动 gemini CLI 执行编码
#   4. 根据退出码回写 kanban_complete 或 kanban_block
#
# 用法：
#   export GOOGLE_API_KEY="your-key"
#   bash scripts/gemini_worker.sh
#
# 前置条件：
#   - npm install -g @google/gemini-cli@latest
#   - hermes CLI 可用

set -euo pipefail

HERMES=${HERMES_BIN:-hermes}
HERMES_PROFILE=${HERMES_PROFILE:-coder}
POLL_INTERVAL=${POLL_INTERVAL:-30}
GEMINI_BIN=${GEMINI_BIN:-gemini}

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# 检查依赖
for cmd in $HERMES $GEMINI_BIN jq; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "❌ 缺少依赖: $cmd"
        exit 1
    fi
done

log "🚀 Gemini Worker 启动 (轮询间隔: ${POLL_INTERVAL}s)"

while true; do
    # 查找 assignee=gemini 且状态为 ready 的任务
    # 注意: 这里依赖 hermes kanban list 的输出格式，可能需要根据实际版本调整
    TASK_ID=$($HERMES -p $HERMES_PROFILE kanban list --assignee gemini --status ready --format json 2>/dev/null \
        | jq -r '.[0].id // empty' 2>/dev/null || true)

    if [ -z "$TASK_ID" ]; then
        sleep $POLL_INTERVAL
        continue
    fi

    log "📋 拾取任务: $TASK_ID"

    # 获取任务详情
    TASK_JSON=$($HERMES -p $HERMES_PROFILE kanban show "$TASK_ID" --format json 2>/dev/null)
    WORKSPACE=$(echo "$TASK_JSON" | jq -r '.workspace // empty')
    TASK_DOC=$(echo "$TASK_JSON" | jq -r '.metadata.task_doc // empty')
    BRANCH=$(echo "$TASK_JSON" | jq -r '.metadata.branch // empty')
    TEST_CMD=$(echo "$TASK_JSON" | jq -r '.metadata.test_cmd // "echo no-test-cmd"')
    LINT_CMD=$(echo "$TASK_JSON" | jq -r '.metadata.lint_cmd // "echo no-lint-cmd"')
    RISK_LEVEL=$(echo "$TASK_JSON" | jq -r '.metadata.risk_level // "L2"')
    TITLE=$(echo "$TASK_JSON" | jq -r '.title // "未知任务"')

    # 提取项目目录（从 workspace 字段，格式: "dir:/path/to/project"）
    PROJECT_DIR="${WORKSPACE#dir:}"
    if [ -z "$PROJECT_DIR" ] || [ ! -d "$PROJECT_DIR" ]; then
        log "❌ 无法定位项目目录: $WORKSPACE"
        $HERMES -p $HERMES_PROFILE kanban block "$TASK_ID" --reason "Gemini Worker 无法定位项目目录: $WORKSPACE"
        continue
    fi

    log "📂 项目: $PROJECT_DIR | 分支: $BRANCH | 风险: $RISK_LEVEL"

    # 切换到项目目录和分支
    cd "$PROJECT_DIR"
    if [ -n "$BRANCH" ]; then
        git checkout "$BRANCH" 2>/dev/null || true
    fi

    # 构造 Prompt
    PROMPT="你是一个编码实现智能体。请严格按照以下任务文档执行 Red-Green 循环编码。

## 任务信息
- 任务: $TITLE
- 任务文档: $TASK_DOC
- 分支: $BRANCH
- 测试命令: $TEST_CMD
- Lint 命令: $LINT_CMD

## 执行步骤
1. 读取任务文档 '$TASK_DOC'，理解实施计划
2. 如果有评审修正记录（2.1节），将修正纳入执行计划
3. 按照原子步骤逐步实现：
   a. 先写测试（Red Phase）
   b. 再写代码（Green Phase）
   c. 每步完成后运行: $TEST_CMD
   d. 如果测试失败，自动修复（最多重试 3 次）
4. 全部步骤完成后执行验证：
   a. $TEST_CMD -v  （确保全部通过）
   b. $LINT_CMD --fix <修改的文件>  （自动修复）
   c. $LINT_CMD <修改的文件>  （确认清洁）
5. 更新任务文档中的进度追踪和证据链（3.1 和 3.2 节）

## 输出要求
完成后，在项目根目录创建文件 '.gemini-result.json'，内容为:
{
  \"status\": \"success\" 或 \"failed\",
  \"changed_files\": [\"file1.py\", ...],
  \"tests_passed\": 数字,
  \"lint_clean\": true/false,
  \"summary\": \"一句话总结\",
  \"failure_reason\": \"如果失败，说明原因\"
}

## 重要规则
- 所有分析和注释使用中文
- 严格按照计划步骤执行，不擅自扩展范围
- 如果遇到计划缺陷或外部依赖问题，在 .gemini-result.json 中标记 failed 并说明原因"

    # 执行 Gemini CLI
    log "🤖 启动 Gemini CLI..."
    GEMINI_EXIT=0
    $GEMINI_BIN -p "$PROMPT" --non-interactive 2>&1 | tee "/tmp/gemini-worker-${TASK_ID}.log" || GEMINI_EXIT=$?

    # 读取结果
    RESULT_FILE="$PROJECT_DIR/.gemini-result.json"
    if [ -f "$RESULT_FILE" ]; then
        STATUS=$(jq -r '.status' "$RESULT_FILE")
        SUMMARY=$(jq -r '.summary' "$RESULT_FILE")
        CHANGED_FILES=$(jq -c '.changed_files' "$RESULT_FILE")
        TESTS_PASSED=$(jq -r '.tests_passed' "$RESULT_FILE")
        LINT_CLEAN=$(jq -r '.lint_clean' "$RESULT_FILE")
        FAILURE_REASON=$(jq -r '.failure_reason // empty' "$RESULT_FILE")

        if [ "$STATUS" = "success" ]; then
            log "✅ 编码成功: $SUMMARY"

            if [ "$RISK_LEVEL" = "L3" ]; then
                $HERMES -p $HERMES_PROFILE kanban block "$TASK_ID" \
                    --reason "[L3 门禁] 编码验证已完成 ($SUMMARY)。请人工检查代码后，手动 complete 放行。"
            else
                $HERMES -p $HERMES_PROFILE kanban complete "$TASK_ID" \
                    --summary "Gemini 编码完成。${TESTS_PASSED} 个测试通过。$SUMMARY" \
                    --metadata "{\"changed_files\":$CHANGED_FILES,\"tests_passed\":$TESTS_PASSED,\"lint_clean\":$LINT_CLEAN,\"executor\":\"gemini-cli\"}"
            fi
        else
            log "❌ 编码失败: $FAILURE_REASON"
            $HERMES -p $HERMES_PROFILE kanban block "$TASK_ID" \
                --reason "Gemini 编码失败: $FAILURE_REASON"
        fi

        # 清理结果文件
        rm -f "$RESULT_FILE"
    else
        # 没有结果文件，检查退出码
        if [ $GEMINI_EXIT -ne 0 ]; then
            log "❌ Gemini CLI 异常退出 (code: $GEMINI_EXIT)"
            $HERMES -p $HERMES_PROFILE kanban block "$TASK_ID" \
                --reason "Gemini CLI 异常退出 (exit code: $GEMINI_EXIT)。日志: /tmp/gemini-worker-${TASK_ID}.log"
        else
            log "⚠️ Gemini CLI 完成但未生成 .gemini-result.json"
            $HERMES -p $HERMES_PROFILE kanban block "$TASK_ID" \
                --reason "Gemini CLI 完成但未生成结果文件。需要人工检查。日志: /tmp/gemini-worker-${TASK_ID}.log"
        fi
    fi

    log "🔁 继续轮询..."
done

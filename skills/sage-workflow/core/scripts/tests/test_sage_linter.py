from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "sage_linter.py"

UNCHECKED_EVIDENCE = (
    "### 3.2 🧪 证据链\n"
    "- [ ] **AC-1**: 待回填\n"
    "- [ ] **自动化测试结果**: 待回填\n"
    "- [ ] **Lint 检查结果**: 待回填\n"
)

CHECKED_EVIDENCE = (
    "### 3.2 🧪 证据链\n"
    "- [x] **AC-1**: 单测全部通过\n"
    "- [x] **自动化测试结果**: 全部通过\n"
    "- [x] **Lint 检查结果**: 通过\n"
)


def load_linter():
    """以独立模块名加载 sage_linter.py，避免与已安装包或其他测试产生导入冲突。"""
    spec = importlib.util.spec_from_file_location("sage_linter_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["sage_linter_under_test"] = module
    spec.loader.exec_module(module)
    return module


class CheckEvidenceCompletePhaseTests(unittest.TestCase):
    """check_evidence_complete 阶段感知三态：早期阶段跳过 / 收尾阶段阻断 / 元数据缺失维持强制。"""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.linter = load_linter()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()
        sys.modules.pop("sage_linter_under_test", None)

    def write_task(self, phase_line: str, evidence: str) -> Path:
        """构造最小 TASK 文档；phase_line 传空串表示缺失"当前阶段"元数据。"""
        metadata = f"- **当前阶段**: {phase_line}\n" if phase_line else ""
        task = Path(self.temp_dir.name) / "ACTIVE_TASK_T-TEST.md"
        task.write_text(
            "# TASK\n\n"
            "- **任务编号 (ID)**: T-TEST\n"
            "- **风险等级**: L2\n"
            f"{metadata}"
            "- **项目根目录**: test\n"
            "- **功能分支**: feat/t-test\n\n"
            "## 阶段 3：开发与验证\n\n"
            f"{evidence}\n"
            "## 阶段 4：代码审查\n",
            encoding="utf-8",
        )
        return task

    def test_early_stages_skip_evidence_check(self) -> None:
        for stage in ("init", "plan-review", "dev"):
            with self.subTest(stage=stage):
                task = self.write_task(stage, UNCHECKED_EVIDENCE)
                ok, msg = self.linter.check_evidence_complete(task)
                self.assertTrue(ok)
                self.assertIn("跳过", msg)

    def test_close_stage_blocks_unchecked_evidence(self) -> None:
        task = self.write_task("close", UNCHECKED_EVIDENCE)
        ok, msg = self.linter.check_evidence_complete(task)
        self.assertFalse(ok)
        self.assertIn("证据链不完整", msg)

    def test_code_review_stage_blocks_unchecked_evidence(self) -> None:
        task = self.write_task("code-review", UNCHECKED_EVIDENCE)
        ok, _ = self.linter.check_evidence_complete(task)
        self.assertFalse(ok)

    def test_missing_stage_metadata_stays_strict(self) -> None:
        task = self.write_task("", UNCHECKED_EVIDENCE)
        ok, msg = self.linter.check_evidence_complete(task)
        self.assertFalse(ok)
        self.assertIn("证据链不完整", msg)

    def test_close_stage_passes_when_evidence_checked(self) -> None:
        task = self.write_task("close", CHECKED_EVIDENCE)
        ok, _ = self.linter.check_evidence_complete(task)
        self.assertTrue(ok)


# 构造注入用临时测试源码：通过 / 失败 / 慢（超时实证）三种输入
PASSING_TEST_SOURCE = (
    "import unittest\n"
    "class TestInjectedOk(unittest.TestCase):\n"
    "    def test_ok(self):\n"
    "        self.assertTrue(True)\n"
)

FAILING_TEST_SOURCE = (
    "import unittest\n"
    "class TestInjectedBad(unittest.TestCase):\n"
    "    def test_bad(self):\n"
    "        self.fail('intentional failure for check_unit_tests')\n"
)

SLOW_TEST_SOURCE = (
    "import time\n"
    "import unittest\n"
    "class TestInjectedSlow(unittest.TestCase):\n"
    "    def test_slow(self):\n"
    "        time.sleep(5)\n"
)


class CheckUnitTestsStateTests(unittest.TestCase):
    """check_unit_tests 三态 + 超时分支。

    契约（TASK T-012 步骤 2）：仅做函数级注入调用（tests_dir 指向临时目录），
    禁止在用例内触发 --all 全量路径，防止递归门禁。
    """

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.linter = load_linter()
        self.tests_dir = Path(self.temp_dir.name) / "tests"
        self.tests_dir.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()
        sys.modules.pop("sage_linter_under_test", None)

    def write_test_file(self, source: str) -> Path:
        target = self.tests_dir / "test_injected.py"
        target.write_text(source, encoding="utf-8")
        return target

    def test_passing_suite_passes(self) -> None:
        self.write_test_file(PASSING_TEST_SOURCE)
        ok, msg = self.linter.check_unit_tests(tests_dir=self.tests_dir)
        self.assertTrue(ok, msg)
        self.assertIn("通过", msg)

    def test_failing_suite_blocks(self) -> None:
        self.write_test_file(FAILING_TEST_SOURCE)
        ok, msg = self.linter.check_unit_tests(tests_dir=self.tests_dir)
        self.assertFalse(ok)
        self.assertIn("失败", msg)

    def test_empty_tests_dir_skips(self) -> None:
        ok, msg = self.linter.check_unit_tests(tests_dir=self.tests_dir)
        self.assertTrue(ok)
        self.assertIn("跳过", msg)

    def test_missing_tests_dir_skips(self) -> None:
        ok, msg = self.linter.check_unit_tests(tests_dir=self.tests_dir / "nonexistent")
        self.assertTrue(ok)
        self.assertIn("跳过", msg)

    def test_timeout_treated_as_failure(self) -> None:
        self.write_test_file(SLOW_TEST_SOURCE)
        ok, msg = self.linter.check_unit_tests(tests_dir=self.tests_dir, timeout=1)
        self.assertFalse(ok)
        self.assertIn("超时", msg)


class RuleIdAndDisclosureTests(unittest.TestCase):
    """规则 ID 中心化标注、启发式检查器命中依据披露、运行日志三态（T-014）。"""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.linter = load_linter()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()
        sys.modules.pop("sage_linter_under_test", None)

    def write_task(self, content: str) -> Path:
        task = Path(self.temp_dir.name) / "ACTIVE_TASK_T-TEST.md"
        task.write_text(content, encoding="utf-8")
        return task

    # ---------- 规则 ID 派生与三格式输出 ----------

    def test_rule_id_from_label_formats(self) -> None:
        self.assertEqual(self.linter._rule_id_from_label("[10/16] 范围锁定校验"), "SAGE-10")
        self.assertEqual(self.linter._rule_id_from_label("17. 提交信息中文校验"), "SAGE-17")
        self.assertIsNone(self.linter._rule_id_from_label("无编号标签"))

    def test_collector_json_carries_rule_id(self) -> None:
        collector = self.linter.ResultCollector(fmt="json")
        collector.add("10. 范围锁定校验", False, "越权修改")
        self.assertEqual(collector.results[0].rule_id, "SAGE-10")
        self.assertIn("rule_id", collector.results[0].to_dict())
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            collector.flush()
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["results"][0]["rule_id"], "SAGE-10")

    def test_text_fail_and_warn_lines_carry_rule_id(self) -> None:
        collector = self.linter.ResultCollector(fmt="text")
        collector.add("10. 范围锁定校验", False, "越权修改")
        collector.add("6. 文档新鲜度扫描", True, "⚠️ 新鲜度警告")
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            collector.flush()
        output = buffer.getvalue()
        self.assertIn("[SAGE-10]", output)
        self.assertIn("[SAGE-06]", output)

    def test_unparseable_label_degrades_silently(self) -> None:
        collector = self.linter.ResultCollector(fmt="text")
        collector.add("无编号标签", False, "违规")
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            collector.flush()
        self.assertNotIn("[SAGE-", buffer.getvalue())

    # ---------- 风险扩展校验命中依据披露 ----------

    def test_risk_ac_placeholder_disclosure(self) -> None:
        task = self.write_task(
            "# TASK\n\n"
            "- **风险等级**: L2\n\n"
            "### 1.3a 验收标准\n\n"
            "| AC-ID | 类型 | 可证伪验收标准 | 验证方式 | 证据位置 |\n"
            "|-------|------|----------------|----------|----------|\n"
            "| AC-1 | [auto] | 运行全部单测 | 待填 | |\n\n"
            "### 1.3b 风险矩阵\n\n"
            "| 风险 | 概率 | 影响 | 缓解措施 |\n"
            "|------|------|------|---------|\n"
            "| 真实风险条目 | 低 | 低 | 真实应对方式 |\n\n"
            "### 1.4 范围锁定\n"
        )
        ok, msg = self.linter.check_task_risk_sections(task)
        self.assertFalse(ok)
        self.assertIn('命中占位符标记 "待填"', msg)
        self.assertIn("验证方式 列", msg)
        self.assertIn("判定词表", msg)
        self.assertIn("证据位置 列为空", msg)

    def test_risk_matrix_placeholder_disclosure(self) -> None:
        task = self.write_task(
            "# TASK\n\n"
            "- **风险等级**: L2\n\n"
            "### 1.3a 验收标准\n\n"
            "| AC-ID | 类型 | 可证伪验收标准 | 验证方式 | 证据位置 |\n"
            "|-------|------|----------------|----------|----------|\n"
            "| AC-1 | [auto] | 全部单测通过 | unittest discover | 3.2 |\n\n"
            "### 1.3b 风险矩阵\n\n"
            "| 风险 | 概率 | 影响 | 缓解措施 |\n"
            "|------|------|------|---------|\n"
            "| (风险描述) | 低/中/高 | 低/中/高 | (缓解方案) |\n\n"
            "### 1.4 范围锁定\n"
        )
        ok, msg = self.linter.check_task_risk_sections(task)
        self.assertFalse(ok)
        self.assertIn("未填写具体内容", msg)
        self.assertIn("命中", msg)
        self.assertIn("判定词表", msg)

    def test_risk_matrix_missing_table_disclosure(self) -> None:
        task = self.write_task(
            "# TASK\n\n"
            "- **风险等级**: L2\n\n"
            "### 1.3a 验收标准\n\n"
            "| AC-ID | 类型 | 可证伪验收标准 | 验证方式 | 证据位置 |\n"
            "|-------|------|----------------|----------|----------|\n"
            "| AC-1 | [auto] | 全部单测通过 | unittest discover | 3.2 |\n\n"
            "### 1.3b 风险矩阵\n\n"
            "暂无内容。\n\n"
            "### 1.4 范围锁定\n"
        )
        ok, msg = self.linter.check_task_risk_sections(task)
        self.assertFalse(ok)
        self.assertIn("缺少完整表格", msg)

    # ---------- 盲审完整性三态披露 ----------

    def test_review_section_missing_disclosure(self) -> None:
        task = self.write_task("# TASK\n\n- **风险等级**: L2\n\n## 阶段 3：开发与验证\n")
        ok, msg = self.linter.check_review_complete(task)
        self.assertFalse(ok)
        self.assertIn("章节不存在", msg)
        self.assertIn("要求标题", msg)

    def test_review_section_without_marker_disclosure(self) -> None:
        task = self.write_task(
            "# TASK\n\n- **风险等级**: L2\n\n"
            "### 2.1 评审意见\n\n一些普通文字。\n\n"
            "## 阶段 3：开发与验证\n"
        )
        ok, msg = self.linter.check_review_complete(task)
        self.assertFalse(ok)
        self.assertIn("未找到审查结论标记", msg)
        self.assertIn("判定词表", msg)

    def test_review_section_placeholder_only_disclosure(self) -> None:
        task = self.write_task(
            "# TASK\n\n- **风险等级**: L2\n\n"
            "### 2.1 评审意见\n\n"
            "- [ ] **评审意见**: (由 reviewer 填写)\n"
            "评审反馈 OK\n\n"
            "## 阶段 3：开发与验证\n"
        )
        ok, msg = self.linter.check_review_complete(task)
        self.assertFalse(ok)
        self.assertIn("存在审查标记但无实质内容", msg)
        self.assertIn("占位词表", msg)

    # ---------- TD-8 回归：模板 HTML 门禁注释不得参与盲审判定 ----------

    def test_review_section_template_html_comments_not_counted(self) -> None:
        # 模板原样空 2.1 节：HTML 门禁注释含 OK/WARN/BLOCK，修复前会被误计为结论标记与实质内容而恒放行；
        # 4.1 提供真实报告以隔离断言目标
        task = self.write_task(
            "# TASK\n\n- **风险等级**: L2\n\n"
            "### 2.1 评审意见 (Review Feedback)\n\n"
            "- [ ] **评审意见**: (由 reviewer 填写)\n"
            "- [ ] **修正记录**: (如有修改)\n\n"
            "<!-- 盲审按“执行通道配置”调用 CLI 或 subagent；Prompt 只提供 REPO_ROOT、TASK_PATH、ROLE_PROMPT、PHASE 等必要定位信息，其他调度信息从 TASK 元数据读取，并要求 reviewer 写回本节。 -->\n"
            "<!-- 门禁：若本节未出现 OK/WARN/BLOCK 等有效审查报告，流程不得进入阶段 3。 -->\n\n"
            "## 💻 阶段 3：开发与验证\n\n"
            "### 4.1 代码评审 (Code Review Feedback)\n\n"
            "### 审查结果：OK\n\n"
            "逐维度评定全部通过。\n\n"
            "## 🧠 阶段 5：收尾与归档\n"
        )
        ok, msg = self.linter.check_review_complete(task)
        self.assertFalse(ok)
        self.assertIn("2.1 计划评审报告", msg)
        self.assertIn("未找到审查结论标记", msg)

    def test_review_section_multiline_html_comment_not_counted(self) -> None:
        # 跨行 HTML 注释（<!-- 与 --> 分行）同样不得参与判定，覆盖 DOTALL 剥离分支；
        # 2.1 提供真实报告以隔离断言目标
        task = self.write_task(
            "# TASK\n\n- **风险等级**: L2\n\n"
            "### 2.1 评审意见 (Review Feedback)\n\n"
            "### 审查结果：OK\n\n"
            "逐维度评定全部通过。\n\n"
            "## 💻 阶段 3：开发与验证\n\n"
            "### 4.1 代码评审 (Code Review Feedback)\n\n"
            "- [ ] **核心变更点**:\n"
            "<!-- 多行门禁说明：\n"
            "    结论词 OK WARN BLOCK 出现在注释内部\n"
            "-->\n\n"
            "## 🧠 阶段 5：收尾与归档\n"
        )
        ok, msg = self.linter.check_review_complete(task)
        self.assertFalse(ok)
        self.assertIn("4.1 代码评审报告", msg)
        self.assertIn("未找到审查结论标记", msg)

    def test_review_section_real_report_with_html_comments_passes(self) -> None:
        # 防误伤：真实审查报告与 HTML 门禁注释共存时必须放行（2.1/4.1 对称覆盖）
        task = self.write_task(
            "# TASK\n\n- **风险等级**: L2\n\n"
            "### 2.1 评审意见 (Review Feedback)\n\n"
            "### 审查结果：OK\n\n"
            "逐维度评定全部通过，计划可证伪且范围锁定完整。\n\n"
            "<!-- 门禁：若本节未出现 OK/WARN/BLOCK 等有效审查报告，流程不得进入阶段 3。 -->\n\n"
            "## 💻 阶段 3：开发与验证\n\n"
            "### 4.1 代码评审 (Code Review Feedback)\n\n"
            "### 审查结果：WARN\n\n"
            "存在轻微改进建议，无阻塞项。\n\n"
            "<!-- 门禁：若本节未出现 OK/WARN/BLOCK 等有效审查报告，流程不得进入阶段 5。 -->\n\n"
            "## 🧠 阶段 5：收尾与归档\n"
        )
        ok, msg = self.linter.check_review_complete(task)
        self.assertTrue(ok, msg)

    # ---------- 阶段感知：盲审报告按阶段到期（与 check_evidence_complete 同构） ----------

    def test_review_stage_init_skips_both_sections(self) -> None:
        # init 阶段两节均未到期：空节（含模板门禁注释）不阻断
        task = self.write_task(
            "# TASK\n\n- **风险等级**: L2\n- **当前阶段**: init\n\n"
            "### 2.1 评审意见 (Review Feedback)\n\n"
            "<!-- 门禁注释：OK/WARN/BLOCK -->\n\n"
            "## 💻 阶段 3：开发与验证\n\n"
            "### 4.1 代码评审 (Code Review Feedback)\n\n"
            "<!-- 门禁注释：OK/WARN/BLOCK -->\n\n"
            "## 🧠 阶段 5：收尾与归档\n"
        )
        ok, msg = self.linter.check_review_complete(task)
        self.assertTrue(ok, msg)
        self.assertIn("未到期", msg)

    def test_review_stage_dev_defers_code_review_only(self) -> None:
        # dev 阶段：2.1 已到期、4.1 未到期——4.1 空节放行，2.1 空节仍阻断
        due_plan = self.write_task(
            "# TASK\n\n- **风险等级**: L2\n- **当前阶段**: dev\n\n"
            "### 2.1 评审意见 (Review Feedback)\n\n"
            "### 审查结果：OK\n\n"
            "计划评审通过。\n\n"
            "## 💻 阶段 3：开发与验证\n\n"
            "### 4.1 代码评审 (Code Review Feedback)\n\n"
            "<!-- 门禁注释：OK/WARN/BLOCK -->\n\n"
            "## 🧠 阶段 5：收尾与归档\n"
        )
        ok, msg = self.linter.check_review_complete(due_plan)
        self.assertTrue(ok, msg)
        self.assertIn("4.1", msg)
        self.assertIn("未到期", msg)

        due_code = self.write_task(
            "# TASK\n\n- **风险等级**: L2\n- **当前阶段**: dev\n\n"
            "### 2.1 评审意见 (Review Feedback)\n\n"
            "<!-- 门禁注释：OK/WARN/BLOCK -->\n\n"
            "## 💻 阶段 3：开发与验证\n\n"
            "### 4.1 代码评审 (Code Review Feedback)\n\n"
            "### 审查结果：OK\n\n"
            "代码评审通过。\n\n"
            "## 🧠 阶段 5：收尾与归档\n"
        )
        ok, msg = self.linter.check_review_complete(due_code)
        self.assertFalse(ok)
        self.assertIn("2.1 计划评审报告", msg)

    def test_review_stage_code_review_enforces_both(self) -> None:
        # code-review 阶段两节均到期：双空节均列入阻断
        task = self.write_task(
            "# TASK\n\n- **风险等级**: L2\n- **当前阶段**: code-review\n\n"
            "### 2.1 评审意见 (Review Feedback)\n\n"
            "<!-- 门禁注释：OK/WARN/BLOCK -->\n\n"
            "## 💻 阶段 3：开发与验证\n\n"
            "### 4.1 代码评审 (Code Review Feedback)\n\n"
            "<!-- 门禁注释：OK/WARN/BLOCK -->\n\n"
            "## 🧠 阶段 5：收尾与归档\n"
        )
        ok, msg = self.linter.check_review_complete(task)
        self.assertFalse(ok)
        self.assertIn("2.1 计划评审报告", msg)
        self.assertIn("4.1 代码评审报告", msg)

    def test_review_stage_missing_metadata_enforces_both(self) -> None:
        # 元数据缺失维持强制（fail-safe）：无当前阶段行时空节仍阻断
        task = self.write_task(
            "# TASK\n\n- **风险等级**: L2\n\n"
            "### 2.1 评审意见 (Review Feedback)\n\n"
            "<!-- 门禁注释：OK/WARN/BLOCK -->\n\n"
            "## 💻 阶段 3：开发与验证\n\n"
            "### 4.1 代码评审 (Code Review Feedback)\n\n"
            "<!-- 门禁注释：OK/WARN/BLOCK -->\n\n"
            "## 🧠 阶段 5：收尾与归档\n"
        )
        ok, msg = self.linter.check_review_complete(task)
        self.assertFalse(ok)
        self.assertIn("2.1 计划评审报告", msg)
        self.assertIn("4.1 代码评审报告", msg)

    # ---------- TD-9 回归：模板默认值元数据不得被误判为 init ----------

    def test_stage_template_default_blocks_evidence_check(self) -> None:
        # 元数据仍为模板管道默认行：check_evidence_complete 不得按 init 跳过，须阻断并披露
        task = self.write_task(
            "# TASK\n\n"
            "- **风险等级**: L2\n"
            "- **当前阶段**: init | plan-review | dev | code-review | close\n\n"
            "### 3.2 🧪 证据链\n"
            "- [ ] **AC-1**: 待回填\n"
            "- [ ] **自动化测试结果**: 待回填\n"
            "- [ ] **Lint 检查结果**: 待回填\n"
        )
        ok, msg = self.linter.check_evidence_complete(task)
        self.assertFalse(ok)
        self.assertIn("模板默认值", msg)
        self.assertIn("当前阶段", msg)

    def test_stage_template_default_blocks_review_check(self) -> None:
        # 元数据仍为模板管道默认行：check_review_complete 不得按 init 跳过，须阻断并披露
        task = self.write_task(
            "# TASK\n\n- **风险等级**: L2\n"
            "- **当前阶段**: init | plan-review | dev | code-review | close\n\n"
            "### 2.1 评审意见 (Review Feedback)\n\n"
            "<!-- 门禁注释：OK/WARN/BLOCK -->\n\n"
            "## 💻 阶段 3：开发与验证\n\n"
            "### 4.1 代码评审 (Code Review Feedback)\n\n"
            "<!-- 门禁注释：OK/WARN/BLOCK -->\n\n"
            "## 🧠 阶段 5：收尾与归档\n"
        )
        ok, msg = self.linter.check_review_complete(task)
        self.assertFalse(ok)
        self.assertIn("模板默认值", msg)

    def test_stage_template_default_blocks_execution_channel_check(self) -> None:
        # 元数据仍为模板管道默认行：check_execution_channel_records 不得按 init 仅要求 1.0；
        # 1.0 预先填好以隔离默认值判定，排除未勾选噪声
        task = self.write_task(
            "# TASK\n\n"
            "- **风险等级**: L2\n"
            "- **当前阶段**: init | plan-review | dev | code-review | close\n\n"
            "执行通道记录\n\n"
            "### 1.0 执行通道记录\n"
            "- [x] **角色契约**: prompts/planner.md 已加载并遵循\n"
            "- [x] **执行通道**: Main Agent\n"
            "- [x] **偏离处理**: N/A\n"
        )
        ok, msg = self.linter.check_execution_channel_records(task)
        self.assertFalse(ok)
        self.assertIn("模板默认值", msg)

    def test_parse_current_stage_no_token_path(self) -> None:
        # helper 直测：值全为非 ASCII 占位文本（无 [a-z-]+ token）→ 与"缺失"等价 ("", False)（计划盲审建议 4）
        stage, is_default = self.linter._parse_current_stage("- **当前阶段**: [填写实际阶段]")
        self.assertEqual(stage, "")
        self.assertFalse(is_default)
        # 模板管道默认行 → 默认值标记
        stage, is_default = self.linter._parse_current_stage(
            "- **当前阶段**: init | plan-review | dev | code-review | close"
        )
        self.assertEqual(stage, "")
        self.assertTrue(is_default)
        # 正常值
        stage, is_default = self.linter._parse_current_stage("- **当前阶段**: dev")
        self.assertEqual(stage, "dev")
        self.assertFalse(is_default)

    # ---------- 执行通道记录格式披露 ----------

    def test_execution_channel_missing_section_disclosure(self) -> None:
        task = self.write_task(
            "# TASK\n\n"
            "- **风险等级**: L2\n"
            "- **当前阶段**: dev\n\n"
            "执行通道记录\n\n"
            "### 1.0 执行通道记录\n"
            "- [x] **角色契约**: prompts/planner.md 已加载并遵循\n"
            "- [x] **执行通道**: Main Agent\n"
            "- [x] **偏离处理**: N/A\n"
        )
        ok, msg = self.linter.check_execution_channel_records(task)
        self.assertFalse(ok)
        self.assertIn("要求标题: ### 3.0 执行通道记录", msg)

    def test_execution_channel_format_disclosure(self) -> None:
        task = self.write_task(
            "# TASK\n\n"
            "- **风险等级**: L2\n"
            "- **当前阶段**: dev\n\n"
            "执行通道记录\n\n"
            "### 1.0 执行通道记录\n"
            "- [ ] **角色契约**: prompts/planner.md 已加载并遵循\n"
            "- [x] **执行通道**: Main Agent\n"
            "- [x] **偏离处理**: N/A\n\n"
            "### 3.0 执行通道记录\n"
            "- [x] **角色契约**: prompts/coder.md 已加载并遵循\n"
            "- [x] **偏离处理**: N/A\n"
        )
        ok, msg = self.linter.check_execution_channel_records(task)
        self.assertFalse(ok)
        self.assertIn("复选框未勾选", msg)
        self.assertIn("要求行格式", msg)

    # ---------- 模型元数据类别披露 ----------

    def test_model_metadata_paren_placeholder_disclosure(self) -> None:
        task = self.write_task("- **使用模型**: (见模型选择指南)\n")
        ok, msg = self.linter.check_model_metadata(task)
        self.assertFalse(ok)
        self.assertIn("括号占位符", msg)
        self.assertIn("(见模型选择指南)", msg)

    def test_model_metadata_keyword_disclosure(self) -> None:
        task = self.write_task("- **使用模型**: 请填写模型名称\n")
        ok, msg = self.linter.check_model_metadata(task)
        self.assertFalse(ok)
        self.assertIn('占位词"填写"', msg)

    # ---------- 运行日志与 .sage/ 元文件判定 ----------

    def test_write_run_log_appends_single_line(self) -> None:
        collector = self.linter.ResultCollector(fmt="text")
        collector.add("10. 范围锁定校验", False, "越权修改")
        collector.add("6. 文档新鲜度扫描", True, "⚠️ 新鲜度警告")
        root = Path(self.temp_dir.name)
        self.linter.write_run_log(root, "all", collector, hook_mode=False)
        log_file = root / ".sage" / "linter-runs.jsonl"
        self.assertTrue(log_file.exists())
        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        entry = json.loads(lines[0])
        self.assertEqual(entry["mode"], "all")
        self.assertEqual(entry["exit_code"], 2)
        self.assertEqual(entry["fail"], ["SAGE-10"])
        self.assertEqual(entry["warn"], ["SAGE-06"])
        self.assertIn("ts", entry)

    def test_write_run_log_hook_mode_skips_clean_runs(self) -> None:
        root = Path(self.temp_dir.name)
        clean = self.linter.ResultCollector(fmt="text")
        clean.add("10. 范围锁定校验", True, "通过")
        self.linter.write_run_log(root, "scope", clean, hook_mode=True)
        self.assertFalse((root / ".sage" / "linter-runs.jsonl").exists())

        warn_only = self.linter.ResultCollector(fmt="text")
        warn_only.add("6. 文档新鲜度扫描", True, "⚠️ 新鲜度警告")
        self.linter.write_run_log(root, "scope", warn_only, hook_mode=True)
        self.assertTrue((root / ".sage" / "linter-runs.jsonl").exists())

    def test_write_run_log_default_uses_module_hook_flag(self) -> None:
        root = Path(self.temp_dir.name)
        collector = self.linter.ResultCollector(fmt="text")
        collector.add("10. 范围锁定校验", False, "越权修改")
        self.linter.write_run_log(root, "all", collector)
        self.assertTrue((root / ".sage" / "linter-runs.jsonl").exists())

    def test_sage_dir_treated_as_meta_file(self) -> None:
        self.assertTrue(self.linter._is_meta_file(".sage/linter-runs.jsonl"))


class CheckPlanClearanceTests(unittest.TestCase):
    """check_plan_clearance 判定矩阵（T-018）：到期强制 / 早期跳过 / L0·L3 豁免 / fail-safe。"""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.linter = load_linter()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()
        sys.modules.pop("sage_linter_under_test", None)

    def write_task(self, risk: str | None, phase: str, clearance: str | None) -> Path:
        """构造最小 TASK 文档；risk/clearance 传 None 表示缺失对应元数据行。"""
        lines = ["# TASK\n\n", "- **任务编号 (ID)**: T-TEST\n"]
        if risk is not None:
            lines.append(f"- **风险等级**: {risk}\n")
        lines.append(f"- **当前阶段**: {phase}\n")
        if clearance is not None:
            lines.append(f"- **计划放行**: {clearance}\n")
        lines.append("- **项目根目录**: test\n- **功能分支**: feat/t-test\n")
        task = Path(self.temp_dir.name) / "ACTIVE_TASK_T-TEST.md"
        task.write_text("".join(lines), encoding="utf-8")
        return task

    def test_dev_pending_clearance_blocks_with_guidance(self) -> None:
        task = self.write_task("L1", "dev", "待放行")
        ok, msg = self.linter.check_plan_clearance(task)
        self.assertFalse(ok)
        self.assertIn("计划放行未完成", msg)
        self.assertIn("已放行", msg)
        self.assertIn("planner.md 第 8 节", msg)

    def test_dev_cleared_passes(self) -> None:
        task = self.write_task("L2", "dev", "已放行（用户确认，2026-08-31T01:23:42+08:00）")
        ok, msg = self.linter.check_plan_clearance(task)
        self.assertTrue(ok)

    def test_early_stages_skip(self) -> None:
        for stage in ("init", "plan-review"):
            with self.subTest(stage=stage):
                task = self.write_task("L2", stage, "待放行")
                ok, msg = self.linter.check_plan_clearance(task)
                self.assertTrue(ok)
                self.assertIn("跳过", msg)

    def test_l0_and_l3_exempt(self) -> None:
        for risk in ("L0", "L3"):
            with self.subTest(risk=risk):
                task = self.write_task(risk, "dev", "待放行")
                ok, msg = self.linter.check_plan_clearance(task)
                self.assertTrue(ok)
                self.assertIn("跳过", msg)

    def test_close_stage_pending_blocks(self) -> None:
        task = self.write_task("L2", "close", "待放行")
        ok, _ = self.linter.check_plan_clearance(task)
        self.assertFalse(ok)

    def test_missing_field_failsafe_blocks(self) -> None:
        task = self.write_task("L1", "dev", None)
        ok, msg = self.linter.check_plan_clearance(task)
        self.assertFalse(ok)
        self.assertIn("缺失", msg)

    def test_missing_risk_failsafe_enforces(self) -> None:
        task = self.write_task(None, "dev", "待放行")
        ok, _ = self.linter.check_plan_clearance(task)
        self.assertFalse(ok)

    def test_unknown_stage_failsafe_enforces(self) -> None:
        task = self.write_task("L1", "unknown-stage", "待放行")
        ok, _ = self.linter.check_plan_clearance(task)
        self.assertFalse(ok)

    def test_stage_template_default_skips(self) -> None:
        """当前阶段为模板管道默认行时跳过（init 模板态「待放行」为合法初始值）。"""
        task = Path(self.temp_dir.name) / "ACTIVE_TASK_T-TEST.md"
        task.write_text(
            "# TASK\n\n"
            "- **任务编号 (ID)**: T-TEST\n"
            "- **风险等级**: L2\n"
            "- **当前阶段**: init | plan-review | dev | code-review | close\n"
            "- **计划放行**: 待放行\n"
            "- **项目根目录**: test\n"
            "- **功能分支**: feat/t-test\n",
            encoding="utf-8",
        )
        ok, msg = self.linter.check_plan_clearance(task)
        self.assertTrue(ok)
        self.assertIn("跳过", msg)


class CheckChangelogUpdateStageTests(unittest.TestCase):
    """check_changelog_update 阶段感知三态（T-021）：早期阶段跳过 / close 强制 / fail-safe 维持强制。

    「有代码变更」分支依赖 git 工作区：临时目录内 git init 构造最小仓——
    CHANGELOG.md 先提交使其被跟踪且无变更，再放一个未跟踪代码文件 app.py 构成代码变更，
    此时 CHANGELOG 不在变更列表即应触发联动判定。
    """

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.linter = load_linter()
        self.repo = Path(self.temp_dir.name)
        # 最小 git 仓：CHANGELOG.md 入库（被跟踪、无变更），app.py 未跟踪即代码变更
        self.linter.run_git_cmd(["init"], cwd=self.repo)
        self.linter.run_git_cmd(["config", "user.email", "test@example.com"], cwd=self.repo)
        self.linter.run_git_cmd(["config", "user.name", "tester"], cwd=self.repo)
        (self.repo / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
        self.linter.run_git_cmd(["add", "CHANGELOG.md"], cwd=self.repo)
        self.linter.run_git_cmd(["commit", "-m", "init"], cwd=self.repo)
        (self.repo / "app.py").write_text("print('code change')\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()
        sys.modules.pop("sage_linter_under_test", None)

    def write_task(self, phase_line: str) -> Path:
        """构造最小 TASK 文档；phase_line 传空串表示缺失"当前阶段"元数据。"""
        metadata = f"- **当前阶段**: {phase_line}\n" if phase_line else ""
        task = self.repo / "ACTIVE_TASK_T-TEST.md"
        task.write_text(
            "# TASK\n\n"
            "- **任务编号 (ID)**: T-TEST\n"
            "- **风险等级**: L2\n"
            f"{metadata}"
            "- **项目根目录**: test\n"
            "- **功能分支**: feat/t-test\n",
            encoding="utf-8",
        )
        return task

    def test_early_stages_skip_changelog_check(self) -> None:
        # CHANGELOG 回填属 close 期动作：init/plan-review/dev/code-review 未到期，跳过且不阻断
        for stage in ("init", "plan-review", "dev", "code-review"):
            with self.subTest(stage=stage):
                task = self.write_task(stage)
                ok, msg = self.linter.check_changelog_update(
                    self.repo / "CHANGELOG.md", cwd=self.repo, task_file=task
                )
                self.assertTrue(ok)
                self.assertIn("未到期", msg)
                self.assertIn(stage, msg)

    def test_close_stage_blocks_when_changelog_not_updated(self) -> None:
        # close 期有代码变更且 CHANGELOG 未更新：维持既有强制阻断
        task = self.write_task("close")
        ok, msg = self.linter.check_changelog_update(
            self.repo / "CHANGELOG.md", cwd=self.repo, task_file=task
        )
        self.assertFalse(ok)
        self.assertIn("未进行同步更新", msg)

    def test_task_file_none_enforces(self) -> None:
        # task_file=None（向后兼容）：退化为既有强制行为（fail-safe 最严侧）
        ok, msg = self.linter.check_changelog_update(self.repo / "CHANGELOG.md", cwd=self.repo)
        self.assertFalse(ok)
        self.assertIn("未进行同步更新", msg)

    def test_missing_stage_metadata_enforces(self) -> None:
        # 元数据「当前阶段」行缺失：无法判定阶段，fail-safe 强制并披露判定依据
        task = self.write_task("")
        ok, msg = self.linter.check_changelog_update(
            self.repo / "CHANGELOG.md", cwd=self.repo, task_file=task
        )
        self.assertFalse(ok)
        self.assertIn("当前阶段", msg)
        self.assertIn("fail-safe", msg)

    def test_unknown_stage_value_enforces(self) -> None:
        # 未知阶段值：无法判定阶段，fail-safe 强制且消息回显实际值（AP-009）
        task = self.write_task("unknown-stage")
        ok, msg = self.linter.check_changelog_update(
            self.repo / "CHANGELOG.md", cwd=self.repo, task_file=task
        )
        self.assertFalse(ok)
        self.assertIn("unknown-stage", msg)
        self.assertIn("fail-safe", msg)

    def test_stage_template_default_enforces(self) -> None:
        # 模板管道默认行（未更新）：不得被误判为 init 跳过，fail-safe 强制并披露（TD-9 同源）
        task = self.write_task("init | plan-review | dev | code-review | close")
        ok, msg = self.linter.check_changelog_update(
            self.repo / "CHANGELOG.md", cwd=self.repo, task_file=task
        )
        self.assertFalse(ok)
        self.assertIn("模板默认值", msg)


class CheckTemplatesPristineDisclosureTests(unittest.TestCase):
    """check_templates_pristine 阻断消息豁免参数披露（T-021 / AP-009）：判定语义零变化。"""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.linter = load_linter()
        self.repo = Path(self.temp_dir.name)
        # 最小 git 仓：templates/ 入库，使后续工作区改动能被 git diff 捕获
        self.linter.run_git_cmd(["init"], cwd=self.repo)
        self.linter.run_git_cmd(["config", "user.email", "test@example.com"], cwd=self.repo)
        self.linter.run_git_cmd(["config", "user.name", "tester"], cwd=self.repo)
        self.templates = self.repo / "templates"
        self.templates.mkdir()
        (self.templates / "TASK-TEMPLATE.md").write_text("# 模板原文\n", encoding="utf-8")
        self.linter.run_git_cmd(["add", "."], cwd=self.repo)
        self.linter.run_git_cmd(["commit", "-m", "init"], cwd=self.repo)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()
        sys.modules.pop("sage_linter_under_test", None)

    def test_untouched_templates_pass(self) -> None:
        # 判定语义零变化（改前行为）：模板未改 → 通过
        ok, msg = self.linter.check_templates_pristine(self.templates, self.repo)
        self.assertTrue(ok, msg)

    def test_modified_template_blocks_with_allow_param_disclosure(self) -> None:
        # 判定语义零变化（改前行为）：模板已改 → 阻断；阻断消息须披露豁免参数与适用条件
        (self.templates / "TASK-TEMPLATE.md").write_text("# 模板被篡改\n", encoding="utf-8")
        ok, msg = self.linter.check_templates_pristine(self.templates, self.repo)
        self.assertFalse(ok)
        self.assertIn("--allow-template-changes", msg)
        self.assertIn("撤销更改", msg)


class PlanClearanceRuleIdContractTests(unittest.TestCase):
    """计划放行 rule ID 契约（T-018）：SAGE-18 显式映射、SAGE-01~17 零变化、全局唯一。"""

    def setUp(self) -> None:
        self.linter = load_linter()

    def tearDown(self) -> None:
        sys.modules.pop("sage_linter_under_test", None)

    def test_explicit_rule_id_overrides_label_derivation(self) -> None:
        collector = self.linter.ResultCollector(fmt="json")
        collector.add("[17/17] 计划放行校验", False, "未放行", rule_id="SAGE-18")
        self.assertEqual(collector.results[0].rule_id, "SAGE-18")

    def test_scenario_a_label_derives_sage18(self) -> None:
        self.assertEqual(self.linter._rule_id_from_label("18. 计划放行校验"), "SAGE-18")

    def test_bare_label_17_derives_reserved_sage17(self) -> None:
        """负向断言：[17/17] 裸派生即 SAGE-17（hook 保留段）——显式 rule_id 覆盖存在的理由。"""
        self.assertEqual(self.linter._rule_id_from_label("[17/17] 计划放行校验"), "SAGE-17")

    def test_all_labels_rule_ids_unique_and_sage17_reserved(self) -> None:
        labels = [
            "1.", "2.", "3.", "10.", "12.", "13.", "14.", "15.", "18.",  # 场景 A
            "[4/17]", "[5/17]", "[6/17]", "[7/17]",
            "[8/17]", "[9/17]", "[11/17]", "[16/17]",  # 场景 B 通用
        ]
        ids = [self.linter._rule_id_from_label(label) for label in labels]
        self.assertTrue(all(ids))
        self.assertEqual(len(ids), len(set(ids)), f"rule ID 重复: {ids}")
        self.assertNotIn("SAGE-17", ids)


if __name__ == "__main__":
    unittest.main()

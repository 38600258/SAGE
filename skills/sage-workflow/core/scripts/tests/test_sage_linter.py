from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()

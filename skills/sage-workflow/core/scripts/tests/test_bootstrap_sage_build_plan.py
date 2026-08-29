from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "bootstrap_sage.py"


def load_bootstrap():
    """以独立模块名加载 bootstrap_sage.py，允许 monkeypatch 模块级 CORE_ROOT/SKILL_ROOT。"""
    spec = importlib.util.spec_from_file_location("bootstrap_sage_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["bootstrap_sage_under_test"] = module
    spec.loader.exec_module(module)
    return module


class BuildPlanTests(unittest.TestCase):
    """TD-4 构建产物过滤 + TD-6 tests 透传名单（monkeypatch 模块级 CORE_ROOT/SKILL_ROOT 到临时目录）。"""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        # 构造独立临时 skill 布局，避免依赖真实仓库，保证用例可移植
        self.tmp_root = Path(self.temp_dir.name)
        self.core_root = self.tmp_root / "core"
        self.skill_root = self.tmp_root / "skill"
        self._mk_tree(self.core_root)
        self._mk_tree(self.skill_root / "adapters")
        self.mod = load_bootstrap()
        self.orig_core, self.orig_skill = self.mod.CORE_ROOT, self.mod.SKILL_ROOT
        self.mod.CORE_ROOT = self.core_root
        self.mod.SKILL_ROOT = self.skill_root
        self.repo_root = self.tmp_root / "repo"
        self.repo_root.mkdir()

    def tearDown(self) -> None:
        self.mod.CORE_ROOT, self.mod.SKILL_ROOT = self.orig_core, self.orig_skill
        self.temp_dir.cleanup()

    def _mk_tree(self, root: Path) -> None:
        # 最小可配置目录骨架：prompts/templates/guides/methodology/scaffold/githooks + scripts/tests
        for d in ("prompts", "templates", "guides", "methodology", "scaffold", "githooks"):
            (root / d).mkdir(parents=True)
        (root / "scripts" / "tests").mkdir(parents=True)

    def plan_paths(self) -> tuple[list[str], list[str]]:
        """返回 copied 源路径清单与目标路径清单（均转 str 便于断言）。"""
        sources, targets = [], []
        for source, target, _ in self.mod.build_plan(self.repo_root):
            sources.append(str(source))
            targets.append(str(target))
        return sources, targets

    def _target_has(self, targets: list[str], rel: str) -> bool:
        # 用 as_posix 归一化 Windows 反斜杠分隔符，使断言平台无关
        return any(Path(t).as_posix().endswith(rel) for t in targets)

    def test_filter_build_artifacts(self) -> None:
        # 在 core 与 adapters 下各埋一个 __pycache__ 缓存文件 + 一个 .pyc 文件
        cached_prompt = self.core_root / "prompts" / "__pycache__" / "reviewer.cpython.pyc"
        cached_prompt.parent.mkdir(parents=True)
        cached_prompt.write_bytes(b"p")
        pyc_guide = self.core_root / "guides" / "guide.pyc"
        pyc_guide.write_bytes(b"p")
        adapter_pyc = self.skill_root / "adapters" / "codex" / "__pycache__" / "provision.cpython.pyc"
        adapter_pyc.parent.mkdir(parents=True)
        adapter_pyc.write_bytes(b"p")

        sources, _ = self.plan_paths()
        for artifact in (str(cached_prompt), str(pyc_guide), str(adapter_pyc)):
            self.assertNotIn(artifact, sources, f"构建产物应被过滤：{artifact}")

    def test_tests_transmission_list(self) -> None:
        # TD-6：透传 test_sage_linter.py 与 __init__.py，不透传 test_dispatch_phase.py
        # 仅透传固定名单，构造同目录三个文件模拟：可透传与不可透传
        linter_src = self.core_root / "scripts" / "tests" / "test_sage_linter.py"
        linter_src.write_text("# linter test\n", encoding="utf-8")
        (self.core_root / "scripts" / "tests" / "test_dispatch_phase.py").write_text(
            "# dispatch test\n", encoding="utf-8"
        )
        (self.core_root / "scripts" / "tests" / "test_bootstrap_sage_build_plan.py").write_text(
            "# bootstrap plan test\n", encoding="utf-8"
        )
        (self.core_root / "scripts" / "tests" / "__init__.py").write_text(
            "", encoding="utf-8"
        )

        _, targets = self.plan_paths()
        # 透传项存在
        self.assertTrue(self._target_has(targets, "scripts/tests/test_sage_linter.py"))
        # __init__.py 透传
        self.assertTrue(self._target_has(targets, "scripts/tests/__init__.py"))
        # 不透传项不存在（固定白名单：仅 linter test + __init__）
        self.assertFalse(self._target_has(targets, "test_dispatch_phase.py"))
        self.assertFalse(self._target_has(targets, "test_bootstrap_sage_build_plan.py"))

    def test_scripts_copied(self) -> None:
        # 保证既有脚本复制逻辑未回归：sage_linter.py 与 sage_dispatch.py 仍在计划内
        _, targets = self.plan_paths()
        self.assertTrue(self._target_has(targets, "scripts/sage_linter.py"))
        self.assertTrue(self._target_has(targets, "scripts/sage_dispatch.py"))

    def test_template_transform_marker(self) -> None:
        # TD-7：templates 复制条目必须携带 "template" 转换（执行通道配置路径重写由 render_template 承载）
        (self.core_root / "templates" / "TASK-TEMPLATE.md").write_text(
            "- **执行通道配置**: skills/sage-workflow/core/guides/execution-channels.md\n",
            encoding="utf-8",
        )
        plan = self.mod.build_plan(self.repo_root)
        template_entries = [
            transform
            for source, _, transform in plan
            if Path(source).as_posix().endswith("/templates/TASK-TEMPLATE.md")
        ]
        self.assertEqual(template_entries, ["template"])

    def test_render_template_rewrites_core_guides_path(self) -> None:
        # TD-7：skill 仓库语境的权威 guides 路径在 bootstrap 目标项目中重写为 docs/guides/
        content = (
            "# 任务模板\n"
            "- **执行通道配置**: skills/sage-workflow/core/guides/execution-channels.md\n"
        )
        rendered = self.mod.render_template(content)
        self.assertIn("docs/guides/execution-channels.md", rendered)
        self.assertNotIn("skills/sage-workflow/core/guides/", rendered)
        # 无关内容不受影响
        self.assertIn("# 任务模板", rendered)


if __name__ == "__main__":
    unittest.main()
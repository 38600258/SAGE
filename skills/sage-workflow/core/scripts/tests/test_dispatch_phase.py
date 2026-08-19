from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "dispatch_phase.py"
SKILL_ROOT = Path(__file__).resolve().parents[3]


class DispatchPhaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name) / "repo"
        self.repo_root.mkdir()
        (self.repo_root / "docs" / "project").mkdir(parents=True)
        (self.repo_root / "prompts").mkdir()
        for role in ("reviewer", "coder", "closer"):
            (self.repo_root / "prompts" / f"{role}.md").write_text(
                f"# {role}\n\n执行角色契约。\n", encoding="utf-8"
            )
        self.task_path = self.repo_root / "docs" / "project" / "ACTIVE_TASK_T-001.md"
        self.task_path.write_text(self.task_content("dev"), encoding="utf-8")
        (self.repo_root / "src.txt").write_text("before\n", encoding="utf-8")
        self.run_process(["git", "init"], cwd=self.repo_root)
        self.run_process(["git", "config", "user.email", "sage@example.test"], cwd=self.repo_root)
        self.run_process(["git", "config", "user.name", "SAGE Test"], cwd=self.repo_root)
        self.run_process(["git", "add", "."], cwd=self.repo_root)
        self.run_process(["git", "commit", "-m", "chore(test): 初始化"], cwd=self.repo_root)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @staticmethod
    def task_content(phase: str) -> str:
        return f"""# TASK\n\n- **任务编号 (ID)**: T-001\n- **风险等级**: L2\n- **当前阶段**: {phase}\n- **项目根目录**: test\n- **功能分支**: feat/t-001-test\n\n## 阶段 1：初始化\n\n### 1.1 背景\n已冻结背景。\n\n### 1.2 决策\n已冻结决策。\n\n### 1.3 计划\n已冻结计划。\n\n### 1.4 范围\n已冻结范围。\n\n### 1.5 非目标\n已冻结非目标。\n\n## 阶段 2：计划评审\n\n### 2.1 评审意见\n待执行\n\n## 阶段 3：开发与验证\n\n### 3.1 任务进度追踪\n待执行\n\n### 3.2 证据链\n待执行\n\n## 阶段 4：代码审查\n\n### 4.1 代码评审\n待执行\n\n## 阶段 5：收尾与归档\n\n### 5.1 收尾记录\n待执行\n"""

    def run_process(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        expected: int = 0,
    ) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        self.assertEqual(
            completed.returncode,
            expected,
            msg=f"command={command}\nstdout={completed.stdout}\nstderr={completed.stderr}",
        )
        return completed

    def dispatch(self, *args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
        return self.run_process([sys.executable, str(SCRIPT), *args], expected=expected)

    def prepare(
        self,
        adapter: str = "codex",
        channel: str = "auto",
        model: str | None = None,
        adapter_file: Path | None = None,
    ) -> dict[str, object]:
        command = [
            "prepare",
            "--repo-root",
            str(self.repo_root),
            "--task-path",
            str(self.task_path),
            "--phase",
            "dev",
            "--adapter",
            adapter,
            "--channel",
            channel,
        ]
        if model:
            command.extend(("--model", model))
        if adapter_file:
            command.extend(("--adapter-file", str(adapter_file)))
        command.extend(("--format", "json"))
        completed = self.dispatch(*command)
        return json.loads(completed.stdout)

    def test_prepare_native_subagent_envelope_and_verify_real_output(self) -> None:
        receipt = self.prepare()
        self.assertEqual(receipt["action"], "spawn_subagent")
        self.assertEqual(receipt["channel"], "subagent")
        self.assertEqual(receipt["agent_type"], "sage_coder")
        self.assertEqual(
            receipt["model"],
            {
                "requested": "gpt-5.6-terra",
                "binding": "agent-registration",
                "source": "adapter",
            },
        )
        self.assertEqual(
            set(receipt["context"]),
            {"REPO_ROOT", "TASK_PATH", "ROLE_PROMPT", "PHASE"},
        )
        self.assertNotIn("L2", receipt["prompt"])

        receipt_path = str(receipt["receipt_path"])
        self.dispatch("verify", "--receipt", receipt_path, "--format", "json", expected=1)

        content = self.task_path.read_text(encoding="utf-8")
        content = content.replace("### 3.1 任务进度追踪\n待执行", "### 3.1 任务进度追踪\n- [x] 完成跨宿主派发实现")
        content = content.replace("### 3.2 证据链\n待执行", "### 3.2 证据链\n- [x] 单元测试和质量门禁均通过")
        self.task_path.write_text(content, encoding="utf-8")
        (self.repo_root / "src.txt").write_text("after\n", encoding="utf-8")

        verified = self.dispatch("verify", "--receipt", receipt_path, "--format", "json")
        payload = json.loads(verified.stdout)
        self.assertEqual(payload["status"], "completed")
        self.assertTrue(payload["verification"]["success"])

    def test_reviewer_requires_new_or_changed_verdict(self) -> None:
        content = self.task_content("code-review").replace(
            "### 4.1 代码评审\n待执行",
            "### 4.1 代码评审\n### 审查结果：WARN\n旧审查报告。",
        )
        self.task_path.write_text(content, encoding="utf-8")
        self.run_process(["git", "add", "."], cwd=self.repo_root)
        self.run_process(["git", "commit", "-m", "docs(test): 写入旧审查"], cwd=self.repo_root)
        completed = self.dispatch(
            "prepare",
            "--repo-root",
            str(self.repo_root),
            "--task-path",
            str(self.task_path),
            "--phase",
            "code-review",
            "--adapter",
            "codex",
            "--format",
            "json",
        )
        receipt = json.loads(completed.stdout)
        receipt_path = str(receipt["receipt_path"])

        content = self.task_path.read_text(encoding="utf-8").replace(
            "旧审查报告。",
            "旧审查报告。\n\n- 仅追加失败恢复记录。",
        )
        self.task_path.write_text(content, encoding="utf-8")
        self.dispatch("verify", "--receipt", receipt_path, "--format", "json", expected=1)

        content = self.task_path.read_text(encoding="utf-8").replace(
            "- 仅追加失败恢复记录。",
            "- 仅追加失败恢复记录。\n\n### 审查结果：OK\n新增独立审查报告。",
        )
        self.task_path.write_text(content, encoding="utf-8")
        verified = self.dispatch("verify", "--receipt", receipt_path, "--format", "json")
        payload = json.loads(verified.stdout)
        self.assertTrue(payload["verification"]["success"])

    def test_request_model_override_is_recorded(self) -> None:
        adapter_path = Path(self.temp_dir.name) / "request-model.json"
        adapter_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "id": "request-model",
                    "display_name": "请求级模型测试",
                    "native_subagent": {
                        "supported": True,
                        "invoker": "host",
                        "agent_types": {
                            "plan-review": "reviewer",
                            "dev": "coder",
                            "code-review": "reviewer",
                            "close": "closer",
                        },
                    },
                    "models": {
                        "dev": {
                            "id": "default-model",
                            "subagent_binding": "request",
                            "cli_binding": "command-argument",
                        }
                    },
                    "cli": {"supported": False, "invoker": "none"},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        receipt = self.prepare(
            adapter_file=adapter_path,
            model="override-model",
        )
        self.assertEqual(receipt["model"]["requested"], "override-model")
        self.assertEqual(receipt["model"]["binding"], "request")
        self.assertEqual(receipt["model"]["source"], "argument")

    def test_agent_registration_rejects_single_dispatch_override(self) -> None:
        completed = self.dispatch(
            "prepare",
            "--repo-root",
            str(self.repo_root),
            "--task-path",
            str(self.task_path),
            "--phase",
            "dev",
            "--adapter",
            "codex",
            "--model",
            "other-model",
            expected=2,
        )
        self.assertIn("宿主 Agent 注册固定", completed.stderr)

    def test_cli_model_must_be_consumed_by_command_placeholder(self) -> None:
        receipt = self.prepare(adapter="cli", model="cli-model")
        helper = Path(self.temp_dir.name) / "model_agent.py"
        helper.write_text(
            """from pathlib import Path
import sys
task = Path(sys.argv[1])
repo = Path(sys.argv[2])
model = sys.argv[3]
content = task.read_text(encoding='utf-8')
content = content.replace('### 3.1 任务进度追踪\\n待执行', '### 3.1 任务进度追踪\\n- [x] CLI 已完成实现')
content = content.replace('### 3.2 证据链\\n待执行', '### 3.2 证据链\\n- [x] CLI 自动验证已通过')
task.write_text(content, encoding='utf-8')
(repo / 'model.txt').write_text(model, encoding='utf-8')
""",
            encoding="utf-8",
        )
        command_json = json.dumps(
            [sys.executable, str(helper), "{task_path}", "{repo_root}", "{model}"],
            ensure_ascii=False,
        )
        completed = self.dispatch(
            "run-cli",
            "--receipt",
            str(receipt["receipt_path"]),
            "--command-json",
            command_json,
            "--format",
            "json",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual((self.repo_root / "model.txt").read_text(encoding="utf-8"), "cli-model")

    def test_cli_model_without_placeholder_is_blocked(self) -> None:
        receipt = self.prepare(adapter="cli", model="cli-model")
        completed = self.dispatch(
            "run-cli",
            "--receipt",
            str(receipt["receipt_path"]),
            "--command-json",
            json.dumps([sys.executable, "-c", "pass"]),
            expected=2,
        )
        self.assertIn("未消费 {model}", completed.stderr)

    def test_cli_model_placeholder_without_selected_model_is_blocked(self) -> None:
        receipt = self.prepare(adapter="cli")
        completed = self.dispatch(
            "run-cli",
            "--receipt",
            str(receipt["receipt_path"]),
            "--command-json",
            json.dumps([sys.executable, "-c", "pass", "{model}"]),
            expected=2,
        )
        self.assertIn("未解析到模型", completed.stderr)

    def test_codex_cli_fallback_requires_reason_and_authorization(self) -> None:
        completed = self.dispatch(
            "prepare",
            "--repo-root",
            str(self.repo_root),
            "--task-path",
            str(self.task_path),
            "--phase",
            "dev",
            "--adapter",
            "codex",
            "--channel",
            "cli",
            expected=2,
        )
        self.assertIn("--fallback-reason", completed.stderr)
        self.assertIn("--fallback-authorized", completed.stderr)

    def test_cli_channel_executes_command_array_and_verifies(self) -> None:
        receipt = self.prepare(adapter="cli")
        self.assertEqual(receipt["action"], "run_cli")
        helper = Path(self.temp_dir.name) / "fake_agent.py"
        helper.write_text(
            """from pathlib import Path\nimport sys\ntask = Path(sys.argv[1])\nrepo = Path(sys.argv[2])\ncontent = task.read_text(encoding='utf-8')\ncontent = content.replace('### 3.1 任务进度追踪\\n待执行', '### 3.1 任务进度追踪\\n- [x] CLI 已完成实现')\ncontent = content.replace('### 3.2 证据链\\n待执行', '### 3.2 证据链\\n- [x] CLI 自动验证已通过')\ntask.write_text(content, encoding='utf-8')\n(repo / 'cli-output.txt').write_text('ok\\n', encoding='utf-8')\n""",
            encoding="utf-8",
        )
        command_json = json.dumps(
            [sys.executable, str(helper), "{task_path}", "{repo_root}"],
            ensure_ascii=False,
        )
        completed = self.dispatch(
            "run-cli",
            "--receipt",
            str(receipt["receipt_path"]),
            "--command-json",
            command_json,
            "--format",
            "json",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["cli_returncode"], 0)
        self.assertTrue((self.repo_root / "cli-output.txt").is_file())

    def test_cancel_marks_host_cancellation_requirement(self) -> None:
        receipt = self.prepare()
        completed = self.dispatch(
            "cancel",
            "--receipt",
            str(receipt["receipt_path"]),
            "--reason",
            "测试取消",
            "--format",
            "json",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "cancelled")
        self.assertTrue(payload["host_cancel_required"])


    def test_injected_channel_envelope_records_isolation_and_authorization(self) -> None:
        completed = self.dispatch(
            "prepare",
            "--repo-root",
            str(self.repo_root),
            "--task-path",
            str(self.task_path),
            "--phase",
            "dev",
            "--adapter",
            "generic-tool",
            "--channel",
            "injected",
            "--format",
            "json",
        )
        receipt = json.loads(completed.stdout)
        self.assertEqual(receipt["action"], "spawn_subagent")
        self.assertEqual(receipt["channel"], "injected")
        self.assertEqual(receipt["agent_type"], "sage_coder")
        self.assertEqual(receipt["injection"]["isolation"], "context-fresh")
        self.assertTrue(receipt["injection"]["requires_authorization"])

        receipt_path = str(receipt["receipt_path"])
        content = self.task_path.read_text(encoding="utf-8")
        content = content.replace(
            "### 3.1 任务进度追踪\n待执行", "### 3.1 任务进度追踪\n- [x] 注入式子代理已完成实现"
        )
        content = content.replace("### 3.2 证据链\n待执行", "### 3.2 证据链\n- [x] 注入式子代理验证已通过")
        self.task_path.write_text(content, encoding="utf-8")
        (self.repo_root / "injected.txt").write_text("ok\n", encoding="utf-8")
        verified = self.dispatch("verify", "--receipt", receipt_path, "--format", "json")
        payload = json.loads(verified.stdout)
        self.assertTrue(payload["verification"]["success"])

    def test_injected_channel_requires_adapter_declaration(self) -> None:
        completed = self.dispatch(
            "prepare",
            "--repo-root",
            str(self.repo_root),
            "--task-path",
            str(self.task_path),
            "--phase",
            "dev",
            "--adapter",
            "codex",
            "--channel",
            "injected",
            expected=2,
        )
        self.assertIn("注入式", completed.stderr)

    def test_doctor_reports_channel_availability(self) -> None:
        completed = self.dispatch("doctor", "--adapter", "generic-tool", "--format", "json")
        payload = json.loads(completed.stdout)
        channels = {check["channel"]: check for check in payload["checks"]}
        self.assertFalse(channels["subagent"]["available"])
        self.assertTrue(channels["injected"]["available"])
        self.assertEqual(payload["recommended_channel"], "injected")

    def test_doctor_cli_probe_without_command_is_unavailable(self) -> None:
        completed = self.dispatch("doctor", "--adapter", "cli", "--format", "json", expected=1)
        payload = json.loads(completed.stdout)
        channels = {check["channel"]: check for check in payload["checks"]}
        self.assertTrue(channels["cli"]["declared"])
        self.assertFalse(channels["cli"]["available"])
        self.assertIsNone(payload["recommended_channel"])

    def test_provision_claude_code_generates_markdown_agents(self) -> None:
        target = Path(self.temp_dir.name) / "claude-agents"
        completed = self.dispatch(
            "provision",
            "--adapter",
            "claude-code",
            "--target-dir",
            str(target),
            "--format",
            "json",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["adapter"], "claude-code")
        self.assertEqual([item["status"] for item in payload["results"]], ["written", "written", "written"])
        reviewer = (target / "sage-reviewer.md").read_text(encoding="utf-8")
        self.assertIn("name: sage-reviewer", reviewer)
        self.assertIn("tools: Read, Write, Edit, Grep, Glob, Bash", reviewer)
        self.assertIn("ROLE_PROMPT", reviewer)
        coder = (target / "sage-coder.md").read_text(encoding="utf-8")
        self.assertIn("name: sage-coder", coder)
        self.assertIn("SAGE coder 子代理", coder)

    def test_provision_codex_toml_uses_adapter_models_and_skips_existing(self) -> None:
        target = Path(self.temp_dir.name) / "codex-agents"
        self.dispatch(
            "provision",
            "--adapter",
            "codex",
            "--target-dir",
            str(target),
            "--format",
            "json",
        )
        reviewer = (target / "sage-reviewer.toml").read_text(encoding="utf-8")
        self.assertIn('model = "gpt-5.6-sol"', reviewer)
        self.assertIn('model_provider = "codex_shim"', reviewer)
        self.assertIn('sandbox_mode = "read-only"', reviewer)
        coder = (target / "sage-coder.toml").read_text(encoding="utf-8")
        self.assertIn('model = "gpt-5.6-terra"', coder)
        self.assertIn('sandbox_mode = "workspace-write"', coder)

        # 未加 --force 时对已存在注册文件跳过（skips_existing 语义）
        completed = self.dispatch(
            "provision",
            "--adapter",
            "codex",
            "--target-dir",
            str(target),
            "--format",
            "json",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual([item["status"] for item in payload["results"]], ["skipped", "skipped", "skipped"])

        # --force 覆盖已存在注册文件
        completed = self.dispatch(
            "provision",
            "--adapter",
            "codex",
            "--target-dir",
            str(target),
            "--force",
            "--format",
            "json",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual([item["status"] for item in payload["results"]], ["written", "written", "written"])

    def test_provision_codex_passes_model_provider(self) -> None:
        target = Path(self.temp_dir.name) / "codex-provider"
        self.dispatch(
            "provision",
            "--adapter",
            "codex",
            "--target-dir",
            str(target),
            "--model-provider",
            "custom_shim",
            "--format",
            "json",
        )
        reviewer = (target / "sage-reviewer.toml").read_text(encoding="utf-8")
        self.assertIn('model_provider = "custom_shim"', reviewer)

    def test_provision_rejects_model_provider_for_non_toml_adapter(self) -> None:
        target = Path(self.temp_dir.name) / "claude-provider"
        completed = self.dispatch(
            "provision",
            "--adapter",
            "claude-code",
            "--target-dir",
            str(target),
            "--model-provider",
            "custom_shim",
            expected=2,
        )
        self.assertIn("仅 codex", completed.stderr)

    def test_provision_rejects_adapters_without_provision_script(self) -> None:
        for adapter in ("cli", "generic-tool"):
            with self.subTest(adapter=adapter):
                completed = self.dispatch(
                    "provision",
                    "--adapter",
                    adapter,
                    "--target-dir",
                    str(Path(self.temp_dir.name) / f"{adapter}-agents"),
                    expected=2,
                )
                self.assertIn("不提供子代理生成", completed.stderr)
                # TD-2：语义修正后不得再混入 "cli/generic-tool" 误导后缀
                self.assertNotIn("cli/generic-tool 无原生", completed.stderr)

    def test_provision_rejects_unknown_adapter(self) -> None:
        completed = self.dispatch(
            "provision",
            "--adapter",
            "nope",
            "--target-dir",
            str(Path(self.temp_dir.name) / "nope-agents"),
            expected=2,
        )
        # TD-2：未知 adapter 报"找不到 adapter"（含排查提示），而非误报"不提供子代理生成"
        self.assertIn("找不到 adapter", completed.stderr)

    def test_provision_prefers_local_adapter_script(self) -> None:
        local_dir = self.repo_root / "docs" / "guides" / "execution-adapters" / "codex"
        local_dir.mkdir(parents=True)
        # 项目本地 provision.py：写入 marker 文件以证明委托执行命中本地脚本而非 skill 内置
        (local_dir / "provision.py").write_text(
            "from pathlib import Path\n"
            "import sys\n"
            "target = Path(sys.argv[sys.argv.index('--target-dir') + 1])\n"
            "target.mkdir(parents=True, exist_ok=True)\n"
            "(target / 'local-provision-marker.txt').write_text('local', encoding='utf-8')\n",
            encoding="utf-8",
        )
        target = Path(self.temp_dir.name) / "local-agents"
        self.dispatch(
            "provision",
            "--adapter",
            "codex",
            "--repo-root",
            str(self.repo_root),
            "--target-dir",
            str(target),
        )
        marker = (target / "local-provision-marker.txt").read_text(encoding="utf-8")
        self.assertEqual(marker, "local")

    def test_provision_role_filter_is_passed_through(self) -> None:
        target = Path(self.temp_dir.name) / "role-agents"
        completed = self.dispatch(
            "provision",
            "--adapter",
            "claude-code",
            "--target-dir",
            str(target),
            "--role",
            "coder",
            "--format",
            "json",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual([item["role"] for item in payload["results"]], ["coder"])
        self.assertTrue((target / "sage-coder.md").is_file())
        self.assertFalse((target / "sage-reviewer.md").exists())


if __name__ == "__main__":
    unittest.main()

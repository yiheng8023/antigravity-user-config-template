"""使用临时用户目录验证恢复、同步和命令护栏的数据边界。"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import install
import knowledge
import memory
import safety
import clean


class TemporaryHome(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="antigravity-test-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.config = self.home / ".gemini/config"
        self.cli = self.home / ".gemini/antigravity-cli"

    def write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def snapshot(self):
        return {p.relative_to(self.home).as_posix(): p.read_bytes() for p in self.home.rglob("*") if p.is_file()}

    def run_install(self, *args):
        env = dict(os.environ, HOME=str(self.home), USERPROFILE=str(self.home))
        result = subprocess.run([sys.executable, "-B", str(REPO / "scripts/install.py"), *args], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        return result

    def test_install_preserves_permissions_plugins_and_unknown_keys(self):
        original = {"plugins": {"gdocs": {"enabled": False, "custom": 7}}, "userSettings": {"permissionPreset": "custom", "internetAccessPolicy": "deny", "allowAgentAccessNonWorkspaceFiles": False, "remoteControlEnabled": False, "futureSetting": 2}, "futureRoot": [1]}
        self.write(self.config / "config.json", original)
        result = self.run_install("--skip-rules")
        self.assertEqual(result.returncode, 0, result.stderr)
        actual = json.loads((self.config / "config.json").read_text())
        self.assertEqual(actual["plugins"]["gdocs"], original["plugins"]["gdocs"])
        for key, value in original["userSettings"].items():
            self.assertEqual(actual["userSettings"][key], value)
        self.assertEqual(actual["futureRoot"], [1])

    def test_existing_cli_trust_is_not_expanded(self):
        for trusted in ([], [str(self.home / "one-project")]):
            with self.subTest(trusted=trusted):
                self.write(self.cli / "settings.json", {"trustedWorkspaces": trusted, "toolPermission": "request-review"})
                result = self.run_install("--skip-rules")
                self.assertEqual(result.returncode, 0, result.stderr)
                actual = json.loads((self.cli / "settings.json").read_text())
                self.assertEqual(actual["trustedWorkspaces"], trusted)
                self.assertEqual(actual["toolPermission"], "request-review")

    def test_custom_hooks_and_disabled_guard_are_preserved(self):
        custom = {"Stop": [{"command": "custom-stop"}]}
        self.write(self.config / "hooks.json", {"custom": custom, "git-guard": {"enabled": False, "PreToolUse": [{"hooks": [{"command": "custom-guard"}]}]}})
        result = self.run_install("--skip-rules")
        self.assertEqual(result.returncode, 0, result.stderr)
        actual = json.loads((self.config / "hooks.json").read_text())
        self.assertEqual(actual["custom"], custom)
        self.assertFalse(actual["git-guard"]["enabled"])
        self.assertEqual(actual["git-guard"]["PreToolUse"][0]["hooks"][0]["command"], "custom-guard")

    def test_mcp_credentials_and_disabled_choice_are_preserved(self):
        existing = {"mcpServers": {"example": {"disabled": True, "env": {"CUSTOM": "local-only"}}}, "future": True}
        self.write(self.config / "mcp_config.json", existing)
        result = self.run_install("--skip-rules")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.config / "mcp_config.json").read_text()), existing)

    def test_invalid_json_anywhere_causes_zero_writes(self):
        paths = [self.config / "config.json", self.config / "hooks.json", self.config / "mcp_config.json", self.cli / "settings.json"]
        for path in paths:
            for content in ('{"broken":', '[]', 'null', ''):
                with self.subTest(file=path.name, content=content):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content)
                    before = self.snapshot()
                    result = self.run_install()
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(self.snapshot(), before)
                    path.unlink()

    def test_invalid_sections_cause_zero_writes(self):
        for rel, content in [("config.json", {"userSettings": []}), ("config.json", {"plugins": {"bad": False}}), ("mcp_config.json", {"mcpServers": []}), ("hooks.json", {"git-guard": {"PreToolUse": None}})]:
            with self.subTest(rel=rel, content=content):
                self.write(self.config / rel, content)
                before = self.snapshot()
                result = self.run_install()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.snapshot(), before)
                (self.config / rel).unlink()

    def test_dry_run_and_unknown_arguments_have_zero_writes(self):
        for flags, expected in [(('--dry-run',), 0), (('--typo',), 2)]:
            result = self.run_install(*flags)
            self.assertEqual(result.returncode, expected, result.stderr)
            self.assertEqual(self.snapshot(), {})

    def test_install_is_idempotent(self):
        result = self.run_install("--skip-rules")
        self.assertEqual(result.returncode, 0, result.stderr)
        before = self.snapshot()
        result = self.run_install("--skip-rules")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_rules_and_existing_memory_survive_install(self):
        self.config.mkdir(parents=True)
        (self.config / "AGENTS.md").write_text("private existing rules")
        topic = self.config / "memory/MEMORY.md"
        topic.parent.mkdir()
        topic.write_text("private existing index")
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.config / "AGENTS.md").read_text(), "private existing rules")
        self.assertEqual(topic.read_text(), "private existing index")

    def test_guard_runs_from_unrelated_working_directory(self):
        self.write(self.config / "hooks.json", {"git-guard": {"enabled": False, "PreToolUse": [{"matcher": "run_command", "hooks": [{"command": "node ./hooks/git-guard.js"}]}]}})
        result = self.run_install("--skip-rules")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads((self.config / "hooks.json").read_text())
        self.assertFalse(config["git-guard"]["enabled"])
        command = config["git-guard"]["PreToolUse"][0]["hooks"][0]["command"]
        result = subprocess.run(command, shell=True, cwd=self.home, input=json.dumps({"toolCall": {"args": {"CommandLine": "git -C project reset --hard"}}}), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["decision"], "force_ask")

    def test_concurrent_config_change_is_not_overwritten(self):
        target = self.config / "config.json"
        self.write(target, {"new": True})
        with self.assertRaises(ValueError):
            install.write_json(target, {"old": True}, b"{}", False)
        self.assertEqual(json.loads(target.read_text()), {"new": True})

    def test_bom_json_is_supported(self):
        self.config.mkdir(parents=True)
        (self.config / "config.json").write_text('{}', encoding="utf-8-sig")
        result = self.run_install("--skip-rules")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_empty_knowledge_source_never_prunes_target(self):
        source, target = self.home / "source", self.home / "target"
        source.mkdir()
        (source / "README.md").write_text("placeholder")
        self.write(target / "item/metadata.json", {"title": "real work"})
        before = self.snapshot()
        knowledge.copy_tree_contents(source, target, prune_stale=True)
        self.assertEqual(self.snapshot(), before)

    def test_knowledge_prune_requires_explicit_flag(self):
        source, target = self.home / "source", self.home / "target"
        self.write(source / "new/metadata.json", {})
        self.write(target / "old/metadata.json", {})
        lock = target / "knowledge.lock"
        lock.write_text("active lock")
        knowledge.copy_tree_contents(source, target)
        self.assertTrue((target / "old/metadata.json").exists())
        knowledge.copy_tree_contents(source, target, prune_stale=True)
        self.assertFalse((target / "old/metadata.json").exists())
        self.assertEqual(lock.read_text(), "active lock")

    def test_memory_prune_requires_explicit_flag(self):
        source, target = self.home / "source", self.home / "target"
        source.mkdir()
        target.mkdir()
        (source / "new.md").write_text("new")
        (target / "old.md").write_text("old")
        with patch.object(memory, "PRUNE", False):
            memory.sync(source, target, "restore")
        self.assertTrue((target / "old.md").exists())
        with patch.object(memory, "PRUNE", True):
            memory.sync(source, target, "restore")
        self.assertFalse((target / "old.md").exists())

    def test_knowledge_backup_blocks_secrets_before_copy(self):
        source, target = self.home / "source", self.home / "target"
        secret = "ghp_" + "x" * 30
        self.write(source / "item/metadata.json", {"title": secret})
        stdout = io.StringIO()
        with patch.object(knowledge, "LIVE_DESKTOP_KNOWLEDGE", source), patch.object(knowledge, "LIVE_CLI_KNOWLEDGE", source), patch.object(knowledge, "REPO_KNOWLEDGE", target), patch.object(knowledge, "_is_template_repo", return_value=False), patch.object(sys, "argv", ["knowledge.py", "--backup"]), contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit):
                knowledge.main()
        self.assertFalse(target.exists())
        self.assertNotIn(secret, stdout.getvalue())
        self.assertNotIn(secret[:14], stdout.getvalue())

    def test_secret_scanner_keeps_values_out_of_diagnostics(self):
        for secret in ("ghp_" + "x" * 30, "sk-proj-" + "y" * 40, "Bearer " + "z" * 30):
            source = self.home / "source.md"
            source.write_text(secret)
            hits = safety.scan_files({source.name: source})
            self.assertTrue(hits)
            self.assertNotIn(secret, str(hits))
            self.assertNotIn(secret[:14], str(hits))
        self.assertFalse(safety.secret_labels('{"token":"${LOCAL_TOKEN}"}'))

    def test_template_backups_refuse_private_content(self):
        for module in (memory, knowledge):
            with patch.object(module, "_is_template_repo", return_value=True), patch.object(sys, "argv", ["sync.py", "--backup"]):
                with self.assertRaises(SystemExit):
                    module.main()

    def test_sync_refuses_escaping_symlink(self):
        source, outside = self.home / "source", self.home / "outside"
        source.mkdir()
        outside.mkdir()
        (outside / "secret.md").write_text("outside")
        try:
            (source / "escaped.md").symlink_to(outside / "secret.md")
        except OSError:
            self.skipTest("platform does not permit symlinks")
        with self.assertRaises(ValueError):
            memory._md_files(source)

    @unittest.skipUnless(os.name == "nt", "Windows junction regression")
    def test_knowledge_prune_preserves_empty_external_junction_tree(self):
        source, target, outside = self.home / "source", self.home / "target", self.home / "outside"
        self.write(source / "item/metadata.json", {})
        target.mkdir()
        (outside / "empty-child").mkdir(parents=True)
        junction = target / "external"
        result = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(junction), str(outside)], capture_output=True)
        if result.returncode:
            self.skipTest("junction creation is unavailable")
        try:
            with self.assertRaises(ValueError):
                knowledge.copy_tree_contents(source, target, prune_stale=True)
            self.assertTrue((outside / "empty-child").is_dir())
            self.assertFalse((target / "item").exists())
        finally:
            junction.rmdir()

    def test_runtime_cleaner_preserves_work_and_recent_crashes(self):
        root = self.home / ".gemini"
        files = [root / "config/config.json.bak-restore", root / "antigravity/scratch/work.py", root / "antigravity/brain/session/.tempmediaStorage/image.png", root / "antigravity/crashes/crash_recent.log"]
        for f in files:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("valuable")
        stale = root / "antigravity/crashes/crash_old.log"
        stale.write_text("old crash")
        os.utime(stale, (time.time() - 8 * 86400,) * 2)
        clean.clean_runtime(root)
        self.assertFalse(stale.exists())
        self.assertTrue(all(f.exists() for f in files))

    def test_cleaner_preserves_native_extension(self):
        (self.home / "extension.pyd").write_text("binary extension")
        clean.clean_repo(self.home)
        self.assertTrue((self.home / "extension.pyd").exists())


class GuardTests(unittest.TestCase):
    def decision(self, raw):
        result = subprocess.run(["node", str(REPO / "hooks/git-guard.js")], input=raw, text=True, capture_output=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_dangerous_commands_and_safe_counterexamples(self):
        danger = [
            "git reset --hard", "git -C project reset --hard", "git -c color.ui=false reset --hard",
            '"C:/Program Files/Git/cmd/git.exe" --git-dir=repo reset --hard',
            "git clean -fdx", "git clean --force", "git clean -f -e.env", "git clean -fe.env", "git clean -f -e -n", "git clean -f --exclude --dry-run", "git clean -f --exclude=-n",
            "git reset --hard>reset.log", "git reset --hard 2>reset.log", "git reset >reset.log --hard", "git reset 2>reset.log --hard", "git reset 2>&1 --hard", "git reset >'reset log' --hard", "git >reset.log reset --hard", "git push >push.log --force", "git push 2>&1 --force", "git branch -D old", "git branch --force --delete old", "git branch -df old",
            "git checkout -- file", "git checkout .", "git checkout -f", "git switch --discard-changes main",
            "git restore file", "git restore -SW file", "git restore --staged --worktree file",
            "git restore --staged a; git restore b", "git restore a; git restore --staged b",
            "git push --force origin main", "git push -f", "git push origin +HEAD:main", "git push --mirror",
            "git push origin :old", "git push origin --delete old", "git push -d origin old",
            "git stash drop", "git stash clear", "git reflog delete HEAD@{1}", "git update-ref -d refs/heads/old",
            "git filter-branch --all", "git gc --prune=now", 'sh -c "git -C repo reset --hard"',
        ]
        safe = [
            "git status --short", "git diff", "git branch -d merged", "git branch --delete merged",
            "git restore --staged file", "git restore -S file", "git restore --source=HEAD --staged file",
            "git push origin main", "git push --force-with-lease origin main", "git checkout main", "git switch main",
            "git clean -ndx", "git clean -nf", "git clean --dry-run --force", "git clean -f -e.env -n", "git status >status.log", "git reset >--hard", "git status 2>&1", "git stash list", "git gc", "npm test",
        ]
        for command, expected in [(c, "force_ask") for c in danger] + [(c, "allow") for c in safe]:
            with self.subTest(command=command):
                actual = self.decision(json.dumps({"toolCall": {"name": "run_command", "args": {"CommandLine": command}}}))
                self.assertEqual(actual["decision"], expected)

    def test_invalid_inputs_require_review(self):
        for raw in ('', '{broken', '{}', '[]', 'null', '{"toolCall":{"args":[]}}', '{"CommandLine":123}'):
            with self.subTest(raw=raw):
                self.assertEqual(self.decision(raw)["decision"], "force_ask")

    def test_command_is_not_echoed_in_hook_reason(self):
        marker = "private-command-argument"
        result = self.decision(json.dumps({"cmd": f"git reset --hard {marker}"}))
        self.assertEqual(result["decision"], "force_ask")
        self.assertNotIn(marker, json.dumps(result))


if __name__ == "__main__":
    unittest.main()

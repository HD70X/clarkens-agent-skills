"""Offline behavioral checks; never use the real OS credential or Google API."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import gemini as bridge
import install as installer


def response(parts, reason="STOP"):
    return {"candidates": [{"content": {"role": "model", "parts": parts}, "finishReason": reason}],
            "modelVersion": "gemini-test-explicit", "usageMetadata": {"totalTokenCount": 7}}


class FakeClient:
    key = "test-key-not-a-real-credential"

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def generate(self, model, contents, *args, **kwargs):
        self.requests.append((model, copy.deepcopy(contents)))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gemini-tests-")
        self.base = Path(self.temp.name).resolve()
        self.project = self.base / "project"
        self.project.mkdir()
        self.state = self.base / "private"
        self.state.mkdir()
        self.patches = [patch.object(bridge, "data_dir", return_value=self.state),
                        patch.dict(os.environ, {"CODEX_THREAD_ID": "task-alpha"}),
                        patch.object(bridge, "get_key", return_value=FakeClient.key)]
        for p in self.patches:
            p.start()
        self.tools = bridge.LocalTools(self.project, FakeClient.key)

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def cli(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = bridge.main(args)
        return code, json.loads(output.getvalue()) if output.getvalue() else None

    def authorize(self, mode="both"):
        return self.cli(["authorize", "--root", str(self.project), "--mode", mode,
                         "--user-approved", "--approval", "User authorizes this test task"])

    def run_state(self):
        return {"run_id": "a" * 32, "task_id": "task-alpha", "root": str(self.project),
                "model": "gemini-test-explicit", "contents": [{"role": "user", "parts": [{"text": "Fix the file"}]}],
                "max_turns": 5, "rounds": 0, "changed_files": [], "status": "ready",
                "pending": [], "results": {}, "timeout": 10, "max_output_tokens": 100, "thinking": None}

    def test_generation_requires_explicit_model_before_key_or_network(self):
        for args in (["ask"], ["agent", "start"]):
            with patch.object(bridge, "GoogleClient") as client, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    bridge.main(args + ["--root", str(self.project), "--prompt", "hi"])
                self.assertEqual(error.exception.code, 2)
                client.assert_not_called()

    def test_unicode_results_remain_json_on_legacy_windows_codepages(self):
        for encoding in ("cp1252", "gbk"):
            raw = io.BytesIO()
            text = io.TextIOWrapper(raw, encoding=encoding)
            value = {"text": "中文审查结果 ✅", "root": "C:/用户/项目"}
            with contextlib.redirect_stdout(text):
                bridge.emit(value)
            self.assertEqual(json.loads(raw.getvalue().decode(encoding)), value)
            text.detach()

    def test_no_grant_no_network(self):
        with patch.object(bridge, "GoogleClient") as client:
            with self.assertRaises(bridge.BridgeError):
                self.cli(["ask", "--root", str(self.project), "--model", "gemini-test-explicit", "--prompt", "hi"])
            client.assert_not_called()

    def test_task_and_project_authorizations_are_separate_from_model(self):
        self.authorize()
        grant = bridge.load_json(bridge.grant_path("task-alpha"))
        self.assertNotIn("model", grant)
        bridge.require_grant("task-alpha", self.project, "execute")
        other = self.base / "other"
        other.mkdir()
        with self.assertRaises(bridge.BridgeError):
            bridge.require_grant("task-alpha", other, "consult")
        with patch.dict(os.environ, {"CODEX_THREAD_ID": "task-beta"}):
            with self.assertRaises(bridge.BridgeError):
                bridge.task_id("task-alpha")
            with self.assertRaises(bridge.BridgeError):
                bridge.require_grant("task-beta", self.project, "execute")

    def test_consult_does_not_grant_execution(self):
        self.authorize("consult")
        with self.assertRaises(bridge.BridgeError):
            bridge.require_grant("task-alpha", self.project, "execute")

    def test_explicit_model_passed_unchanged_and_no_consult_tools(self):
        self.authorize()
        fake = FakeClient([response([{"text": "OK"}])])
        with patch.object(bridge, "GoogleClient", return_value=fake):
            code, result = self.cli(["ask", "--root", str(self.project), "--model", "gemini-test-explicit", "--prompt", "Hi"])
        self.assertEqual((code, result["text"]), (0, "OK"))
        self.assertEqual(fake.requests[0][0], "gemini-test-explicit")

    def test_file_hash_and_protected_paths(self):
        self.tools.invoke("write_file", {"path": "src/a.py", "content": "old"})
        original = self.tools.invoke("read_file", {"path": "src/a.py"})
        with self.assertRaises(bridge.BridgeError):
            self.tools.invoke("write_file", {"path": "src/a.py", "content": "new"})
        self.tools.invoke("write_file", {"path": "src/a.py", "content": "new", "expected_sha256": original["sha256"]})
        self.assertEqual((self.project / "src/a.py").read_text(), "new")
        with self.assertRaises(bridge.BridgeError):
            self.tools.invoke("write_file", {"path": "src/a.py", "content": "race", "expected_sha256": original["sha256"]})
        for value in ("../outside", ".env", ".env.local", ".git/config", "AGENTS.md", ".secrets/key.json", "key.pem"):
            with self.subTest(value=value), self.assertRaises(bridge.BridgeError):
                self.tools.path(value)

    def test_symlink_escape_blocked(self):
        outside = self.base / "outside"
        outside.mkdir()
        try:
            (self.project / "linked").symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation unavailable")
        with self.assertRaises(bridge.BridgeError):
            self.tools.invoke("write_file", {"path": "linked/oops", "content": "outside"})
        self.assertFalse((outside / "oops").exists())

    def test_commands_pause_then_resume_with_actual_results_and_signatures(self):
        self.authorize()
        first = response([
            {"functionCall": {"id": "write-1", "name": "write_file", "args": {"path": "answer.txt", "content": "42"}},
             "thoughtSignature": "opaque-signature"},
            {"functionCall": {"id": "cmd-1", "name": "run_command", "args": {"path": ".", "argv": ["python", "-m", "unittest"]}}}])
        fake = FakeClient([first, response([{"text": "Done"}])])
        run = self.run_state()
        with patch.object(bridge.subprocess, "run", side_effect=AssertionError("No model-command subprocess allowed")):
            bridge.drive(run, fake)
        self.assertEqual(run["status"], "needs_host")
        self.assertEqual(run["host_requests"][0]["index"], 1)
        self.assertEqual((self.project / "answer.txt").read_text(), "42")
        result = self.base / "result.json"
        bridge.save_json(result, {"exit_code": 0, "stdout": "passed", "stderr": ""})
        self.cli(["agent", "reply", "--run-id", run["run_id"], "--index", "1", "--result-file", str(result)])
        with self.assertRaises(bridge.BridgeError):
            self.cli(["agent", "reply", "--run-id", run["run_id"], "--index", "1", "--result-file", str(result)])
        with patch.object(bridge, "GoogleClient", return_value=fake):
            code, final = self.cli(["agent", "resume", "--run-id", run["run_id"]])
        self.assertEqual((code, final["status"]), (0, "completed"))
        self.assertEqual(final["changed_files"], ["answer.txt"])
        contents = fake.requests[1][1]
        self.assertEqual(contents[1], first["candidates"][0]["content"])
        command_response = contents[2]["parts"][1]["functionResponse"]
        self.assertEqual(command_response["id"], "cmd-1")
        self.assertEqual(command_response["response"]["stdout"], "passed")

    def test_api_error_no_retry_or_switch(self):
        run = self.run_state()
        fake = FakeClient([bridge.BridgeError("HTTP 404")])
        with self.assertRaises(bridge.BridgeError):
            bridge.drive(run, fake)
        self.assertEqual(run["status"], "error")
        self.assertEqual(len(fake.requests), 1)
        self.assertEqual(run["model"], "gemini-test-explicit")

    def test_incomplete_does_not_execute_returned_tool(self):
        run = self.run_state()
        fake = FakeClient([response([{"functionCall": {"name": "write_file", "args": {
            "path": "bad.txt", "content": "no"}}}], "MAX_TOKENS")])
        bridge.drive(run, fake)
        self.assertEqual(run["status"], "incomplete")
        self.assertFalse((self.project / "bad.txt").exists())

    def test_turn_limit_does_not_invent_completion(self):
        run = self.run_state()
        run["max_turns"] = 1
        fake = FakeClient([response([{"functionCall": {"name": "write_file", "args": {
            "path": "draft.txt", "content": "draft"}}}])])
        bridge.drive(run, fake)
        self.assertEqual(run["status"], "turn_limit")
        self.assertEqual(len(fake.requests), 1)

    def test_sensitive_content_is_not_sent_or_written(self):
        (self.project / "contains.txt").write_text(FakeClient.key)
        with self.assertRaises(bridge.BridgeError):
            self.tools.invoke("read_file", {"path": "contains.txt"})
        with self.assertRaises(bridge.BridgeError):
            self.tools.invoke("write_file", {"path": "out.txt", "content": FakeClient.key})
        self.assertNotIn(FakeClient.key, bridge.redact(FakeClient.key, FakeClient.key))

    def test_revoke_stops_continuation(self):
        self.authorize()
        run = self.run_state()
        bridge.check_run(run, None)
        self.cli(["revoke"])
        with self.assertRaises(bridge.BridgeError):
            bridge.check_run(run, None)

    def test_install_complete_skill_and_upgrade_without_credential(self):
        target = self.base / "install/skills/gemini-bridge"
        result = installer.install(target)
        self.assertFalse(result["credential_copied"])
        for name in ("SKILL.md", "agents/openai.yaml", "scripts/credentials.py", "references/installation.md"):
            self.assertTrue((target / name).is_file())
        (target / "old-file").write_text("old")
        with self.assertRaises(ValueError):
            installer.install(target)
        result = installer.install(target, upgrade=True)
        self.assertFalse((target / "old-file").exists())
        self.assertTrue((Path(result["backup"]) / "old-file").exists())
        self.assertFalse(target in Path(result["backup"]).parents)


if __name__ == "__main__":
    unittest.main()

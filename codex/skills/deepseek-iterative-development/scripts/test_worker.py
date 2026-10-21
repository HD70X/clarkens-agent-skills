#!/usr/bin/env python3
"""Offline behavioral checks using synthetic credentials, Git worktrees and a fake CLI."""
import argparse
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

import configure_worker as configuration
import worker

FAKE = r'''#!/usr/bin/env python3
import json, os, pathlib, subprocess, sys, time
if '--help' in sys.argv:
    print('--profile --json --output-last-message')
    sys.exit(0)
mode = os.environ.get('DEEPSEEK_TEST_MODE', 'complete')
print(json.dumps({'type':'thread.started','thread_id':'offline-fake-thread'}), flush=True)
pathlib.Path(os.environ['DEEPSEEK_TEST_MARKER']).write_text('started')
if mode in ('wait', 'orphan'):
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(90)'])
    pathlib.Path(os.environ['DEEPSEEK_TEST_CHILD']).write_text(str(child.pid))
    if mode == 'wait': time.sleep(90)
if mode == 'fail':
    print(json.dumps({'type':'turn.failed','error':{'message':'offline failure'}}), flush=True)
    sys.exit(1)
sys.stdin.read()
target = pathlib.Path('notes.txt' if mode == 'outside' else 'src/main.txt')
target.write_text('worker change')
if mode == 'commit':
    subprocess.run(['git','add','src/main.txt'],check=True)
    subprocess.run(['git','-c','user.name=Offline','-c','user.email=offline@example.invalid','commit','-qm','fake'],check=True)
if mode == 'stage-user-work':
    subprocess.run(['git','add','notes.txt'],check=True)
if mode == 'alter-index':
    blob = subprocess.run(['git','hash-object','-w','--stdin'],input=b'changed index only',capture_output=True,check=True).stdout.decode().strip()
    subprocess.run(['git','update-index','--cacheinfo','100644,'+blob+',notes.txt'],check=True)
if mode == 'ignored-write':
    pathlib.Path('.scratch').mkdir(exist_ok=True)
    pathlib.Path('.scratch/hidden.txt').write_text('outside declared source scope')
report = pathlib.Path(sys.argv[sys.argv.index('--output-last-message')+1])
report.write_text('Implemented; actual independent acceptance is not performed.')
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':12,'output_tokens':7,'untrusted_note':'discard'}}),flush=True)
'''


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="codex-deepseek-offline-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.home = self.root / "codex-config"
        self.repo = self.root / "project with spaces"
        self.repo.mkdir()
        self.git("init", "-q")
        (self.repo / "src").mkdir()
        (self.repo / "src/main.txt").write_text("baseline")
        (self.repo / "notes.txt").write_text("preserve")
        self.git("add", ".")
        self.git("-c", "user.name=Offline", "-c", "user.email=offline@example.invalid", "commit", "-qm", "baseline")
        self.control_dir = self.root / "run"
        self.control_dir.mkdir()
        self.state_path = self.control_dir / "state.json"
        module = worker.control()
        initial = module.initialize(argparse.Namespace(
            run_id="offline-run", coordinator_id="offline", project_root=str(self.repo),
            deadline_utc=None, hours=1, closing_minutes=1,
        ), datetime.now(timezone.utc))
        module.atomic_write(self.state_path, initial)
        self.task_file = self.control_dir / "task.md"
        self.task_file.write_text("Implement a bounded change and report checks.")
        self.manifest = self.control_dir / "attempt-1.task.json"
        self.out = self.control_dir / "attempt-1"
        self.fake = self.root / "fake-codex"
        self.fake.write_text(FAKE)
        self.fake.chmod(0o700)
        source = {"models": [{"slug": "deepseek-flash", "context_window": 1000,
                              "base_instructions": "REMOTE PROMPT MUST NOT SURVIVE",
                              "supported_reasoning_levels": [{"effort": "high"}]}]}
        catalog = configuration.build_catalog(source, "deepseek-flash", "high")
        configuration.install(self.home, "deepseek-flash", "high", "deepseek-worker", "env", catalog)
        self.settings = self.home / "deepseek-worker.settings.json"
        self.home_mock = mock.patch.object(configuration, "codex_home", return_value=self.home)
        self.home_mock.start()
        self.addCleanup(self.home_mock.stop)
        self.environment = mock.patch.dict(os.environ, {
            "DEEPSEEK_API_KEY": "offline-synthetic-credential",
            "DEEPSEEK_TEST_MODE": "complete", "DEEPSEEK_TEST_MARKER": str(self.root / "started"),
            "DEEPSEEK_TEST_CHILD": str(self.root / "child.pid"),
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True).stdout

    def prepare(self, timeout=10):
        worker.prepare(argparse.Namespace(
            state=str(self.state_path), workspace=str(self.repo), task_id="bounded-code", attempt=1,
            task_file=str(self.task_file), output_dir=str(self.out), manifest=str(self.manifest),
            allow=["src"], timeout_seconds=timeout,
        ))
        return json.loads(self.manifest.read_text())

    def run_task(self, task):
        with worker.workspace_lock(self.repo):
            return worker.execute(task, self.settings, str(self.fake))

    def update_control(self, mutate):
        state = json.loads(self.state_path.read_text())
        mutate(state)
        worker.write_json(self.state_path, state)

    def assert_child_stopped(self):
        pid = int((self.root / "child.pid").read_text())
        result = subprocess.run(["ps", "-p", str(pid), "-o", "stat="], capture_output=True)
        self.assertTrue(result.returncode != 0 or result.stdout.strip().startswith(b"Z"), result.stdout)

    def test_completed_result_is_unreviewed_and_records_actual_diff(self):
        receipt = self.run_task(self.prepare())
        self.assertEqual(receipt["status"], "completed_unreviewed")
        self.assertEqual(receipt["independent_acceptance"], "not_performed")
        self.assertEqual(receipt["changed_paths"], ["src/main.txt"])
        self.assertEqual(receipt["out_of_scope_paths"], [])
        self.assertIsNone(receipt["effective_model"])
        self.assertEqual(receipt["events"]["usage"], [{"input_tokens": 12, "output_tokens": 7}])
        self.assertTrue(receipt["process_group_stopped"])
        self.assertEqual(json.loads((self.out / "receipt.json").read_text())["run_id"], "offline-run")

    def test_missing_credentials_request_takeover_without_starting_cli(self):
        task = self.prepare()
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}):
            receipt = self.run_task(task)
        self.assertEqual(receipt["reason"], "missing_credential")
        self.assertEqual(receipt["status"], "needs_codex_takeover")
        self.assertFalse(receipt["worker_process_started"])
        self.assertFalse((self.root / "started").exists())

    def test_worker_error_preserves_takeover_and_does_not_accept(self):
        os.environ["DEEPSEEK_TEST_MODE"] = "fail"
        receipt = self.run_task(self.prepare())
        self.assertEqual(receipt["status"], "needs_codex_takeover")
        self.assertEqual(receipt["reason"], "worker_failed")

    def test_out_of_scope_edit_to_existing_dirty_file_is_detected(self):
        (self.repo / "notes.txt").write_text("user's uncommitted work")
        os.environ["DEEPSEEK_TEST_MODE"] = "outside"
        receipt = self.run_task(self.prepare())
        self.assertEqual(receipt["status"], "needs_codex_takeover")
        self.assertEqual(receipt["out_of_scope_paths"], ["notes.txt"])
        self.assertEqual((self.repo / "notes.txt").read_text(), "worker change")

    def test_worker_commit_is_detected_without_reverting_user_work(self):
        os.environ["DEEPSEEK_TEST_MODE"] = "commit"
        receipt = self.run_task(self.prepare())
        self.assertEqual(receipt["status"], "needs_codex_takeover")
        self.assertNotEqual(receipt["input_version"], receipt["output_version"])

    def test_ignored_out_of_scope_write_is_detected(self):
        (self.repo / ".gitignore").write_text(".scratch/\n")
        os.environ["DEEPSEEK_TEST_MODE"] = "ignored-write"
        receipt = self.run_task(self.prepare())
        self.assertEqual(receipt["status"], "needs_codex_takeover")
        self.assertIn(".scratch/hidden.txt", receipt["out_of_scope_paths"])

    def test_staging_user_dirty_work_is_detected(self):
        (self.repo / "notes.txt").write_text("user work")
        os.environ["DEEPSEEK_TEST_MODE"] = "stage-user-work"
        receipt = self.run_task(self.prepare())
        self.assertEqual(receipt["status"], "needs_codex_takeover")
        self.assertIn("notes.txt", receipt["out_of_scope_paths"])

    def test_index_blob_change_with_same_mm_status_is_detected(self):
        (self.repo / "notes.txt").write_text("staged user version")
        self.git("add", "notes.txt")
        (self.repo / "notes.txt").write_text("working user version")
        os.environ["DEEPSEEK_TEST_MODE"] = "alter-index"
        receipt = self.run_task(self.prepare())
        self.assertEqual(receipt["status"], "needs_codex_takeover")
        self.assertIn("notes.txt", receipt["out_of_scope_paths"])
        self.assertEqual((self.repo / "notes.txt").read_text(), "working user version")

    def test_settings_model_and_effort_must_match_reviewed_catalog_and_profile(self):
        for key, value in (("model", "unreviewed-model"), ("effort", "unsupported-effort")):
            settings = json.loads(self.settings.read_text())
            original = dict(settings)
            settings[key] = value
            worker.write_json(self.settings, settings)
            with self.assertRaises(worker.Refused):
                worker.doctor(self.settings, str(self.fake))
            worker.write_json(self.settings, original)

    def test_input_changes_refuse_dispatch(self):
        task = self.prepare()
        (self.repo / "src/main.txt").write_text("new user work")
        with self.assertRaises(worker.Refused) as result:
            self.run_task(task)
        self.assertEqual(result.exception.code, "stale_input")
        self.assertFalse((self.root / "started").exists())

    def test_instruction_changes_refuse_dispatch(self):
        task = self.prepare()
        self.task_file.write_text("a changed task")
        with self.assertRaises(worker.Refused) as result:
            self.run_task(task)
        self.assertEqual(result.exception.code, "task_changed")

    def test_paused_and_expired_runs_never_start(self):
        task = self.prepare()
        self.update_control(lambda state: state.update(status="paused"))
        with self.assertRaises(worker.Refused) as result:
            self.run_task(task)
        self.assertEqual(result.exception.code, "stopped")
        def expire(state):
            state["status"] = "active"
            state["started_at_utc"] = (datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()
            state["close_at_utc"] = (datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
            state["deadline_utc"] = (datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
        self.update_control(expire)
        with self.assertRaises(worker.Refused):
            self.run_task(task)
        self.assertFalse((self.root / "started").exists())

    def test_duplicate_workspace_dispatch_is_refused(self):
        with worker.workspace_lock(self.repo):
            with self.assertRaises(worker.Refused) as result:
                with worker.workspace_lock(self.repo):
                    self.fail("duplicate lock accepted")
        self.assertEqual(result.exception.code, "workspace_busy")

    def test_traversal_scope_and_cross_project_contract_are_refused(self):
        with self.assertRaises(worker.Refused):
            worker.allowed_paths(["../Secrets.xcconfig"])
        task = self.prepare()
        task["scope_revision"] += 1
        with self.assertRaises(worker.Refused) as result:
            self.run_task(task)
        self.assertEqual(result.exception.code, "stale")
        task["scope_revision"] -= 1
        other = self.root / "another-project"
        other.mkdir()
        subprocess.run(["git", "-C", str(other), "init", "-q"], check=True)
        task["workspace"] = str(other)
        with self.assertRaises(worker.Refused) as result:
            self.run_task(task)
        self.assertEqual(result.exception.code, "wrong_project")

    def test_timeout_ends_grandchild_and_requests_takeover(self):
        os.environ["DEEPSEEK_TEST_MODE"] = "wait"
        receipt = self.run_task(self.prepare(timeout=0.6))
        self.assertEqual(receipt["reason"], "task_timeout")
        self.assertEqual(receipt["status"], "needs_codex_takeover")
        self.assertTrue(receipt["process_group_stopped"])
        self.assert_child_stopped()

    def mutate_when_started(self, mutate):
        def change():
            until = time.monotonic() + 5
            while not (self.root / "child.pid").exists() and time.monotonic() < until:
                time.sleep(0.02)
            self.update_control(mutate)
        thread = threading.Thread(target=change)
        thread.start()
        self.addCleanup(thread.join, 6)

    def test_stop_during_execution_ends_processes_without_takeover(self):
        os.environ["DEEPSEEK_TEST_MODE"] = "wait"
        self.mutate_when_started(lambda state: state.update(status="stopped"))
        receipt = self.run_task(self.prepare())
        self.assertEqual(receipt["status"], "stopped")
        self.assertTrue(receipt["process_group_stopped"])
        self.assert_child_stopped()

    def test_scope_change_during_execution_is_stale_not_takeover(self):
        os.environ["DEEPSEEK_TEST_MODE"] = "wait"
        self.mutate_when_started(lambda state: state["current"].update(scope_revision=1))
        receipt = self.run_task(self.prepare())
        self.assertEqual(receipt["status"], "stale")
        self.assert_child_stopped()

    def test_completed_parent_cleans_up_leftover_child(self):
        os.environ["DEEPSEEK_TEST_MODE"] = "orphan"
        receipt = self.run_task(self.prepare())
        self.assertEqual(receipt["status"], "completed_unreviewed")
        self.assert_child_stopped()

    def test_hard_run_deadline_stops_worker_without_takeover(self):
        def shorten(state):
            now = datetime.now(timezone.utc)
            state["close_at_utc"] = (now + timedelta(seconds=0.15)).isoformat()
            state["deadline_utc"] = (now + timedelta(seconds=0.5)).isoformat()
        os.environ["DEEPSEEK_TEST_MODE"] = "wait"
        self.mutate_when_started(shorten)
        receipt = self.run_task(self.prepare())
        self.assertEqual(receipt["status"], "stopped")
        self.assertTrue(receipt["process_group_stopped"])
        self.assert_child_stopped()

    def test_cancelling_supervisor_stops_worker_and_grandchild(self):
        task = self.prepare()
        launcher = self.root / "supervisor.py"
        scripts = str(Path(__file__).resolve().parent)
        launcher.write_text(
            "import pathlib,sys\nsys.path.insert(0," + repr(scripts) + ")\n"
            "import worker\nworker.configuration.codex_home=lambda:pathlib.Path(" + repr(str(self.home)) + ")\n"
            "sys.exit(worker.main(sys.argv[1:]))\n"
        )
        environment = dict(os.environ)
        environment["DEEPSEEK_TEST_MODE"] = "wait"
        proc = subprocess.Popen([sys.executable, str(launcher), "run", "--manifest", str(self.manifest),
                                 "--settings", str(self.settings), "--codex-bin", str(self.fake)],
                                env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            until = time.monotonic() + 5
            while not (self.root / "child.pid").exists() and time.monotonic() < until:
                time.sleep(0.02)
            self.assertTrue((self.root / "child.pid").exists())
            proc.send_signal(signal.SIGTERM)
            stdout, stderr = proc.communicate(timeout=8)
            self.assertEqual(proc.returncode, 11, stderr.decode())
            receipt = json.loads(stdout)
            self.assertEqual(receipt["status"], "stopped")
            self.assertEqual(receipt["reason"], "supervisor_cancelled")
            self.assertTrue(receipt["process_group_stopped"])
            self.assert_child_stopped()
        finally:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=8)

    def test_dry_run_starts_no_worker_or_output_directory(self):
        self.prepare()
        with redirect_stdout(io.StringIO()) as output:
            code = worker.main(["run", "--manifest", str(self.manifest), "--settings", str(self.settings),
                                "--codex-bin", str(self.fake), "--dry-run"])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(output.getvalue())["dry_run"])
        self.assertFalse((self.root / "started").exists())
        self.assertFalse(self.out.exists())

    def test_generated_config_drops_remote_instructions_and_preserves_existing_files(self):
        catalog = json.loads((self.home / "model-catalogs/deepseek-worker.json").read_text())
        self.assertNotIn("REMOTE PROMPT", json.dumps(catalog))
        primary = self.home / "config.toml"
        primary.write_text('model = "unchanged"\n')
        with self.assertRaises(ValueError):
            configuration.install(self.home, "deepseek-flash", "high", "deepseek-worker", "env", catalog)
        self.assertEqual(primary.read_text(), 'model = "unchanged"\n')
        for path in self.home.rglob("*"):
            if path.is_file():
                self.assertNotIn("offline-synthetic-credential", path.read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Offline behavior tests: no real keys, hosting writes, or paid API calls."""
import argparse
import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

import nxtpath_video as video
import r2_references as r2


class VideoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.job = self.root / "attempt-01"
        self.prompt = self.root / "prompt.txt"
        self.prompt.write_text("The character slowly waves, fixed camera.")
        self.config = {"NXTPATH_API_KEY": "fake-test-credential", "NXTPATH_SEEDANCE_MODEL": "seedance-2.5"}
        video.SECRETS.clear()
        video.SECRETS.add(self.config["NXTPATH_API_KEY"])
        self.args = argparse.Namespace(job=str(self.job), prompt_file=self.prompt, model=None, reference=[], duration=4, resolution="480p", ratio="1:1")

    def prepared(self, local=False):
        if local:
            image = self.root / "source.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            self.args.reference = [str(image)]
        video.prepare(self.args, self.config)

    def accepted(self):
        self.prepared()
        with patch.object(video, "api", return_value={"output": {"task_id": "opaque-private-task"}}):
            video.submit(self.args, self.config)

    def test_prepare_is_offline_and_exclusive(self):
        with patch.object(video, "api") as api:
            self.prepared(local=True)
            self.assertEqual(video.load_manifest(self.job)["references"][0]["sha256"], video.digest(self.root / "source.png"))
            with self.assertRaises(FileExistsError):
                video.prepare(self.args, self.config)
            api.assert_not_called()
        self.assertEqual((self.job / "manifest.json").stat().st_mode & 0o777, 0o600)

    def test_invalid_duration_does_not_create_job(self):
        self.args.duration = 3
        with self.assertRaises(video.VideoError):
            video.prepare(self.args, self.config)
        self.assertFalse(self.job.exists())

    def test_changed_snapshot_blocks_submission(self):
        self.prepared(local=True)
        (self.job / "inputs/reference-1.png").write_bytes(b"changed")
        with patch.object(video, "api") as api, self.assertRaises(video.VideoError):
            video.submit(self.args, self.config)
        api.assert_not_called()

    def test_changed_manifest_blocks_submission(self):
        self.prepared()
        manifest = video.read_json(self.job / "manifest.json")
        manifest["parameters"]["duration"] = 8
        video.write_json(self.job / "manifest.json", manifest)
        with patch.object(video, "api") as api, self.assertRaises(video.VideoError):
            video.submit(self.args, self.config)
        api.assert_not_called()

    def test_expired_reference_blocks_paid_post(self):
        self.prepared(local=True)
        ref = video.load_manifest(self.job)["references"][0]
        video.write_json(self.job / "hosting.json", {"references": {"0": {"sha256": ref["sha256"], "verified_anonymous_get": True,
                         "url": "https://example.invalid/image.png", "expires_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()}}})
        with patch.object(video, "api") as api, self.assertRaises(video.VideoError):
            video.submit(self.args, self.config)
        api.assert_not_called()
        self.assertFalse((self.job / "submission.json").exists())

    def test_submission_is_reserved_before_post_and_not_replayed(self):
        self.prepared()
        def accepted(*args):
            self.assertEqual(video.read_json(self.job / "submission.json")["outcome"], "unknown")
            return {"output": {"task_id": "opaque-private-task"}}
        with patch.object(video, "api", side_effect=accepted) as api:
            summary = video.submit(self.args, self.config)
            with self.assertRaises(video.VideoError):
                video.submit(self.args, self.config)
            self.assertEqual(api.call_count, 1)
            self.assertNotIn("opaque-private-task", json.dumps(summary))

    def test_unknown_network_result_is_not_replayed(self):
        self.prepared()
        with patch.object(video, "api", side_effect=video.VideoError("timeout")) as api:
            with self.assertRaises(video.VideoError):
                video.submit(self.args, self.config)
            with self.assertRaises(video.VideoError):
                video.submit(self.args, self.config)
            self.assertEqual(api.call_count, 1)
        self.assertEqual(video.read_json(self.job / "submission.json")["outcome"], "unknown")

    def test_quota_rejection_is_recorded_without_fallback(self):
        self.prepared()
        with patch.object(video, "api", side_effect=video.APIError(429, "quota reached")) as api:
            with self.assertRaises(video.APIError):
                video.submit(self.args, self.config)
        self.assertEqual(api.call_count, 1)
        self.assertEqual(video.read_json(self.job / "submission.json")["outcome"], "rejected")

    def test_success_without_task_id_remains_unknown(self):
        self.prepared()
        with patch.object(video, "api", return_value={"output": {}}), self.assertRaises(video.VideoError):
            video.submit(self.args, self.config)
        self.assertEqual(video.read_json(self.job / "submission.json")["outcome"], "unknown")

    def test_recover_task_after_interrupted_record_update(self):
        self.accepted()
        record = video.read_json(self.job / "submission.json")
        record.update(task_id=None, outcome="unknown")
        video.write_json(self.job / "submission.json", record)
        with patch.object(video, "api", return_value={"output": {"task_status": "Running"}}) as api:
            summary = video.status(self.args, self.config)
        self.assertEqual(summary["status"], "Running")
        self.assertIsNone(api.call_args.kwargs.get("payload"))
        self.assertEqual(video.read_json(self.job / "submission.json")["outcome"], "accepted")

    def test_unexpected_artifact_origin_is_rejected(self):
        with self.assertRaises(video.VideoError):
            video.artifact_url("task", {"output": {"task_status": "Success", "urls": ["https://evil.invalid/video.mp4"]}})

    def test_media_redirect_never_receives_api_key(self):
        self.job.mkdir()
        url = "https://api.nxtpath.ai/v1/tasks/artifacts/task/0"
        location = "https://ark-acg-cn-beijing.tos-cn-beijing.volces.com/output.mp4?signature=private"
        opener = Mock()
        opener.open.side_effect = [HTTPError(url, 302, "Found", {"Location": location}, io.BytesIO()), io.BytesIO(b"video")]
        with patch.object(video.request, "build_opener", return_value=opener):
            video.open_artifact(self.config["NXTPATH_API_KEY"], url, self.job)
        first, second = [call.args[0] for call in opener.open.call_args_list]
        self.assertTrue(first.get_header("Authorization"))
        self.assertIsNone(second.get_header("Authorization"))

    def test_unverified_redirect_is_not_followed(self):
        self.job.mkdir()
        opener = Mock()
        opener.open.side_effect = HTTPError("https://api.nxtpath.ai", 302, "Found", {"Location": "https://evil.invalid/video.mp4"}, io.BytesIO())
        with patch.object(video.request, "build_opener", return_value=opener), self.assertRaises(video.VideoError):
            video.open_artifact(self.config["NXTPATH_API_KEY"], "https://api.nxtpath.ai/v1/tasks/artifacts/task/0", self.job)
        self.assertEqual(opener.open.call_count, 1)

    def test_cached_download_is_verified_without_network(self):
        self.job.mkdir()
        (self.job / "video.mp4").write_bytes(b"\x00\x00\x00\x18ftypisom")
        video.write_json(self.job / "download.json", {"sha256": video.digest(self.job / "video.mp4")})
        with patch.object(video, "api") as api:
            self.assertTrue(video.download(self.args, self.config)["already_downloaded"])
        api.assert_not_called()

    def test_env_file_is_parsed_without_executing_shell_and_env_wins(self):
        env_file = self.root / "env"
        touched = self.root / "should-not-exist"
        env_file.write_text("export NXTPATH_API_KEY='$(touch " + str(touched) + ")'\n")
        env_file.chmod(0o600)
        with patch.dict(os.environ, {}, clear=True):
            config, _ = video.load_config(env_file)
            self.assertIn("$(touch", config["NXTPATH_API_KEY"])
            self.assertFalse(touched.exists())
        with patch.dict(os.environ, {"NXTPATH_API_KEY": "override-test-key"}, clear=True):
            config, _ = video.load_config(env_file)
            self.assertEqual(config["NXTPATH_API_KEY"], "override-test-key")

    def test_env_file_permission_violation_is_rejected(self):
        env_file = self.root / "env"
        env_file.write_text("export NXTPATH_API_KEY=private\n")
        env_file.chmod(0o644)
        with self.assertRaises(video.VideoError):
            video.load_config(env_file)

    def test_secret_and_signed_url_do_not_reach_console(self):
        message = video.safe_error("oops " + self.config["NXTPATH_API_KEY"] + " https://example.invalid/?signature=sensitive")
        self.assertNotIn(self.config["NXTPATH_API_KEY"], message)
        self.assertNotIn("signature", message)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            video.emit({"error": self.config["NXTPATH_API_KEY"]})
        self.assertNotIn(self.config["NXTPATH_API_KEY"], output.getvalue())

    def test_r2_403_does_not_trigger_upload(self):
        image = self.root / "image.png"
        image.write_bytes(b"image")
        client = Mock()
        denied = Exception()
        denied.response = {"ResponseMetadata": {"HTTPStatusCode": 403}}
        client.head_object.side_effect = denied
        with patch.object(r2, "connection", return_value=(client, "bucket", "https://account.r2.cloudflarestorage.com")), self.assertRaises(video.VideoError):
            r2.publish(self.config, image)
        client.put_object.assert_not_called()


if __name__ == "__main__":
    unittest.main()

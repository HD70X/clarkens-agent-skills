"""Offline behavior tests: no real keys, hosting writes, or paid API calls."""
import argparse
from concurrent.futures import ThreadPoolExecutor
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

import nxtpath_minimax_video as video
import r2_references as r2


class VideoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.job = self.root / "attempt-01"
        self.prompt = self.root / "prompt.txt"
        self.prompt.write_text("The character slowly waves, fixed camera.")
        self.config = {"NXTPATH_API_KEY": "fake-test-credential", "NXTPATH_MINIMAX_MODEL": "minimax/minimax-h3"}
        video.SECRETS.clear()
        video.SECRETS.add(self.config["NXTPATH_API_KEY"])
        self.args = argparse.Namespace(job=str(self.job), prompt_file=self.prompt, model=None, reference=[], first_frame=[], last_frame=[], duration=4, resolution="720p", ratio="16:9")

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

    def test_insecure_redirect_is_not_followed(self):
        self.job.mkdir()
        opener = Mock()
        opener.open.side_effect = HTTPError("https://api.nxtpath.ai", 302, "Found", {"Location": "http://media.invalid/video.mp4"}, io.BytesIO())
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

    def test_keyframe_request_matches_provider_contract(self):
        self.args.first_frame = ["https://example.invalid/first.png"]
        self.args.last_frame = ["https://example.invalid/last.png"]
        video.prepare(self.args, self.config)
        self.assertEqual(video.build_payload(self.job), {
            "model": "minimax/minimax-h3",
            "input": {"content": [
                {"type": "text", "text": self.prompt.read_text()},
                {"type": "image_url", "image_url": {"url": self.args.first_frame[0]}, "role": "first_frame"},
                {"type": "image_url", "image_url": {"url": self.args.last_frame[0]}, "role": "last_frame"},
            ]},
            "parameters": {"resolution": "720p", "duration": 4, "ratio": "16:9"},
        })

    def test_reference_images_have_no_keyframe_roles(self):
        self.args.reference = ["https://example.invalid/a.png", "https://example.invalid/b.jpg"]
        video.prepare(self.args, self.config)
        images = video.build_payload(self.job)["input"]["content"][1:]
        self.assertEqual(len(images), 2)
        self.assertTrue(all("role" not in part for part in images))

    def test_keyframes_cannot_mix_with_references(self):
        self.args.reference = ["https://example.invalid/a.png"]
        self.args.first_frame = ["https://example.invalid/b.png"]
        with self.assertRaises(video.VideoError):
            video.prepare(self.args, self.config)
        self.assertFalse(self.job.exists())

    def test_duplicate_keyframe_is_rejected(self):
        for flag in ("first_frame", "last_frame"):
            with self.subTest(flag=flag):
                setattr(self.args, flag, ["https://example.invalid/a.png"] * 2)
                with self.assertRaises(video.VideoError):
                    video.prepare(self.args, self.config)
                setattr(self.args, flag, [])
        self.assertFalse(self.job.exists())

    def test_seedance_parameters_and_unknown_model_are_rejected_before_spend(self):
        for field, value in (("duration", 13), ("duration", 4.5), ("resolution", "480p"), ("resolution", "1080p"), ("ratio", "2:1"), ("model", "seedance-2.5")):
            original = getattr(self.args, field)
            with self.subTest(field=field, value=value), patch.object(video, "api") as api:
                setattr(self.args, field, value)
                with self.assertRaises(video.VideoError):
                    video.prepare(self.args, self.config)
                self.assertFalse(self.job.exists())
                api.assert_not_called()
            setattr(self.args, field, original)

    def test_inline_and_insecure_urls_are_rejected(self):
        for url in ("data:image/png;base64,AAAA", "http://example.invalid/a.png"):
            with self.subTest(url=url):
                self.args.first_frame = [url]
                with self.assertRaises(video.VideoError):
                    video.prepare(self.args, self.config)
        self.assertFalse(self.job.exists())

    def test_upper_parameter_boundary_and_resolution_case(self):
        self.args.duration = 12
        self.args.resolution = "2K"
        self.args.ratio = "9:16"
        video.prepare(self.args, self.config)
        self.assertEqual(video.build_payload(self.job)["parameters"], {"duration": 12, "resolution": "2k", "ratio": "9:16"})

    def test_concurrent_submit_sends_only_one_post(self):
        self.prepared()
        def submit_once(_):
            try:
                return video.submit(self.args, self.config)["status"]
            except video.VideoError:
                return "blocked"
        with patch.object(video, "api", return_value={"output": {"task_id": "private-task"}}) as api:
            with ThreadPoolExecutor(max_workers=8) as pool:
                outcomes = list(pool.map(submit_once, range(8)))
        self.assertEqual(outcomes.count("submitted"), 1)
        self.assertEqual(api.call_count, 1)
        self.assertEqual(video.read_json(self.job / "submission.json")["request_sha256"], video.digest(self.job / "request.json"))

    def test_ambiguous_http_failures_are_not_replayed(self):
        for code in (408, 409, 500):
            with self.subTest(code=code):
                self.args.job = str(self.root / ("attempt-" + str(code)))
                self.job = Path(self.args.job)
                self.prepared()
                with patch.object(video, "api", side_effect=video.APIError(code, "ambiguous")) as api:
                    with self.assertRaises(video.APIError):
                        video.submit(self.args, self.config)
                    with self.assertRaises(video.VideoError):
                        video.submit(self.args, self.config)
                    self.assertEqual(api.call_count, 1)
                self.assertEqual(video.read_json(self.job / "submission.json")["outcome"], "unknown")

    def test_unknown_status_is_retained_and_rejected(self):
        self.accepted()
        with patch.object(video, "api", return_value={"output": {"task_status": "completed"}}), self.assertRaises(video.VideoError):
            video.status(self.args, self.config)
        self.assertEqual(video.read_json(self.job / "result.json")["output"]["task_status"], "completed")

    def test_relative_artifact_handle_is_resolved(self):
        path = "/v1/tasks/artifacts/private-task/0"
        self.assertEqual(video.artifact_url("private-task", {"output": {"task_status": "Success", "urls": [path]}}), "https://api.nxtpath.ai" + path)
        with self.assertRaises(video.VideoError):
            video.artifact_url("private-task", {"output": {"task_status": "Success", "urls": ["//external.invalid" + path]}})

    def test_all_redirect_hops_are_anonymous(self):
        self.job.mkdir()
        original = "https://api.nxtpath.ai/v1/tasks/artifacts/task/0"
        media = "https://media.example.invalid/output.mp4?signature=private"
        location = "https://cdn.example.invalid/output.mp4?signature=private"
        opener = Mock()
        opener.open.side_effect = [
            HTTPError(original, 302, "Found", {"Location": media}, io.BytesIO()),
            HTTPError(media, 307, "Redirect", {"Location": location}, io.BytesIO()),
            io.BytesIO(b"video"),
        ]
        with patch.object(video.request, "build_opener", return_value=opener):
            video.open_artifact(self.config["NXTPATH_API_KEY"], original, self.job)
        requests = [call.args[0] for call in opener.open.call_args_list]
        self.assertEqual(requests[0].get_header("Authorization"), "Bearer " + self.config["NXTPATH_API_KEY"])
        self.assertTrue(all(item.get_header("Authorization") is None for item in requests[1:]))

    def test_local_keyframe_full_job_can_resume_and_download_without_resubmitting(self):
        image = self.root / "first.png"
        image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
        self.args.first_frame = [str(image)]
        video.prepare(self.args, self.config)
        hosted = {"sha256": video.digest(image), "url": "https://example.invalid/signed.png?signature=private",
                  "verified_anonymous_get": True, "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}
        with patch.object(r2, "publish", return_value=hosted) as publish:
            video.host(self.args, self.config)
            video.host(self.args, self.config)
        self.assertEqual(publish.call_count, 1)
        success = {"output": {"task_status": "Success", "urls": ["/v1/tasks/artifacts/private-task/0"]}}
        responses = [{"output": {"task_id": "private-task"}}, {"output": {"task_status": "Running"}}, success]
        mp4 = b"\x00\x00\x00\x18ftypisom" + b"fixture payload"
        with patch.object(video, "api", side_effect=responses) as api, patch.object(video, "open_artifact", return_value=io.BytesIO(mp4)):
            video.submit(self.args, self.config)
            self.assertEqual(video.status(self.args, self.config)["status"], "Running")
            result = video.download(self.args, self.config)
            self.assertTrue(video.download(self.args, self.config)["already_downloaded"])
            self.assertEqual(api.call_count, 3)
            self.assertEqual(sum(call.args[1] == "/tasks/submit" for call in api.call_args_list), 1)
        self.assertEqual(Path(result["video"]).read_bytes(), mp4)
        self.assertEqual(video.inspect_job(self.args, self.config)["status"], "downloaded")

    def test_doctor_checks_only_catalog_and_seedance_override_is_ignored(self):
        args = argparse.Namespace(check_api=True, check_hosting=False)
        config = {"NXTPATH_API_KEY": "test-key", "NXTPATH_SEEDANCE_MODEL": "seedance-2.5"}
        with patch.object(video, "api", return_value={"data": [{"id": "minimax/minimax-h3"}]}) as api:
            result = video.doctor(args, config, self.root / "env")
        self.assertTrue(result["model_available"])
        self.assertEqual(result["default_model"], "minimax/minimax-h3")
        self.assertEqual(api.call_args.args, ("test-key", "/models"))


if __name__ == "__main__":
    unittest.main()

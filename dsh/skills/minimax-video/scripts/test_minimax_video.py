"""Offline regression tests. No real credentials, API calls, or uploads."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from urllib import error
import wave

import configure
import minimax_config as cfg
import minimax_video as video
import r2_references


class Response(io.BytesIO):
    def __init__(self, data, length=None):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data) if length is None else length)}


class VideoTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="minimax-offline-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.prompt = self.root / "prompt.txt"
        self.prompt.write_text("镜头固定，角色缓慢转头。", encoding="utf-8")
        self.config = {"MINIMAX_API_KEY": "unit-test-key", "MINIMAX_API_HOST": cfg.DEFAULT_HOST}
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        cfg.SECRETS.clear()
        self.addCleanup(cfg.SECRETS.clear)
        # A missed mock must fail before reaching a network.
        self.network_guard = patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("Network forbidden"))
        self.network_guard.start()
        self.addCleanup(self.network_guard.stop)

    def args(self, *extra, name="job"):
        return video.parser().parse_args(["prepare", "--job", str(self.root / name),
                                          "--prompt-file", str(self.prompt), *extra])

    def prepare(self, *extra, name="job"):
        args = self.args(*extra, name=name)
        video.prepare(args, self.config)
        return Path(args.job)

    def image(self, name="first.png", size=(512, 512)):
        from PIL import Image
        path = self.root / name
        Image.new("RGB", size, "navy").save(path)
        return path

    def audio(self, seconds=3):
        path = self.root / f"audio-{seconds}.wav"
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b"\0\0" * (seconds * 16000))
        return path

    def accept(self, job):
        with patch.object(video, "api", return_value={"task_id": "unit-task"}) as api:
            video.submit(video.argparse.Namespace(job=str(job)), self.config)
        return api

    def task_response(self, **changes):
        task = {"id": "unit-task", "model": "MiniMax-H3", "status": "succeeded",
                "content": {"url": "https://cdn.example.test/video.mp4"}}
        task.update(changes)
        return {"task": task}

    def test_text_request_is_official_v2(self):
        job = self.prepare("--duration", "15", "--resolution", "2k", "--ratio", "9:16")
        payload = video.build_payload(job)
        self.assertEqual(payload["duration"], 15)
        self.assertEqual(payload["resolution"], "2K")
        self.assertEqual(payload["ratio"], "9:16")
        self.assertEqual(payload["model"], "MiniMax-H3")
        self.assertNotIn("input", payload)
        self.assertNotIn("parameters", payload)
        self.assertEqual(payload["content"][0]["type"], "text")

    def test_keyframe_snapshot_and_inline_survive_original_edit(self):
        original = self.image()
        before = original.read_bytes()
        job = self.prepare("--first-frame", str(original))
        original.write_bytes(b"original was edited")
        payload = video.build_payload(job)
        self.assertEqual(payload["ratio"], "adaptive")
        part = payload["content"][1]
        self.assertEqual(part["role"], "first_frame")
        self.assertEqual(video.base64.b64decode(part["image_url"]["url"].split(",", 1)[1]), before)
        snapshot = job / video.load_manifest(job)["references"][0]["snapshot"]
        snapshot.write_bytes(b"tampered")
        with self.assertRaises(cfg.VideoError):
            video.build_payload(job)

    def test_roles_counts_and_model_specific_parameters(self):
        cases = [
            ("--first-frame", "https://example.test/a.png", "--ref-audio", "https://example.test/b.wav"),
            ("--model", "MiniMax-H3-Max", "--duration", "4"),
            ("--model", "MiniMax-H3-Lite", "--ref-image", "mm_file://123", "--ratio", "adaptive"),
            ("--model", "MiniMax-H3-Highspeed", "--resolution", "2K"),
            ("--ratio", "adaptive"),
            ("--first-frame", "https://example.test/a.png", "--ratio", "16:9"),
            ("--prompt-expansion-mode", "disabled"),
        ]
        for index, flags in enumerate(cases):
            with self.subTest(flags=flags), self.assertRaises(cfg.VideoError):
                video.prepare(self.args(*flags, name=f"invalid-{index}"), self.config)
        flags = sum((["--ref-image", f"mm_file://{i}"] for i in range(10)), [])
        with self.assertRaises(cfg.VideoError):
            video.prepare(self.args(*flags), self.config)
        job = self.prepare("--model", "MiniMax-H3-Max", "--duration", "5",
                           "--prompt-expansion-mode", "disabled", "--no-aigc-watermark")
        payload = video.build_payload(job)
        self.assertEqual(payload["extra"]["prompt_expansion_mode"], "disabled")
        self.assertIs(payload["aigc_watermark"], False)

    def test_local_audio_and_combined_duration(self):
        audio = self.audio(3)
        job = self.prepare("--ref-audio", str(audio))
        payload = video.build_payload(job)
        self.assertEqual(payload["content"][1]["role"], "reference_audio")
        self.assertTrue(payload["content"][1]["audio_url"]["url"].startswith("data:audio/wav;base64,"))
        audio8 = self.audio(8)
        with self.assertRaises(cfg.VideoError):
            video.prepare(self.args("--ref-audio", str(audio8), "--ref-audio", str(audio8), name="too-long"), self.config)

    def test_invalid_local_dimensions_and_request_budget(self):
        small = self.image("small.png", size=(100, 100))
        with self.assertRaises(cfg.VideoError):
            video.prepare(self.args("--first-frame", str(small)), self.config)
        image = self.image()
        with patch.object(video, "MAX_REQUEST_BYTES", 100), self.assertRaises(cfg.VideoError):
            video.prepare(self.args("--first-frame", str(image)), self.config)
        self.assertFalse((self.root / "job").exists())

    def test_misnamed_image_is_rejected_before_inline_or_hosting(self):
        image = self.image()
        misnamed = self.root / "misnamed.jpg"
        misnamed.write_bytes(image.read_bytes())
        with self.assertRaises(cfg.VideoError):
            video.prepare(self.args("--first-frame", str(misnamed)), self.config)
        self.assertFalse((self.root / "job").exists())

    def test_r2_is_explicit_and_uses_verified_immutable_input(self):
        original = self.image()
        job = self.prepare("--first-frame", str(original), "--delivery", "r2")
        with self.assertRaises(cfg.VideoError):
            video.build_payload(job)
        ref = video.load_manifest(job)["references"][0]
        record = {"sha256": ref["sha256"], "verified_anonymous_get": True,
                  "expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
                  "url": "https://private.example.test/input.png?signature=private"}
        with patch.object(r2_references, "publish", return_value=record) as publish:
            video.host(video.argparse.Namespace(job=str(job)), self.config)
        self.assertNotEqual(publish.call_args.args[1], original)
        self.assertEqual(video.build_payload(job)["content"][1]["image_url"]["url"], record["url"])

    def test_submit_reservation_blocks_repeated_or_uncertain_post(self):
        job = self.prepare()
        args = video.argparse.Namespace(job=str(job))
        with patch.object(video, "api", side_effect=cfg.VideoError("timeout")) as api:
            with self.assertRaises(cfg.VideoError):
                video.submit(args, self.config)
            with self.assertRaises(cfg.VideoError):
                video.submit(args, self.config)
        self.assertEqual(api.call_count, 1)
        self.assertEqual(video.read_json(job / "submission.json")["outcome"], "unknown")
        self.assertEqual(video.digest(job / "request.json"), video.read_json(job / "submission.json")["request_sha256"])
        self.assertNotIn("unit-test-key", (job / "request.json").read_text())

    def test_simultaneous_submit_makes_one_post(self):
        job = self.prepare()
        barrier = threading.Barrier(2)
        build = video.build_payload
        def synchronized(path):
            result = build(path)
            barrier.wait(timeout=10)
            return result
        def submit_one():
            try:
                return video.submit(video.argparse.Namespace(job=str(job)), self.config)
            except cfg.VideoError:
                return None
        with patch.object(video, "build_payload", side_effect=synchronized), patch.object(video, "api", return_value={"task_id": "unit-task"}) as api:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: submit_one(), range(2)))
        self.assertEqual(sum(r is not None for r in results), 1)
        self.assertEqual(api.call_count, 1)

    def test_recover_persisted_success_response_without_post(self):
        job = self.prepare()
        self.accept(job)
        record = video.read_json(job / "submission.json")
        record.update(task_id=None, outcome="unknown")
        video.write_json(job / "submission.json", record)
        with patch.object(video, "api", return_value=self.task_response(status="running")) as api:
            result = video.status(video.argparse.Namespace(job=str(job)), self.config)
        self.assertEqual(result["status"], "running")
        self.assertEqual(api.call_count, 1)
        self.assertIsNone(api.call_args.kwargs.get("payload"))
        self.assertIn("/v2/query/video_generation/", api.call_args.args[2])

    def test_frozen_job_rejects_region_request_or_response_mismatch(self):
        job = self.prepare()
        self.accept(job)
        with self.assertRaises(cfg.VideoError):
            video.existing(job, {**self.config, "MINIMAX_API_HOST": "https://api.minimax.io"})
        with patch.object(video, "api", return_value=self.task_response(id="another-task")), self.assertRaises(cfg.VideoError):
            video.fetch_status(job, self.config)
        (job / "request.json").write_text("{}")
        with self.assertRaises(cfg.VideoError):
            video.existing(job, self.config)

    def test_download_is_anonymous_through_redirects_and_reuses_final_file(self):
        job = self.prepare()
        self.accept(job)
        data = b"\0\0\0\x18ftypisom" + b"mock-media"
        redirect = error.HTTPError("https://cdn.example.test/video.mp4", 302, "Moved",
                                   {"Location": "https://media.example.test/final.mp4?signature=private"}, io.BytesIO())
        transport = Mock()
        transport.open.side_effect = [redirect, Response(data)]
        with patch.object(video, "api", return_value=self.task_response()), patch.object(video, "opener", return_value=transport):
            result = video.download(video.argparse.Namespace(job=str(job)), self.config)
        for call in transport.open.call_args_list:
            self.assertNotIn("Authorization", dict(call.args[0].header_items()))
        self.assertEqual(Path(result["video"]).read_bytes(), data)
        with patch.object(video, "api", side_effect=AssertionError("Should use local final file")):
            self.assertTrue(video.download(video.argparse.Namespace(job=str(job)), self.config)["already_downloaded"])
        self.assertEqual((job / "video.mp4").stat().st_mode & 0o777, 0o600)

    def test_incomplete_download_keeps_part_and_never_marks_success(self):
        job = self.prepare()
        self.accept(job)
        transport = Mock()
        transport.open.return_value = Response(b"\0\0\0\x18ftypisom", length=100)
        with patch.object(video, "api", return_value=self.task_response()), patch.object(video, "opener", return_value=transport):
            with self.assertRaises(cfg.VideoError):
                video.download(video.argparse.Namespace(job=str(job)), self.config)
        self.assertTrue((job / "video.mp4.part").exists())
        self.assertFalse((job / "video.mp4").exists())
        self.assertFalse((job / "download.json").exists())

    def test_simultaneous_download_cannot_rewrite_completed_video(self):
        job = self.prepare()
        self.accept(job)
        started, release = threading.Event(), threading.Event()
        data = b"\0\0\0\x18ftypisom" + b"mock-media"
        def blocked_media(*_):
            started.set()
            if not release.wait(timeout=10):
                raise AssertionError("Test download was not released")
            return Response(data)
        args = video.argparse.Namespace(job=str(job))
        with patch.object(video, "api", return_value=self.task_response()), patch.object(video, "open_media", side_effect=blocked_media):
            with ThreadPoolExecutor(max_workers=1) as pool:
                first = pool.submit(video.download, args, self.config)
                self.assertTrue(started.wait(timeout=10))
                try:
                    with self.assertRaises(cfg.VideoError):
                        video.download(args, self.config)
                finally:
                    release.set()
                first.result(timeout=10)
        self.assertEqual(video.digest(job / "video.mp4"), video.read_json(job / "download.json")["sha256"])
        with video.download_lock(job):
            pass

    def test_rejects_http_media_redirect(self):
        job = self.prepare()
        transport = Mock()
        transport.open.side_effect = error.HTTPError("https://cdn.example.test/video", 302, "Moved",
                                                    {"Location": "http://example.test/video"}, io.BytesIO())
        with patch.object(video, "opener", return_value=transport), self.assertRaises(cfg.VideoError):
            video.open_media("https://cdn.example.test/video", job)
        self.assertEqual(transport.open.call_count, 1)

    def test_doctor_only_reads_list_and_does_not_claim_generation(self):
        args = video.argparse.Namespace(check_api=True, check_hosting=False)
        with patch.object(video, "api", return_value={"items": [], "total": 0}) as api:
            result = video.doctor(args, self.config, self.root / "env")
        self.assertTrue(result["api_verified"])
        self.assertFalse(result["generation_verified"])
        self.assertFalse(result["paid_task_created"])
        self.assertIn("/v2/query/video_generation?", api.call_args.args[2])
        self.assertEqual(len(api.call_args.args), 3)

    def test_private_config_is_parsed_without_execution_and_environment_wins(self):
        marker = self.root / "should-not-exist"
        path = self.root / "config" / "env"
        cfg.save_config(path, {"MINIMAX_API_KEY": "test-file-key", "MINIMAX_VIDEO_MODEL": f"$(touch {marker})"})
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-environment-key"}):
            values, loaded = cfg.load_config(path)
        self.assertEqual(values["MINIMAX_API_KEY"], "test-environment-key")
        self.assertEqual(loaded, path)
        self.assertFalse(marker.exists())
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)

    def test_configure_hidden_key_does_not_return_secret(self):
        path = self.root / "config" / "env"
        args = video.argparse.Namespace(env_file=path, region="cn", from_env=False, replace_key=False,
                                        gui=True, reuse_nxtpath_r2=False)
        with patch.object(configure, "hidden_key", return_value="hidden-unit-key"):
            result = configure.configure(args)
        self.assertTrue(result["api_key_configured"])
        self.assertNotIn("hidden-unit-key", json.dumps(result))
        self.assertEqual(cfg.read_env(path)["MINIMAX_API_KEY"], "hidden-unit-key")

    def test_configure_without_region_preserves_existing_global_host(self):
        path = self.root / "config" / "env"
        cfg.save_config(path, {"MINIMAX_API_KEY": "saved-unit-key", "MINIMAX_API_HOST": "https://api.minimax.io"})
        args = video.argparse.Namespace(env_file=path, region=None, from_env=False, replace_key=False,
                                        gui=False, reuse_nxtpath_r2=False)
        result = configure.configure(args)
        self.assertEqual(result["api_host"], "https://api.minimax.io")

    def test_callback_url_is_private_in_console_summaries(self):
        args = self.args("--callback-url", "https://callback.example.test/?secret=private")
        result = video.prepare(args, self.config)
        self.assertNotIn("secret=private", json.dumps(result))
        result = video.inspect_job(video.argparse.Namespace(job=args.job), self.config)
        self.assertNotIn("secret=private", json.dumps(result))
        self.assertTrue(result["parameters"]["callback_url_configured"])

    def test_r2_403_does_not_upload(self):
        class Denied(Exception):
            response = {"ResponseMetadata": {"HTTPStatusCode": 403}}
        client = Mock()
        client.head_object.side_effect = Denied()
        image = self.image()
        with patch.object(r2_references, "connection", return_value=(client, "bucket", "https://r2.example.test")):
            with self.assertRaises(cfg.VideoError):
                r2_references.publish({}, image, "image")
        client.put_object.assert_not_called()

    def test_manifest_and_errors_redact_configured_secrets(self):
        cfg.api_key(self.config)
        self.assertNotIn("unit-test-key", cfg.safe_error("error unit-test-key https://example.test/?signature=hidden"))
        job = self.prepare()
        video.write_json(job / "error.json", {"error": "echoed unit-test-key"})
        self.assertNotIn("unit-test-key", (job / "error.json").read_text())

    def test_api_error_and_official_origin_boundary(self):
        transport = Mock()
        transport.open.side_effect = error.HTTPError(cfg.DEFAULT_HOST + "/v2/video_generation", 402, "No balance",
                                                    {}, io.BytesIO(b'{"error":{"type":"insufficient_balance_error"}}'))
        with patch.object(video, "opener", return_value=transport):
            with self.assertRaises(video.APIError) as error_context:
                video.api(cfg.DEFAULT_HOST, "unit-test-key", "/v2/video_generation", {"model": "MiniMax-H3"})
        self.assertEqual(error_context.exception.code, 402)
        self.assertEqual(transport.open.call_count, 1)
        with self.assertRaises(cfg.VideoError):
            video.api("https://unofficial.example.test", "unit-test-key", "/v2/video_generation", {})


if __name__ == "__main__":
    unittest.main()

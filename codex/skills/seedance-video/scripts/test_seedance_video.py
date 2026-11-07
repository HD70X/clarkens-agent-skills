"""Offline regression tests for the official Seedance request and task lifecycle."""
import base64
from concurrent.futures import ThreadPoolExecutor
from email.message import Message
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import tempfile
from threading import Event
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

import ark_request
import seedance_video as video


KEY = "test-ark-key"
TASK = "cgt-20261107113000-test"
MEDIA_URL = "https://media.example/temporary?signature=private"
REDIRECT_URL = "https://cdn.example/file"
MP4 = b"".join(struct.pack(">I4s", 12, name) + b"test" for name in (b"ftyp", b"moov", b"mdat"))
JPEG = b"\xff\xd8test\xff\xd9"


class Response(io.BytesIO):
    def __init__(self, data, length=None):
        super().__init__(data)
        self.status = 200
        self.headers = {"Content-Length": str(len(data) if length is None else length)}


def redirect(url, location):
    headers = Message()
    headers["Location"] = location
    return HTTPError(url, 302, "Found", headers, io.BytesIO(b""))


class SeedanceTests(unittest.TestCase):
    def setUp(self):
        temp = self.enter_context_or_cleanup(tempfile.TemporaryDirectory())
        self.root = Path(temp)
        self.job = self.root / "job"
        self.prompt = self.root / "prompt.txt"
        self.prompt.write_text("风吹过草地。", encoding="utf-8")
        self.enter_context_or_cleanup(patch.dict(os.environ, {"ARK_API_KEY": KEY, "SEEDANCE_REGION": "cn"}))
        self.enter_context_or_cleanup(patch.object(video, "key_path", side_effect=lambda region: self.root / region / "key"))
        self.transport = Mock()
        self.enter_context_or_cleanup(patch.object(video.request, "build_opener", return_value=self.transport))

    def enter_context_or_cleanup(self, manager):
        value = manager.__enter__()
        self.addCleanup(manager.__exit__, None, None, None)
        return value

    def call(self, *args):
        args = video.parser().parse_args([str(arg) for arg in args])
        return args.handler(args)

    def prepare(self, *args):
        return self.call("prepare", "--job", self.job, "--prompt-file", self.prompt, *args)

    def task(self, status, **fields):
        return Response(video.json_bytes({"id": TASK, "status": status, "model": "doubao-seedance-2-5-260628", **fields}))

    def test_freezes_keyframes_and_roles(self):
        frame = self.root / "frame.png"
        frame.write_bytes(b"local fixture")
        self.prepare("--first-frame", frame, "--last-frame", "asset://asset-approved", "--no-audio")
        frame.unlink()
        self.transport.open.return_value = Response(video.json_bytes({"id": TASK}))
        self.call("submit", "--job", self.job)
        call = self.transport.open.call_args.args[0]
        self.assertEqual(call.get_method(), "POST")
        self.assertEqual(call.data, (self.job / "request.json").read_bytes())
        body = json.loads(call.data)
        self.assertEqual(body["model"], "doubao-seedance-2-5-260628")
        self.assertEqual(body["ratio"], "adaptive")
        self.assertFalse(body["generate_audio"])
        self.assertEqual([part.get("role") for part in body["content"]], [None, "first_frame", "last_frame"])
        encoded = body["content"][1]["image_url"]["url"]
        self.assertEqual(encoded, "data:image/png;base64," + base64.b64encode(b"local fixture").decode("ascii"))

    def test_multimodal_edit_and_global_model(self):
        result = self.call("--region", "global", "prepare", "--job", self.job, "--omni-type", "edit",
                           "--ref-image", "asset://still", "--ref-video", "https://example.com/source.mp4",
                           "--ref-audio", "https://example.com/audio.wav", "--output-format", "mov")
        self.assertEqual(result["model"], "dreamina-seedance-2-5-260628")
        payload = video.read_record(self.job / "request.json")
        self.assertEqual((payload["duration"], payload["ratio"], payload["output_format"]), (-1, "adaptive", "mov"))
        self.assertEqual(payload["omni_reference_task_type"], "edit")
        self.assertEqual([part["type"] for part in payload["content"]], ["image_url", "video_url", "audio_url"])

    def test_rejects_unsupported_input_before_post(self):
        invalid = (
            ("--last-frame", "asset://last"),
            ("--first-frame", "asset://first", "--ref-image", "asset://reference"),
            ("--first-frame", "asset://first", "--ratio", "9:16"),
            ("--ref-video", "local.mp4"),
            ("--model", "2.0", "--ref-audio", "asset://audio"),
            ("--model", "2.0-fast", "--resolution", "1080p"),
            ("--omni-type", "edit", "--ref-video", "asset://video", "--duration", "8"),
        )
        for arguments in invalid:
            with self.subTest(arguments=arguments), self.assertRaises(video.VideoError):
                self.prepare(*arguments)
        frame = self.root / "frame.png"
        frame.write_bytes(b"x" * 1000)
        with patch.object(ark_request, "MAX_REQUEST_BYTES", 1500), self.assertRaisesRegex(video.VideoError, "exceed"):
            self.prepare("--first-frame", frame)
        self.assertFalse(self.job.exists())
        self.transport.open.assert_not_called()

    def test_request_modification_prevents_submission(self):
        self.prepare()
        (self.job / "request.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(video.VideoError, "changed"):
            self.call("submit", "--job", self.job)
        self.assertFalse((self.job / "submission.json").exists())
        self.transport.open.assert_not_called()

    def test_concurrent_and_uncertain_submission_is_sealed(self):
        self.prepare()
        reached_provider = Event()
        finish = Event()

        def timeout(*args, **kwargs):
            reached_provider.set()
            if not finish.wait(5):
                raise RuntimeError("Test did not release mock provider")
            raise TimeoutError()

        self.transport.open.side_effect = timeout
        with ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self.call, "submit", "--job", self.job)
            try:
                self.assertTrue(reached_provider.wait(5))
                with self.assertRaisesRegex(video.VideoError, "sealed"):
                    self.call("submit", "--job", self.job)
            finally:
                finish.set()
            with self.assertRaises(video.VideoError):
                first.result(timeout=5)
        self.assertEqual(self.call("inspect", "--job", self.job)["status"], "unknown")
        with self.assertRaisesRegex(video.VideoError, "sealed"):
            self.call("submit", "--job", self.job)
        self.transport.open.assert_called_once()

    def test_doctor_status_and_anonymous_download(self):
        self.prepare("--return-last-frame")
        self.transport.open.side_effect = [
            Response(b'{"items":[]}'),
            Response(video.json_bytes({"id": TASK})),
            self.task("queued"),
            self.task("succeeded", duration=4, content={"video_url": MEDIA_URL, "last_frame_url": "https://cdn.example/frame"}),
            redirect(MEDIA_URL, REDIRECT_URL),
            Response(MP4),
            Response(JPEG),
        ]
        self.assertTrue(self.call("doctor", "--check-api")["task_list_verified"])
        self.call("submit", "--job", self.job)
        self.assertEqual(self.call("status", "--job", self.job)["status"], "queued")
        result = self.call("download", "--job", self.job)
        self.assertEqual(result["artifacts"][0]["sha256"], hashlib.sha256(MP4).hexdigest())
        self.assertEqual((self.job / "video.mp4").read_bytes(), MP4)
        self.assertEqual((self.job / "last-frame.jpg").read_bytes(), JPEG)
        self.assertNotIn("signature", json.dumps(result))
        calls = [call.args[0] for call in self.transport.open.call_args_list]
        self.assertEqual([call.get_method() for call in calls[:4]], ["GET", "POST", "GET", "GET"])
        self.assertTrue(calls[0].full_url.endswith("/contents/generations/tasks?page_size=1"))
        self.assertTrue(calls[2].full_url.endswith("/contents/generations/tasks/" + TASK))
        self.assertTrue(all(call.get_header("Authorization") == "Bearer " + KEY for call in calls[:4]))
        self.assertTrue(all(call.get_header("Authorization") is None for call in calls[4:]))
        self.assertEqual(calls[5].full_url, REDIRECT_URL)
        self.transport.reset_mock()
        self.assertEqual(self.call("download", "--job", self.job), result)
        self.transport.open.assert_not_called()

    def test_download_retry_after_truncation(self):
        self.prepare()
        succeeded = {"content": {"video_url": MEDIA_URL}}
        self.transport.open.side_effect = [
            Response(video.json_bytes({"id": TASK})),
            self.task("succeeded", **succeeded), Response(MP4[:-1], length=len(MP4)),
            self.task("succeeded", **succeeded), Response(MP4),
        ]
        self.call("submit", "--job", self.job)
        with self.assertRaisesRegex(video.VideoError, "incomplete"):
            self.call("download", "--job", self.job)
        self.assertFalse((self.job / "video.mp4").exists())
        self.assertFalse(list(self.job.glob(".media-*")))
        self.assertEqual(self.call("download", "--job", self.job)["status"], "succeeded")

    def test_recover_uses_the_original_region_and_reports_failure(self):
        global_key = "test-byteplus-key"
        with patch.dict(os.environ, {"ARK_API_KEY": global_key, "SEEDANCE_REGION": "global"}):
            self.call("configure", "--from-env")
        failure = {"code": "InvalidParameter.Test", "message": f"detail {global_key}"}
        self.transport.open.side_effect = [self.task("running"), self.task("failed", error=failure)]
        self.call("--region", "global", "recover", "--job", self.job, "--task-id", TASK)
        with self.assertRaisesRegex(video.VideoError, "different official region"):
            self.call("--region", "cn", "status", "--job", self.job)
        result = self.call("status", "--job", self.job)
        self.assertEqual(result["error_code"], "InvalidParameter.Test")
        self.assertNotIn(global_key, (self.job / "result.json").read_text(encoding="utf-8"))
        with self.assertRaisesRegex(video.VideoError, "sealed"):
            self.call("submit", "--job", self.job)
        calls = [call.args[0] for call in self.transport.open.call_args_list]
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(call.full_url.startswith(video.API_ROOTS["global"]) for call in calls))
        self.assertTrue(all(call.get_header("Authorization") == "Bearer " + global_key for call in calls))

    def test_api_and_media_do_not_follow_unsafe_redirects(self):
        self.prepare()
        self.transport.open.side_effect = [redirect(video.API_ROOTS["cn"], REDIRECT_URL)]
        with self.assertRaisesRegex(video.ArkError, "HTTP 302"):
            self.call("submit", "--job", self.job)
        self.transport.open.assert_called_once()
        self.assertEqual(self.call("inspect", "--job", self.job)["status"], "unknown")
        self.transport.reset_mock()
        self.transport.open.side_effect = [redirect(MEDIA_URL, "http://cdn.example/file")]
        with self.assertRaisesRegex(video.VideoError, "HTTPS"):
            video.open_media(MEDIA_URL)
        self.transport.open.assert_called_once()


if __name__ == "__main__":
    unittest.main()

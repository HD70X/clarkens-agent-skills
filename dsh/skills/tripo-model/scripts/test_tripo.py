#!/usr/bin/env python3
"""Offline tests; fake fetch exercises the installed CLI without any API call."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

CLIENT = Path(__file__).with_name("tripo.py")
SPEC = importlib.util.spec_from_file_location("tripo_skill", CLIENT)
tripo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tripo)
CLI = Path(os.environ.get("TRIPO_TEST_CLI_ENTRY", str(Path.home() / ".local/share/tripo-skill/node_modules/tripo-cli/dist/cli.js")))
NODE = shutil.which("node")
KEY = "tsk_offline_fixture_not_a_real_credential"
TASK = "11111111-1111-4111-8111-111111111111"

FAKE_FETCH = r'''
import {appendFileSync, existsSync} from 'node:fs';
const taskId = '11111111-1111-4111-8111-111111111111';
const envelope = (data) => new Response(JSON.stringify({code:0,data}), {headers:{'content-type':'application/json'}});
globalThis.fetch = async (input, options={}) => {
  const url = new URL(typeof input === 'string' ? input : input.url);
  const method = options.method || 'GET';
  const artifact = url.hostname === 'fixture.invalid';
  const auth = new Headers(options.headers).get('authorization');
  const correct = artifact ? !auth : auth === 'Bearer ' + process.env.TRIPO_API_KEY;
  if (!artifact && url.origin !== 'https://openapi.tripo3d.com') throw new Error('Wrong region host');
  if (!correct) throw new Error('Wrong authorization');
  const event = {method,path:url.pathname,host:url.hostname,authorization_correct:correct};
  if (options.body && typeof options.body === 'string') event.payload=JSON.parse(options.body);
  appendFileSync(process.env.TRIPO_TEST_CALLS, JSON.stringify(event)+'\n');
  if (url.pathname === '/v3/account/balance') return envelope({balance:3000,frozen:0});
  if (url.pathname === '/v3/generation/text-to-model') {
    if (!existsSync(process.env.TRIPO_TEST_RECORD + '/invocation.json')) throw new Error('Missing pre-submit record');
    if (process.env.TRIPO_TEST_MODE === 'uncertain') throw new TypeError('simulated lost submit response');
    return envelope({task_id:taskId});
  }
  if (url.pathname === '/v3/tasks/' + taskId) return envelope({
    task_id:taskId,type:'text_to_model',status:'success',progress:100,credits_consumed:40,
    output:{model_url:'https://fixture.invalid/model.glb',rendered_image_url:'https://fixture.invalid/preview.png'}
  });
  if (artifact && url.pathname.endsWith('.glb')) {
    const json = Buffer.from(JSON.stringify({asset:{version:'2.0'},scene:0,scenes:[{}]}).padEnd(72,' '));
    const header=Buffer.alloc(20); header.write('glTF'); header.writeUInt32LE(2,4);
    header.writeUInt32LE(20+json.length,8); header.writeUInt32LE(json.length,12); header.write('JSON',16);
    return new Response(Buffer.concat([header,json]));
  }
  if (artifact && url.pathname.endsWith('.png')) return new Response(Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a4X8AAAAASUVORK5CYII=','base64'));
  throw new Error('Unexpected fetch route');
};
'''


class CredentialsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tripo-unit-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        tripo.SECRETS.clear()

    def credentials(self, text):
        path = self.root / "credentials.md"
        path.write_text(text, encoding="utf-8")
        path.chmod(0o600)
        return path

    def test_markdown_is_data_not_shell(self):
        path = self.credentials('\ufeff# Credentials\n```dotenv\nTRIPO_REGION=cn\nTRIPO_API_KEY="' + KEY + '"\n```\n$(touch should-not-exist)\n')
        self.assertEqual(tripo.read_credentials(path)["TRIPO_API_KEY"], KEY)
        self.assertNotIn(KEY, tripo.redact("Bearer " + KEY))
        self.assertFalse((self.root / "should-not-exist").exists())

    @unittest.skipIf(os.name == "nt", "POSIX permissions")
    def test_public_credentials_rejected(self):
        path = self.credentials("TRIPO_API_KEY=" + KEY)
        path.chmod(0o644)
        with self.assertRaises(tripo.TripoError):
            tripo.read_credentials(path)

    def test_duplicate_key_rejected(self):
        path = self.credentials("TRIPO_API_KEY=" + KEY + "\nTRIPO_API_KEY=other")
        with self.assertRaises(tripo.TripoError):
            tripo.read_credentials(path)

    def test_mismatched_region_stops_before_dispatch(self):
        path = self.credentials("TRIPO_REGION=cn\nTRIPO_API_KEY=" + KEY)
        args = argparse.Namespace(config=None, region="ov", credentials_file=str(path))
        with self.assertRaises(tripo.TripoError) as result:
            tripo.configuration(args, {})
        self.assertEqual(result.exception.exit_code, 3)

    def test_wrong_host_stops_before_dispatch(self):
        path = self.credentials("TRIPO_REGION=cn\nTRIPO_API_BASE_URL=https://wrong.invalid/v3\nTRIPO_API_KEY=" + KEY)
        args = argparse.Namespace(config=None, region="cn", credentials_file=str(path))
        with self.assertRaises(tripo.TripoError) as result:
            tripo.configuration(args, {})
        self.assertEqual(result.exception.exit_code, 3)


@unittest.skipUnless(NODE and CLI.is_file(), "Install tripo-cli 0.7.1 and Node 20+ for offline CLI integration tests")
class CLIIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tripo-integration-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.record = self.root / "operation"
        self.calls = self.root / "calls.jsonl"
        self.mock = self.root / "fake-fetch.mjs"
        self.mock.write_text(FAKE_FETCH, encoding="utf-8")
        self.credentials = self.root / "credentials.md"
        self.credentials.write_text("# Private\n```dotenv\nTRIPO_REGION=cn\nTRIPO_API_BASE_URL=https://openapi.tripo3d.com/v3\nTRIPO_API_KEY=" + KEY + "\n```\n", encoding="utf-8")
        self.credentials.chmod(0o600)
        self.config = self.root / "settings.json"
        self.config.write_text(json.dumps({"region":"cn", "credentials_file":str(self.credentials),
                                           "cli_entry":str(CLI), "node":NODE, "state_dir":str(self.root / "state")}), encoding="utf-8")
        self.env = {name:value for name,value in os.environ.items() if not name.startswith("TRIPO_") and name != "NODE_OPTIONS"}
        self.env.update({"NODE_OPTIONS":"--import " + self.mock.as_uri(), "TRIPO_TEST_CALLS":str(self.calls),
                         "TRIPO_TEST_RECORD":str(self.record), "NO_COLOR":"1"})

    def run_client(self, *arguments, record=False, extra_env=None):
        command = [sys.executable, str(CLIENT), "--config", str(self.config)]
        if record:
            command += ["--record-dir", str(self.record)]
        command += ["--"] + list(arguments)
        return subprocess.run(command, cwd=self.root, env={**self.env, **(extra_env or {})},
                              capture_output=True, text=True, timeout=45)

    def events(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def test_dry_run_plans_text_and_images_without_network(self):
        result = self.run_client("make", "a low-poly wooden chest", "--model", "tripo-p1", "--seed", "12345", "-p", "face_limit=3000", "--dry-run", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertTrue(plan["valid"])
        self.assertEqual(len(plan["steps"]), 1)
        self.assertEqual(plan["steps"][0]["payload"]["model"], "P1-20260311")
        for name in ("front.png", "back.png"):
            (self.root / name).write_bytes(b"fixture-image")
        result = self.run_client("make", str(self.root / "front.png"), str(self.root / "back.png"), "--dry-run", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["valid"])
        self.assertEqual(self.events(), [])

    def test_paid_operation_requires_record_before_any_network(self):
        result = self.run_client("--profile", "fixture", "make", "a chest", "--json")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.events(), [])

    def test_end_to_end_generation_download_and_resume(self):
        result = self.run_client("make", "a low-poly chest", "--model", "tripo-p1", "--seed", "12345", "--timeout", "15", "-o", str(self.root / "output"), "--json", record=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["credits_consumed"], 40)
        self.assertEqual(Path(data["model_file"]).read_bytes()[:4], b"glTF")
        self.assertTrue(Path(data["preview"]).is_file())
        record = json.loads((Path(data["output_dir"]) / "task.json").read_text())
        self.assertEqual(record["input"]["model_seed"], 12345)
        self.assertEqual(record["input"]["model"], "P1-20260311")
        posts = [e for e in self.events() if e["method"] == "POST"]
        self.assertEqual(len(posts), 1)
        for path in self.record.iterdir():
            self.assertNotIn(KEY, path.read_text())
            self.assertEqual(path.stat().st_mode & 0o077, 0)
        resumed = self.run_client("task", "watch", TASK, "--download", "-o", str(self.root / "resumed"), "--json")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        final = json.loads(resumed.stdout.splitlines()[-1])
        self.assertTrue(Path(final["model_file"]).exists())
        self.assertEqual(len([e for e in self.events() if e["method"] == "POST"]), 1)

    def test_uncertain_submit_never_retried_and_record_cannot_be_reused(self):
        args = ("make", "a chest", "--no-wait", "--json")
        result = self.run_client(*args, record=True, extra_env={"TRIPO_TEST_MODE":"uncertain"})
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual(len([e for e in self.events() if e["method"] == "POST"]), 1)
        completion = json.loads((self.record / "completion.json").read_text())
        self.assertEqual(completion["exit_code"], 7)
        result = self.run_client(*args, record=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(len([e for e in self.events() if e["method"] == "POST"]), 1)

    def test_child_output_and_saved_logs_redact_credentials(self):
        echo = self.root / "echo.mjs"
        echo.write_text("console.log(JSON.stringify({secret:process.env.TRIPO_API_KEY,region:process.env.TRIPO_REGION,base:process.env.TRIPO_API_BASE_URL})); console.error('Bearer '+process.env.TRIPO_API_KEY);", encoding="utf-8")
        result = self.run_client("balance", "--json", record=True, extra_env={"TRIPO_CLI_ENTRY":str(echo)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(KEY, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["base"], "https://openapi.tripo3d.com")
        for path in self.record.iterdir():
            self.assertNotIn(KEY, path.read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)

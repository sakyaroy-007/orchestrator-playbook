"""Public-wire fixtures: local sockets, temporary homes, no Hermes/model calls."""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import socketserver
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest

import test_playbook as fixtures

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "scripts/hermes-worker.py"
_spec = importlib.util.spec_from_file_location("tested_gateway", ROOT / "scripts/hermes_gateway.py")
transport = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(transport)


def frame(payload, opcode=1, final=True):
    if isinstance(payload, str):
        payload = payload.encode()
    count = len(payload)
    prefix = bytes(((128 if final else 0) | opcode, count if count < 126 else 126 if count < 65536 else 127))
    if count >= 126:
        prefix += struct.pack("!H" if count < 65536 else "!Q", count)
    return prefix + payload


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        line = self.rfile.readline().decode()
        if line != "GET /api/ws HTTP/1.1\r\n":
            return
        headers = {}
        while True:
            line = self.rfile.readline()
            if line == b"\r\n":
                break
            key, value = line.decode().split(":", 1)
            headers[key.lower()] = value.strip()
        self.server.fixture.headers.append(headers)
        accept = base64.b64encode(hashlib.sha1((headers["sec-websocket-key"] + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        self.wfile.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                          "Sec-WebSocket-Accept: %s\r\nSec-WebSocket-Protocol: hermes-gateway-v1\r\n\r\n" % accept).encode())
        if self.server.fixture.wire_frames:
            self.wfile.write(self.server.fixture.wire_frames)
            return
        while True:
            header = self.rfile.read(2)
            if not header:
                return
            first, second = header
            if not second & 128:
                self.server.fixture.errors.append("client frame was not masked")
                return
            count = second & 127
            if count in (126, 127):
                count = struct.unpack("!H" if count == 126 else "!Q", self.rfile.read(2 if count == 126 else 8))[0]
            mask = self.rfile.read(4)
            payload = bytes(value ^ mask[i % 4] for i, value in enumerate(self.rfile.read(count)))
            if first & 15 == 10:
                continue
            request = json.loads(payload)
            try:
                result = self.server.fixture.reply(request)
                if result is None:
                    return
                event = self.server.fixture.event
                if event and request["method"] == "prompt.receipt":
                    self.wfile.write(frame(json.dumps(event)))
                    self.server.fixture.event = None
                self.wfile.write(frame(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result})))
            except (BrokenPipeError, ConnectionResetError):
                return


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class GatewayFixture:
    def __init__(self, root, mode="complete"):
        self.root, self.mode = root, mode
        self.requests, self.headers, self.errors = [], [], []
        self.event = None
        self.cancelled = False
        self.lost = False
        self.wire_frames = b""
        self.server = Server(("127.0.0.1", 0), Handler)
        self.server.fixture = self
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.owner = {"profile_id": str(root / "profile"), "instance_id": "boot-1", "code_sha": "fixture-sha"}
        self.attach = {"endpoint": self.owner, "client_code_sha": "fixture-sha", "protocol": "hermes-gateway-v1",
                       "protocols": ["hermes-gateway-v1", "hermes-gateway-ticket.private-fixture-ticket"],
                       "url": "ws://127.0.0.1:%s/api/ws" % self.server.server_address[1]}
        self.binary = root / "fake-hermes"
        self.binary.write_text("#!" + sys.executable + " -I\nimport json,pathlib,sys\n"
                               "args=sys.argv[1:]\nassert args[-3:] == ['gateway','attach','--json'],args\n"
                               "assert '--start' not in args and '--recover' not in args\n"
                               "print(" + repr(json.dumps(self.attach)) + ")\n")
        self.binary.chmod(0o755)
        self.cwd = None
        self.creation = {}
        self.submission = None

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def receipt(self, terminal=False):
        result = {"admission_id": "admission-1", "ref": {"profile_id": self.owner["profile_id"], "session_id": "session-1"},
                  "sequence": 1, "status": "terminal" if terminal else "started", "outcome": None,
                  "authority_epoch": 7, "execution_generation": 1}
        if terminal:
            result.update(outcome="interrupted" if self.cancelled else "completed", result={"final_response": "fixture delivered"})
        return result

    def snapshot(self):
        result = {"session_id": "session-1", "stored_session_id": "session-1", "authority_epoch": 7,
                  "prompts": [], "pending": [], "info": {"desktop_protocol": "hermes-gateway-v1",
                  "profile_id": self.owner["profile_id"], "cwd": self.cwd,
                  "model": self.creation.get("model", "profile-model"),
                  "reasoning_effort": self.creation.get("reasoning", "medium"), "source": "tool"}}
        if self.submission:
            result["pending"] = [dict(self.receipt(), input_id=self.submission)]
        if self.mode == "wrong-cwd":
            result["info"]["cwd"] = "/another-project"
        if self.mode == "lost-unrecoverable":
            result["pending"] = []
        if self.mode == "queued-approval" and self.lost:
            result["prompts"] = [{"kind": "approval", "prompt_id": "resumed-approval", "execution_generation": 1,
                                  "choices": ["once", "deny"]}]
        return result

    def reply(self, request):
        self.requests.append(request)
        method, params = request["method"], request["params"]
        if method == "runtime.describe":
            return {"instance_id": "boot-1", "profile_id": self.owner["profile_id"], "authority_epoch": 7,
                    "capabilities": [] if self.mode == "no-capability" else ["durable-admission-v1", "event-replay-v1", "local-cli-create-v1"],
                    "session_create": {"sources": ["tool"], "parameters": ["source", "request_id", "cwd", "model", "reasoning"]}}
        if method == "session.create":
            self.cwd, self.creation = params["cwd"], params
            return self.snapshot()
        if method == "session.resume":
            return self.snapshot()
        if method == "prompt.submit":
            self.submission = params["submission_id"]
            if self.mode.startswith("lost") and not self.lost:
                self.lost = True
                return None
            if self.mode == "queued-approval":
                return dict(self.receipt(), status="queued", execution_generation=None)
            return self.receipt()
        if method == "prompt.receipt":
            if self.mode == "queued-approval" and not self.lost:
                self.lost = True
                return None
            if self.mode == "unknown":
                return dict(self.receipt(), status="unknown")
            complete = self.mode not in ("wait", "delegation-cancel") or self.cancelled
            return self.receipt(terminal=complete)
        if method == "prompt.cancel":
            self.cancelled = True
            return self.receipt()  # ACK deliberately remains started.
        if method == "process.stop":
            return {"killed": 0, "delegations": 1 if self.mode == "delegation-cancel" else 0}
        if method == "subagent.list":
            return {"subagents": [], "delegations": []}
        if method == "process.list":
            return {"processes": [{"session_id": "process-1", "status": "exited"}]}
        if method == "approval.respond":
            return {"status": "resolved", "prompt_id": params["prompt_id"]}
        raise AssertionError(method)


class HermesWorkerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="playbook-hermes-wire-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.cwd = self.root / "project"
        self.cwd.mkdir()
        self.gateway = GatewayFixture(self.root)
        self.addCleanup(self.gateway.close)
        self.path = self.root / "receipt.json"
        self.record = {"protocol": "hermes-gateway-v1", "attempt_id": "attempt-1", "state": "not_submitted",
                       "cwd": str(self.cwd), "timeout_seconds": 5,
                       "worker": {"client": "hermes", "model": {"mode": "inherit"}, "effort": {"mode": "inherit"},
                                  "hermes": {"approval": "inherit"}}}
        self.env = dict(os.environ, PLAYBOOK_ATTEMPT="attempt-1", PLAYBOOK_HERMES_RECEIPT=str(self.path))
        self.command = [sys.executable, "-I", str(BRIDGE), "--binary", str(self.gateway.binary), "--prompt", "fixture task"]

    def run_worker(self, expected=0):
        self.path.write_text(json.dumps(self.record))
        result = subprocess.run(self.command, env=self.env, capture_output=True, text=True, timeout=12)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertFalse(self.gateway.errors)
        return json.loads(self.path.read_text()), result

    def methods(self, name):
        return [request["params"] for request in self.gateway.requests if request["method"] == name]

    def test_completion_has_durable_identity_settings_result_and_no_ticket(self):
        self.record["worker"].update(profile="chosen-profile", model={"mode": "fixed", "value": "chosen-model"},
                                     effort={"mode": "fixed", "value": "high"})
        receipt, result = self.run_worker()
        self.assertEqual(receipt["state"], "terminal")
        self.assertEqual(receipt["admission_id"], "admission-1")
        self.assertEqual(receipt["observed"]["model"], "chosen-model")
        self.assertEqual(receipt["observed"]["reasoning_effort"], "high")
        self.assertIn("fixture delivered", result.stdout)
        self.assertFalse(receipt["entire_task_tree_proven"])
        self.assertNotIn("ticket", self.path.read_text() + result.stdout + result.stderr)
        self.assertNotIn("origin", self.gateway.headers[0])
        self.assertNotIn("unattended", self.methods("prompt.submit")[0])
        self.assertNotIn("finite", self.methods("prompt.submit")[0])

    def test_precheck_requires_cwd_and_branch_in_saved_result(self):
        self.command.append("--precheck")
        receipt, result = self.run_worker(expected=3)
        self.assertEqual(receipt["state"], "terminal")
        self.assertFalse(receipt["precheck_passed"])
        self.assertIn("precheck failed", result.stdout)

    def test_capability_or_cwd_mismatch_never_submits(self):
        for mode in ("no-capability", "wrong-cwd"):
            with self.subTest(mode=mode):
                self.gateway.mode = mode
                receipt, _ = self.run_worker(expected=2)
                self.assertEqual(receipt["state"], "not_submitted")
        self.assertFalse(self.methods("prompt.submit"))

    def test_lost_submit_ack_recovers_exact_identity_without_resubmission(self):
        self.gateway.mode = "lost-recoverable"
        receipt, _ = self.run_worker()
        self.assertTrue(receipt["reconnected"])
        self.assertEqual(len(self.methods("prompt.submit")), 1)
        self.assertEqual(len(self.methods("session.create")), 1)

    def test_reconnect_refreshes_queued_generation_before_answering_approval(self):
        self.gateway.mode = "queued-approval"
        self.record["worker"]["hermes"]["approval"] = "approve"
        receipt, _ = self.run_worker()
        self.assertTrue(receipt["reconnected"])
        self.assertEqual(self.methods("approval.respond"), [{"session_id": "session-1",
                         "execution_generation": 1, "prompt_id": "resumed-approval", "choice": "once"}])
        self.assertEqual(len(self.methods("prompt.submit")), 1)

    def test_unrecoverable_submit_and_unknown_outcome_never_replay(self):
        for mode in ("lost-unrecoverable", "unknown"):
            with self.subTest(mode=mode):
                self.gateway.mode, self.gateway.lost = mode, False
                before = len(self.methods("prompt.submit"))
                receipt, _ = self.run_worker(expected=75)
                self.assertEqual(receipt["state"], "unknown")
                self.assertEqual(len(self.methods("prompt.submit")), before + 1)

    def test_approval_choices_are_once_or_deny_not_persistent_grants(self):
        for policy, choice in (("approve", "once"), ("deny", "deny"), ("inherit", None)):
            with self.subTest(policy=policy):
                self.record["worker"]["hermes"]["approval"] = policy
                self.gateway.event = {"jsonrpc": "2.0", "method": "event", "params": {"type": "approval.request",
                    "session_id": "session-1", "admission_id": "admission-1", "payload": {"kind": "approval",
                    "prompt_id": "approval-1", "execution_generation": 1, "choices": ["once", "deny", "always"]}}}
                before = len(self.methods("approval.respond"))
                self.run_worker()
                after = self.methods("approval.respond")
                self.assertEqual(len(after), before + (choice is not None))
                if choice:
                    self.assertEqual(after[-1]["choice"], choice)

    def test_cancel_waits_for_terminal_receipt_and_checks_resources(self):
        self.gateway.mode = "wait"
        self.record["timeout_seconds"] = 1
        receipt, _ = self.run_worker(expected=125)
        self.assertEqual(receipt["state"], "terminal")
        self.assertEqual(receipt["turn_outcome"], "interrupted")
        self.assertTrue(receipt["cancel_requested"])
        self.assertEqual(self.methods("prompt.cancel"), [{"session_id": "session-1", "admission_id": "admission-1"}])
        self.assertEqual(self.methods("process.stop"), [{"session_id": "session-1"}])

    def test_delegation_cancel_ack_does_not_count_as_join(self):
        self.gateway.mode = "delegation-cancel"
        self.record["timeout_seconds"] = 1
        receipt, _ = self.run_worker(expected=75)
        self.assertEqual(receipt["state"], "unknown")
        self.assertIn("join proof", receipt["error"])

    def test_fragment_ping_and_extended_message_frames(self):
        message = "汉" * 30000
        payload = message.encode()
        self.gateway.wire_frames = frame(payload[:30], final=False) + frame(b"ping", opcode=9) + frame(payload[30:], opcode=0)
        client = transport.WebSocket(self.gateway.attach["url"], self.gateway.attach["protocols"])
        try:
            self.assertEqual(client.receive(), message)
        finally:
            client.close()

    def test_remote_endpoint_and_oversized_frame_are_rejected(self):
        with self.assertRaises(transport.GatewayError):
            transport.WebSocket("ws://example.invalid/api/ws", ["hermes-gateway-v1"])
        self.gateway.wire_frames = bytes((129, 127)) + struct.pack("!Q", transport.MAX_MESSAGE + 1)
        client = transport.WebSocket(self.gateway.attach["url"], self.gateway.attach["protocols"])
        try:
            with self.assertRaises(transport.GatewayError):
                client.receive()
        finally:
            client.close()


class ManagedHermesTests(unittest.TestCase):
    setUp = fixtures.PlaybookTests.setUp
    tearDown = fixtures.PlaybookTests.tearDown
    cli = fixtures.PlaybookTests.cli
    owner = fixtures.PlaybookTests.owner
    config = fixtures.PlaybookTests.config
    init = fixtures.PlaybookTests.init
    run_args = fixtures.PlaybookTests.run_args
    spawn = fixtures.PlaybookTests.spawn
    wait_process = fixtures.PlaybookTests.wait_process

    def prepare(self, mode):
        gateway = GatewayFixture(self.base, mode)
        self.addCleanup(gateway.close)
        config = self.config(workers=[{"id": "fake", "client": "hermes", "hermes": {"approval": "inherit"}}])
        self.init(config)
        return gateway

    def command(self, gateway):
        return [sys.executable, "-I", str(BRIDGE), "--binary", str(gateway.binary), "--prompt", "fixture"]

    def test_completed_gateway_attempt_remains_only_reported(self):
        gateway = self.prepare("complete")
        result = self.cli("run", *self.run_args("T1", self.command(gateway)))
        self.assertEqual(result["task"]["state"], "reported")
        self.assertFalse(result["accepted"])
        status = self.cli("status")["attempts"][0]
        self.assertEqual(status["external_execution"]["admission_id"], "admission-1")

    def test_unknown_gateway_attempt_retains_slot_and_blocks_retry(self):
        gateway = self.prepare("unknown")
        self.cli("run", *self.run_args("T1", self.command(gateway)), ok=False)
        result = self.cli("status")
        self.assertEqual(result["tasks"]["T1"]["state"], "unknown")
        self.assertEqual(result["attempts"][0]["external_execution"]["state"], "unknown")
        self.cli("run", *self.run_args("T1", self.command(gateway)), ok=False)
        self.assertEqual(sum(r["method"] == "prompt.submit" for r in gateway.requests), 1)

    def test_checkpoint_preserves_unknown_admission_identity_as_a_recovery_blob(self):
        gateway = self.prepare("unknown")
        self.cli("run", *self.run_args("T1", self.command(gateway)), ok=False)
        status = self.cli("status")
        attempt = status["attempts"][0]
        checkpoint = self.cli("checkpoint", *self.owner())["checkpoint"]
        location = Path(checkpoint["path"])
        manifest = json.loads((location / "manifest.json").read_text())
        record = manifest["work_protocol"]["files"]["logs/" + attempt["id"] + ".hermes.json"]
        receipt = json.loads((location / "blobs" / record["sha256"]).read_text())
        self.assertEqual(receipt["admission_id"], "admission-1")
        self.assertEqual(receipt["state"], "unknown")

    def test_arbitrary_hermes_cli_exit_cannot_prove_managed_completion(self):
        self.prepare("complete")
        result = self.cli("run", *self.run_args("T1", [sys.executable, "-c", "pass"]), ok=False)
        self.assertIn("matched gateway bridge", result.stderr)
        self.assertFalse(self.cli("status")["attempts"])

    def test_owner_cancel_uses_gateway_identity_and_records_confirmed_result(self):
        gateway = self.prepare("wait")
        process = self.spawn("run", *self.run_args("T1", self.command(gateway)))
        end = time.monotonic() + 5
        while not any(r["method"] == "prompt.receipt" for r in gateway.requests) and time.monotonic() < end:
            time.sleep(.02)
        attempt = self.cli("status")["attempts"][0]
        self.cli("cancel", *self.owner(), "--attempt", attempt["id"], "--reason", "fixture cancellation")
        result = self.wait_process(process, ok=False)
        self.assertEqual(result["attempt"]["returncode"], 125)
        self.assertTrue(result["attempt"]["cancelled"])
        self.assertEqual(result["attempt"]["external_execution"]["turn_outcome"], "interrupted")
        self.assertEqual(sum(r["method"] == "process.stop" for r in gateway.requests), 1)


if __name__ == "__main__":
    unittest.main()

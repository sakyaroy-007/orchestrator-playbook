#!/usr/bin/env python3
"""Managed Hermes admission bridge. Never run a model outside a reserved attempt.

Uses only the public local gateway attach/RPC protocol. The durable receipt is
cooperative evidence for one admission and its live resource projection, not a
proof that arbitrary external side effects or unregistered work have stopped.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import uuid

_spec = importlib.util.spec_from_file_location("playbook_hermes_gateway", Path(__file__).with_name("hermes_gateway.py"))
gateway = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gateway)
GatewayError = gateway.GatewayError
PROTOCOL = "hermes-gateway-v1"


def need(condition, message):
    if not condition:
        raise GatewayError(message)


def save(path, data):
    need(not path.is_symlink(), "Refusing a symlink receipt")
    fd, temporary = tempfile.mkstemp(prefix=".hermes-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Worker:
    def __init__(self, path, record, binary, prompt, log=None, precheck=False):
        self.path, self.record, self.binary, self.prompt = path, record, binary, prompt
        self.worker = record["worker"]
        self.policy = self.worker["hermes"]["approval"]
        self.rpc = None
        self.stop_requested = False
        self.submission_started = False
        self.cancel_sent = False
        self.seen_delegation = False
        self.answered = set()
        self.output = log
        self.precheck = precheck
        self.branch = ""
        if precheck:
            branch = subprocess.run(["git", "-C", record["cwd"], "branch", "--show-current"],
                                    capture_output=True, text=True, timeout=5)
            if branch.returncode == 0:
                self.branch = branch.stdout.strip()
        self.deadline = time.monotonic() + record["timeout_seconds"]

    def note(self, text):
        print(text, flush=True)
        if self.output:
            self.output.write(text + "\n")
            self.output.flush()

    def update(self, **values):
        self.record.update(values, updated_at=time.time())
        save(self.path, self.record)

    def connect(self, reconnect=False):
        command = [self.binary]
        if self.worker.get("profile"):
            command += ["--profile", self.worker["profile"]]
        command += ["gateway", "attach", "--json"]
        # No --start/--recover: service lifecycle is outside a worker's authority.
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=15, text=True)
        need(result.returncode == 0, "Hermes gateway attach failed; ensure the selected profile's owner is ready")
        try:
            attached = json.loads(result.stdout)
            endpoint = attached["endpoint"]
            need(attached.get("protocol") == PROTOCOL, "Unsupported Hermes gateway protocol")
            need(isinstance(endpoint, dict), "Attach lacks owner identity")
            for key in ("profile_id", "instance_id", "code_sha"):
                need(isinstance(endpoint.get(key), str) and endpoint[key], "Attach lacks " + key)
            need(attached.get("client_code_sha") == endpoint["code_sha"],
                 "Hermes client and running gateway versions differ; reconcile them before dispatch")
            owner = {key: endpoint[key] for key in ("profile_id", "instance_id", "code_sha")}
            if reconnect:
                need(owner == self.record["owner"], "Gateway owner changed; retain unknown work for reconciliation")
            self.rpc = gateway.RPC(gateway.WebSocket(attached["url"], attached["protocols"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise GatewayError("Invalid gateway attach response") from exc
        description = self.rpc.call("runtime.describe")
        need(description.get("profile_id") == owner["profile_id"]
             and description.get("instance_id") == owner["instance_id"], "Gateway owner identity changed during attach")
        need(type(description.get("authority_epoch")) is int, "Gateway lacks its authority epoch")
        if reconnect:
            need(description["authority_epoch"] == self.record["authority_epoch"], "Gateway authority epoch changed")
        capabilities = description.get("capabilities", [])
        need(isinstance(capabilities, list) and {"durable-admission-v1", "event-replay-v1", "local-cli-create-v1"}.issubset(capabilities),
             "Gateway lacks the required durable admission capabilities")
        creation = description.get("session_create", {})
        need(isinstance(creation, dict) and "tool" in creation.get("sources", []), "Gateway does not support tool sessions")
        fields = {"request_id", "source", "cwd"}
        for field, setting in (("model", "model"), ("reasoning", "effort")):
            if self.worker[setting]["mode"] == "fixed":
                fields.add(field)
        need(fields.issubset(creation.get("parameters", [])), "Gateway cannot apply the requested session settings")
        if not reconnect:
            self.update(owner=owner, authority_epoch=description["authority_epoch"],
                        capabilities=capabilities, scope="admission-and-live-session-resources")

    def snapshot(self, result):
        sid = result.get("session_id")
        need(isinstance(sid, str) and sid, "Gateway did not return a session identity")
        need(result.get("authority_epoch") == self.record["authority_epoch"], "Session owner epoch changed")
        if self.record.get("session_id"):
            need(sid == self.record["session_id"], "Gateway returned another session")
        info = result.get("info", {})
        need(isinstance(info, dict) and info.get("desktop_protocol") == PROTOCOL, "Unsupported session protocol")
        need(info.get("profile_id") == self.record["owner"]["profile_id"], "Session profile differs from attach profile")
        need(info.get("cwd") == self.record["cwd"], "Session cwd differs from reserved worktree")
        for field, setting in (("model", "model"), ("reasoning_effort", "effort")):
            if self.worker[setting]["mode"] == "fixed":
                need(info.get(field) == self.worker[setting]["value"], "Session did not confirm requested " + setting)
        observed = {key: info.get(key) for key in ("model", "reasoning_effort", "cwd", "source")}
        self.update(session_id=sid, stored_session_id=result.get("stored_session_id"), observed=observed)
        prompts = result.get("prompts", [])
        need(isinstance(prompts, list), "Invalid session prompt projection")
        for prompt in prompts:
            self.approval(prompt)

    def receipt(self, receipt):
        need(isinstance(receipt, dict), "Invalid admission receipt")
        admission = receipt.get("admission_id")
        need(isinstance(admission, str) and admission, "Submission did not return an admission identity")
        need(receipt.get("ref") == {"profile_id": self.record["owner"]["profile_id"], "session_id": self.record["session_id"]},
             "Receipt belongs to another session/profile")
        need(receipt.get("authority_epoch") == self.record["authority_epoch"], "Admission owner epoch changed")
        if self.record.get("admission_id"):
            need(admission == self.record["admission_id"], "Receipt belongs to another admission")
        need(receipt.get("status") in ("queued", "started", "unknown", "terminal"), "Unknown admission status")
        observed = {key: receipt.get(key) for key in ("admission_id", "status", "outcome", "authority_epoch", "execution_generation", "sequence")}
        self.update(admission_id=admission, admission=observed)
        return receipt

    def approval(self, prompt):
        if not isinstance(prompt, dict) or prompt.get("kind") != "approval":
            return
        identity, generation = prompt.get("prompt_id"), prompt.get("execution_generation")
        need(isinstance(identity, str) and type(generation) is int, "Invalid approval identity")
        if (identity, generation) in self.answered:
            return
        need(generation == self.record.get("admission", {}).get("execution_generation"), "Approval is not bound to the current admission generation")
        if self.policy == "inherit":
            self.update(waiting_approval={"prompt_id": identity, "execution_generation": generation})
            return
        choice = "once" if self.policy == "approve" and not self.stop_requested else "deny"
        need(choice in prompt.get("choices", []), "Requested approval response is unsupported")
        self.rpc.call("approval.respond", session_id=self.record["session_id"],
                      execution_generation=generation, prompt_id=identity, choice=choice)
        self.answered.add((identity, generation))
        self.update(approval_responses=len(self.answered))

    def events(self):
        events = list(self.rpc.events)
        self.rpc.events.clear()
        for event in events:
            if event.get("method") != "event":
                continue
            body = event.get("params", {})
            if not isinstance(body, dict) or body.get("session_id") != self.record.get("session_id"):
                continue
            if body.get("type") == "approval.request":
                if body.get("admission_id") not in (None, self.record.get("admission_id")):
                    raise GatewayError("Approval event belongs to another admission")
                self.approval(body.get("payload"))
            elif body.get("type") == "approval.settled":
                self.update(waiting_approval=None)

    def resources(self):
        children = self.rpc.call("subagent.list", session_id=self.record["session_id"])
        processes = self.rpc.call("process.list", session_id=self.record["session_id"])
        need(isinstance(children.get("subagents"), list) and isinstance(processes.get("processes"), list),
             "Gateway lacks live session resource projections")
        self.seen_delegation = self.seen_delegation or bool(children["subagents"])
        rows = processes["processes"]
        need(all(isinstance(row, dict) and row.get("status") in ("running", "exited") for row in rows),
             "Unknown background process status")
        observed = {"subagents": len(children["subagents"]),
                    "running_processes": sum(row["status"] == "running" for row in rows),
                    "observed_delegation": self.seen_delegation}
        self.update(resources=observed)
        return not observed["subagents"] and not observed["running_processes"]

    def request_cancel(self):
        self.update(cancel_requested=True)
        self.rpc.call("prompt.cancel", session_id=self.record["session_id"], admission_id=self.record["admission_id"])
        stopped = self.rpc.call("process.stop", session_id=self.record["session_id"])
        need(type(stopped.get("delegations")) is int and type(stopped.get("killed")) is int,
             "Invalid process.stop acknowledgement")
        self.seen_delegation = self.seen_delegation or stopped["delegations"] > 0
        self.cancel_sent = True
        self.update(cancel_acknowledged=True, cleanup=stopped)

    def reconnect(self):
        if self.rpc:
            self.rpc.close()
        self.connect(reconnect=True)
        snapshot = self.rpc.call("session.resume", session_id=self.record["session_id"], omit_messages=True)
        # Recover a lost submit ACK from its exact durable submission identity.
        if not self.record.get("admission_id"):
            matches = [row for row in snapshot.get("pending", []) if isinstance(row, dict)
                       and row.get("input_id") == self.record["submission_id"]]
            need(len(matches) == 1, "Lost submission acknowledgement could not be recovered; do not resubmit")
            self.receipt(matches[0])
        # A queued receipt has no generation. Refresh the same admission before
        # handling prompts from a resumed, now-running turn.
        self.receipt(self.rpc.call("prompt.receipt", session_id=self.record["session_id"],
                                  admission_id=self.record["admission_id"], include_result=True))
        self.snapshot(snapshot)
        self.update(reconnected=True)

    def run(self):
        self.update(create_request_id=uuid.uuid4().hex, submission_id=uuid.uuid4().hex,
                    prompt_sha256=hashlib.sha256(self.prompt.encode("utf-8")).hexdigest())
        self.connect()
        if self.stop_requested:
            raise GatewayError("Cancelled before submission")
        params = {"request_id": self.record["create_request_id"], "source": "tool", "cwd": self.record["cwd"]}
        for field, setting in (("model", "model"), ("reasoning", "effort")):
            if self.worker[setting]["mode"] == "fixed":
                params[field] = self.worker[setting]["value"]
        self.snapshot(self.rpc.call("session.create", **params))
        if self.stop_requested or time.monotonic() >= self.deadline:
            raise GatewayError("Stopped before submission")
        self.update(state="submitting")  # Durable before the first byte of task submission.
        self.submission_started = True
        reconnected = False
        try:
            self.receipt(self.rpc.call("prompt.submit", session_id=self.record["session_id"],
                submission_id=self.record["submission_id"], text=self.prompt))
        except (OSError, GatewayError, TimeoutError):
            self.reconnect()
            reconnected = True
        self.update(state="submitted")
        cleanup_deadline = None
        while True:
            try:
                if self.stop_requested or time.monotonic() >= self.deadline:
                    self.stop_requested = True
                    if cleanup_deadline is None:
                        cleanup_deadline = time.monotonic() + 15
                    if not self.cancel_sent:
                        self.request_cancel()
                receipt = self.receipt(self.rpc.call("prompt.receipt", session_id=self.record["session_id"],
                    admission_id=self.record["admission_id"], include_result=True))
                need(receipt["status"] != "unknown", "Gateway cannot determine the admission outcome")
                self.events()
                idle = self.resources()
                if receipt["status"] == "terminal" and idle:
                    outcome = receipt.get("outcome")
                    need(outcome in ("completed", "failed", "cancelled", "interrupted"), "Unsupported terminal outcome")
                    need(not (self.stop_requested and self.seen_delegation),
                         "Delegation interruption has no join proof; retain unknown reservation")
                    result = receipt.get("result")
                    if isinstance(result, dict) and isinstance(result.get("final_response"), str):
                        self.note(result["final_response"])
                    if outcome == "completed":
                        need(isinstance(result, dict) and isinstance(result.get("final_response"), str),
                             "Completed admission lacks its saved result")
                    code = 0 if outcome == "completed" else 125 if outcome in ("cancelled", "interrupted") else 1
                    if code == 0 and self.precheck:
                        passed = self.record["cwd"] in result["final_response"] and (not self.branch or self.branch in result["final_response"])
                        self.update(precheck_passed=passed)
                        if not passed:
                            code = 3
                            self.note("hermes-worker: cwd/branch precheck failed; inspect the saved response")
                    self.update(state="terminal", turn_outcome=outcome, returncode=code,
                                tracked_resources_idle=True, entire_task_tree_proven=False)
                    return code
                if cleanup_deadline is not None and time.monotonic() >= cleanup_deadline:
                    raise GatewayError("Cancellation did not reach a confirmed terminal observation")
                time.sleep(0.2)
            except (OSError, GatewayError, TimeoutError):
                if reconnected:
                    raise
                self.reconnect()
                reconnected = True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--log")
    parser.add_argument("--precheck", action="store_true")
    args = parser.parse_args(argv)
    path = Path(os.environ.get("PLAYBOOK_HERMES_RECEIPT", ""))
    need(path.is_absolute() and path.is_file() and not path.is_symlink() and path.stat().st_size < 1024 * 1024,
         "Hermes bridge requires a supervisor-owned receipt")
    record = json.loads(path.read_text(encoding="utf-8"))
    need(record.get("protocol") == PROTOCOL and record.get("state") == "not_submitted"
         and record.get("attempt_id") == os.environ.get("PLAYBOOK_ATTEMPT"), "Invalid or previously used worker receipt")
    output = None
    worker = None
    old_handlers = {}
    try:
        if args.log:
            target = Path(args.log)
            target.parent.mkdir(parents=True, exist_ok=True)
            output = target.open("x", encoding="utf-8")
        prompt = "Run only pwd and git branch --show-current; report their exact output." if args.precheck else args.prompt
        worker = Worker(path, record, args.binary, prompt, output, precheck=args.precheck)
        def stop(signum, frame):
            worker.stop_requested = True
        for signum in (signal.SIGTERM, signal.SIGINT):
            old_handlers[signum] = signal.signal(signum, stop)
        return worker.run()
    except (OSError, GatewayError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired) as exc:
        # Never include attach stdout, ticket headers, profile secrets or raw RPC errors.
        message = str(exc) if isinstance(exc, GatewayError) else type(exc).__name__ + " during gateway operation"
        if worker:
            worker.update(state="unknown" if worker.submission_started else "not_submitted", error=message)
            worker.note("hermes-worker: " + message)
            return 75 if worker.submission_started else 2
        raise GatewayError(message) from exc
    finally:
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)
        if worker and worker.rpc:
            worker.rpc.close()
        if output:
            output.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GatewayError, OSError, ValueError) as exc:
        print("hermes-worker: " + str(exc), file=sys.stderr)
        raise SystemExit(2)

#!/usr/bin/env python3
"""Bounded local hermes-gateway-v1 transport; Python 3.9+ standard library.

No Hermes imports, daemon start, credential storage, or remote WebSocket support.
Tickets supplied by the public attach command live only in this connection.
"""
import base64
import collections
import hashlib
import ipaddress
import json
import os
import re
import socket
import struct
import time
import urllib.parse

MAX_MESSAGE = 4 * 1024 * 1024


class GatewayError(Exception):
    pass


class WebSocket:
    def __init__(self, url, protocols, timeout=5):
        self.socket = None
        self.buffer = bytearray()
        self.fragments = bytearray()
        self.fragmenting = False
        self.fragment_count = 0
        parsed = urllib.parse.urlsplit(url)
        host = parsed.hostname
        try:
            local = host == "localhost" or ipaddress.ip_address(host).is_loopback
        except ValueError:
            local = False
        if (parsed.scheme != "ws" or not local or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path != "/api/ws"):
            raise GatewayError("Attach must provide a local ws:// loopback /api/ws endpoint")
        if (not isinstance(protocols, list) or "hermes-gateway-v1" not in protocols
                or len(protocols) > 4 or any(not isinstance(p, str) or len(p) > 8192
                or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", p) for p in protocols)):
            raise GatewayError("Invalid attach subprotocols")
        try:
            port = parsed.port
            if not port:
                raise GatewayError("Attach endpoint needs an explicit port")
            self.socket = socket.create_connection(("127.0.0.1" if host == "localhost" else host, port), timeout)
            nonce = base64.b64encode(os.urandom(16)).decode("ascii")
            host_header = "[%s]:%s" % (host, port) if ":" in host else "%s:%s" % (host, port)
            request = ("GET /api/ws HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\n"
                       "Connection: Upgrade\r\nSec-WebSocket-Version: 13\r\n"
                       "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Protocol: %s\r\n\r\n")
            self.socket.sendall((request % (host_header, nonce, ", ".join(protocols))).encode("ascii"))
            deadline = time.monotonic() + timeout
            while b"\r\n\r\n" not in self.buffer:
                if len(self.buffer) > 16384:
                    raise GatewayError("Oversized WebSocket handshake")
                self._receive(deadline)
            header, remaining = bytes(self.buffer).split(b"\r\n\r\n", 1)
            self.buffer = bytearray(remaining)
            lines = header.decode("ascii").split("\r\n")
            fields = {}
            for line in lines[1:]:
                name, separator, value = line.partition(":")
                if not separator or name.lower() in fields:
                    raise GatewayError("Malformed WebSocket handshake")
                fields[name.lower()] = value.strip()
            expected = base64.b64encode(hashlib.sha1((nonce + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()).decode("ascii")
            if (lines[0].split()[:2] != ["HTTP/1.1", "101"]
                    or fields.get("sec-websocket-accept") != expected
                    or fields.get("sec-websocket-protocol") != "hermes-gateway-v1"
                    or fields.get("upgrade", "").lower() != "websocket"
                    or "upgrade" not in fields.get("connection", "").lower().split(", ")):
                raise GatewayError("WebSocket protocol negotiation failed")
        except Exception:
            self.close()
            raise

    def close(self):
        if self.socket is not None:
            self.socket.close()
            self.socket = None

    def _receive(self, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Gateway receive deadline exceeded")
        self.socket.settimeout(remaining)
        data = self.socket.recv(65536)
        if not data:
            raise GatewayError("Gateway disconnected; accepted work may continue")
        self.buffer.extend(data)

    def send(self, text, opcode=1):
        payload = text.encode("utf-8") if isinstance(text, str) else text
        if len(payload) > MAX_MESSAGE:
            raise GatewayError("Outgoing gateway message exceeds the size limit")
        length = len(payload)
        header = bytes((0x80 | opcode, 0x80 | (length if length < 126 else 126 if length < 65536 else 127)))
        if length >= 126:
            header += struct.pack("!H" if length < 65536 else "!Q", length)
        mask = os.urandom(4)
        self.socket.settimeout(5)
        self.socket.sendall(header + mask + bytes(value ^ mask[i % 4] for i, value in enumerate(payload)))

    def receive(self, timeout=5):
        deadline = time.monotonic() + timeout
        while True:
            while len(self.buffer) < 2:
                self._receive(deadline)
            first, second = self.buffer[:2]
            final, opcode = bool(first & 128), first & 15
            if first & 112 or second & 128 or opcode not in (0, 1, 8, 9, 10):
                raise GatewayError("Unsupported or malformed gateway WebSocket frame")
            size, offset = second & 127, 2
            extended = 2 if size == 126 else 8 if size == 127 else 0
            while len(self.buffer) < offset + extended:
                self._receive(deadline)
            if extended:
                size = struct.unpack("!H" if extended == 2 else "!Q", self.buffer[2:2 + extended])[0]
                offset += extended
            if size > MAX_MESSAGE or (opcode >= 8 and (not final or size > 125)):
                raise GatewayError("Oversized or malformed gateway WebSocket frame")
            while len(self.buffer) < offset + size:
                self._receive(deadline)
            payload = bytes(self.buffer[offset:offset + size])
            del self.buffer[:offset + size]
            if opcode == 8:
                raise GatewayError("Gateway closed the connection; accepted work may continue")
            if opcode == 9:
                self.send(payload, opcode=10)
                continue
            if opcode == 10:
                continue
            if opcode == 1:
                if self.fragmenting:
                    raise GatewayError("Interleaved gateway text messages")
                self.fragments = bytearray()
                self.fragment_count = 0
            elif not self.fragmenting:
                raise GatewayError("Unexpected WebSocket continuation")
            self.fragments.extend(payload)
            self.fragment_count += 1
            if len(self.fragments) > MAX_MESSAGE or self.fragment_count > 1024:
                raise GatewayError("Gateway message exceeds the size limit")
            self.fragmenting = not final
            if final:
                try:
                    return bytes(self.fragments).decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise GatewayError("Gateway sent invalid UTF-8") from exc


class RPC:
    def __init__(self, websocket):
        self.websocket = websocket
        self.sequence = 0
        self.messages = collections.deque()
        self.events = collections.deque()

    def close(self):
        self.websocket.close()

    def call(self, method, **params):
        self.sequence += 1
        identity = self.sequence
        self.websocket.send(json.dumps({"jsonrpc": "2.0", "id": identity, "method": method, "params": params}))
        deadline = time.monotonic() + 5
        while True:
            if not self.messages:
                payload = self.websocket.receive(max(0, deadline - time.monotonic()))
                try:
                    rows = [json.loads(line) for line in payload.splitlines() if line.strip()]
                except ValueError as exc:
                    raise GatewayError("Gateway sent invalid JSON") from exc
                if len(rows) > 1024:
                    raise GatewayError("Gateway message batch exceeds limit")
                self.messages.extend(rows)
            message = self.messages.popleft()
            if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
                raise GatewayError("Gateway sent an invalid RPC envelope")
            if message.get("id") == identity and "method" not in message:
                if "error" in message:
                    # Do not echo arbitrary server errors: they may contain credentials.
                    error = message["error"]
                    code = error.get("code") if isinstance(error, dict) else None
                    raise GatewayError("Gateway rejected %s (code %s)" % (method, code))
                result = message.get("result")
                if not isinstance(result, dict):
                    raise GatewayError("Gateway %s returned a non-object result" % method)
                return result
            if "method" in message and "id" in message:
                self.websocket.send(json.dumps({"jsonrpc": "2.0", "id": message["id"],
                    "error": {"code": -32601, "message": "This worker does not answer interactive server requests"}}))
            elif "method" in message:
                if len(self.events) >= 1024:
                    raise GatewayError("Gateway event backlog exceeds limit")
                self.events.append(message)
            if time.monotonic() >= deadline:
                raise TimeoutError("Gateway RPC deadline exceeded")

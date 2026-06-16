import argparse
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path


DEFAULT_CONFIG = Path.home() / ".cursor" / "mcp.json"


def resolve_string(value: str, inputs: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        return inputs.get(key, match.group(0))

    return re.sub(r"\$\{input:([^}]+)\}", repl, value)


def build_command(command: str, args: list[str]) -> list[str]:
    lower = command.lower()
    if lower.endswith(".cmd") or lower.endswith(".bat"):
        return ["cmd.exe", "/d", "/c", command, *args]
    if lower.endswith(".ps1"):
        return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", command, *args]
    return [command, *args]


def start_readers(proc: subprocess.Popen[bytes], stderr_lines: list[str]):
    messages: "queue.Queue[dict]" = queue.Queue()
    protocol_errors: list[str] = []

    def read_stdout():
        stream = proc.stdout
        assert stream is not None
        for line in iter(stream.readline, b""):
            if not line:
                return
            try:
                decoded = line.decode("utf-8").strip()
            except Exception as exc:  # noqa: BLE001
                protocol_errors.append(f"Invalid stdout bytes: {exc}")
                return
            if not decoded:
                continue
            if not decoded.startswith("{"):
                protocol_errors.append(f"Unexpected stdout before JSON payload: {decoded}")
                return
            try:
                messages.put(json.loads(decoded))
            except Exception as exc:  # noqa: BLE001
                protocol_errors.append(f"Invalid JSON line: {exc}")
                return

    def read_stderr():
        stream = proc.stderr
        assert stream is not None
        for raw in iter(stream.readline, b""):
            if not raw:
                break
            try:
                stderr_lines.append(raw.decode("utf-8", errors="replace").rstrip())
            except Exception:  # noqa: BLE001
                stderr_lines.append(repr(raw))

    stdout_thread = threading.Thread(target=read_stdout, daemon=True)
    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stdout_thread.start()
    stderr_thread.start()
    return messages, protocol_errors


def write_message(proc: subprocess.Popen[bytes], payload: dict) -> None:
    body = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
    assert proc.stdin is not None
    proc.stdin.write(body)
    proc.stdin.flush()


def wait_for_response(
    messages: "queue.Queue[dict]",
    protocol_errors: list[str],
    request_id: int,
    timeout_s: float,
) -> dict:
    deadline = time.time() + timeout_s
    buffered: list[dict] = []
    while time.time() < deadline:
        if protocol_errors:
            raise RuntimeError(protocol_errors[0])
        remaining = max(0.1, deadline - time.time())
        try:
            msg = messages.get(timeout=remaining)
        except queue.Empty:
            continue
        if msg.get("id") == request_id:
            return msg
        buffered.append(msg)
    raise TimeoutError(f"Timed out waiting for response id={request_id}")


def smoke_server(name: str, spec: dict, inputs: dict[str, str], timeout_s: float) -> dict:
    command = resolve_string(spec["command"], inputs)
    args = [resolve_string(arg, inputs) for arg in spec.get("args", [])]
    env = os.environ.copy()
    for key, value in spec.get("env", {}).items():
        env[key] = resolve_string(value, inputs)

    stderr_lines: list[str] = []
    cmd = build_command(command, args)
    started = time.time()
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=str(Path.cwd()),
    )
    messages, protocol_errors = start_readers(proc, stderr_lines)

    result = {
        "name": name,
        "command": cmd,
        "initialize_ok": False,
        "tools_list_ok": False,
        "tool_count": None,
        "stderr_tail": None,
        "error": None,
        "duration_s": None,
    }

    try:
        write_message(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "cursor-mcp-smoke", "version": "0.1"},
                },
            },
        )
        init_resp = wait_for_response(messages, protocol_errors, 1, timeout_s)
        if "error" in init_resp:
            raise RuntimeError(f"initialize error: {init_resp['error']}")
        result["initialize_ok"] = True

        write_message(
            proc,
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        )
        write_message(
            proc,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
        tools_resp = wait_for_response(messages, protocol_errors, 2, timeout_s)
        if "error" in tools_resp:
            raise RuntimeError(f"tools/list error: {tools_resp['error']}")
        tools = tools_resp.get("result", {}).get("tools", [])
        result["tools_list_ok"] = True
        result["tool_count"] = len(tools)
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
    finally:
        result["stderr_tail"] = stderr_lines[-20:]
        result["duration_s"] = round(time.time() - started, 3)
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:  # noqa: BLE001
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass

    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--server", action="append", dest="servers")
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--github-pat", default=os.environ.get("SMOKE_GITHUB_PAT", ""))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    mcp_servers: dict[str, dict] = config["mcpServers"]

    names = args.servers or list(mcp_servers.keys())
    inputs = {"github_pat": args.github_pat}

    results = []
    for name in names:
        if name not in mcp_servers:
            results.append({"name": name, "error": "server not found in config"})
            continue
        results.append(smoke_server(name, mcp_servers[name], inputs, args.timeout))

    payload = {"config": str(args.config), "results": results}
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

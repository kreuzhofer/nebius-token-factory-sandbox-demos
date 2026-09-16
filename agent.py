"""Runs inside the microVM. No third-party dependencies required."""

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path


def run_python(code):
    result = subprocess.run(
        [sys.executable, "-I", "-c", code],
        capture_output=True,
        text=True,
        timeout=15,
        env={"PATH": os.defpath},
        cwd="/tmp",
    )
    return {
        "exit_code": result.returncode,
        "stdout": result.stdout[:12000],
        "stderr": result.stderr[:12000],
    }


def main():
    mode = sys.argv[1]
    if mode == "smoke":
        result = run_python(
            'import json; print(json.dumps({"sum_of_squares": sum(x*x for x in range(1,11))}))'
        )
        assert result["exit_code"] == 0
        assert json.loads(result["stdout"])["sum_of_squares"] == 385
        Path("/tmp/smoke.json").write_text(json.dumps(result))
        print(json.dumps({"stage": "smoke", "result": result}))
        return
    key = os.environ.pop("NEBIUS_API_KEY")
    model = os.environ["NEBIUS_MODEL"]
    messages = [
        {
            "role": "system",
            "content": "You are a Python agent. Use run_python to compute the answer before responding. Tool execution is limited to 15 seconds. Python runs as a script: explicitly print results so they appear in stdout. If stdout is empty, run the tool again with print statements before answering.",
        },
        {
            "role": "user",
            "content": "Find all primes below 100, their count and their sum. Verify your result using Python, then give a short answer.",
        },
    ]
    tool = {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": "Execute Python in this sandbox.",
            "parameters": {
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"],
                "additionalProperties": False,
            },
        },
    }
    used_tool = False
    for turn in range(5):
        payload = {
            "model": model,
            "messages": messages,
            "tools": [tool],
            "max_tokens": 1200,
            "tool_choice": "auto"
            if used_tool
            else {"type": "function", "function": {"name": "run_python"}},
        }
        req = urllib.request.Request(
            "https://api.tokenfactory.nebius.com/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            message = json.load(response)["choices"][0]["message"]
        messages.append(message)
        calls = message.get("tool_calls") or []
        if not calls:
            if not used_tool or not message.get("content"):
                raise RuntimeError("Model did not complete the tool-assisted task")
            print(json.dumps({"stage": "agent", "answer": message["content"], "turns": turn + 1}))
            return
        for call in calls:
            try:
                if call["function"]["name"] != "run_python":
                    raise ValueError("Unsupported tool")
                result = run_python(json.loads(call["function"]["arguments"])["code"])
            except (ValueError, KeyError, subprocess.TimeoutExpired) as exc:
                result = {"error": type(exc).__name__}
            used_tool = True
            print(
                json.dumps(
                    {"tool": "run_python", "code": call["function"]["arguments"], "result": result}
                ),
                flush=True,
            )
            messages.append(
                {"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)}
            )
    raise RuntimeError("Agent exceeded five inference turns")


if __name__ == "__main__":
    main()

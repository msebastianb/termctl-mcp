#!/usr/bin/env python3
"""Round 4: the REAL comparison, with an independent judge.

Two lessons from the previous rounds:
 1. removing ~/.local/bin from PATH is not enough: Hermes's terminal tool launches a LOGIN
    shell and zsh re-reads the profile, putting termctl back. Here the binary is actually
    moved and replaced by a stub that answers "command not found" (the real one stays in
    termctl.real and is used by the judge).
 2. the verdict is not taken from the model's answer (which can say "done" vacuously):
    after every run the judge reads the window and decides pass/fail.

Tasks: identify the sessions, follow a stream, answer a menu. Conditions:
"no tool" (neither MCP tool nor command) versus "with the MCP tools".
"""
import importlib.util
import json
import os
import subprocess
import time

SPEC = os.path.expanduser("~/.hermes/cache/scratch/bench_mcp_vs_cli.py")
spec = importlib.util.spec_from_file_location("bench", SPEC)
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

REAL = os.path.expanduser("~/.local/bin/termctl")
HIDDEN = REAL + ".real"
STUB = '#!/bin/sh\necho "zsh: command not found: termctl" >&2\nexit 127\n'
OUT = os.path.expanduser("~/.hermes/cache/scratch/bench-mcp/round4")
os.makedirs(OUT, exist_ok=True)


def shim_on():
    """Makes termctl truly non-existent: moves the binary (no stub, because a stub
    would make it 'present but broken', and the model would waste turns trying to fix it)."""
    if os.path.exists(REAL):
        os.rename(REAL, HIDDEN)


def shim_off():
    if os.path.exists(HIDDEN) and not os.path.exists(REAL):
        os.rename(HIDDEN, REAL)


def judge_tool():
    """The real binary, even when the stub is in between."""
    return HIDDEN if os.path.exists(HIDDEN) else REAL


def judge(kind, wid):
    t = judge_tool()
    try:
        out = subprocess.run([t, "read", str(wid), "-n", "12"], capture_output=True,
                             text=True, timeout=60, stdin=subprocess.DEVNULL)
        lines = json.loads(out.stdout.strip().splitlines()[-1]).get("lines", [])
    except Exception as e:
        return {"verified": False, "error": str(e)[:80]}
    blob = "\n".join(lines)
    if kind == "menu":
        ok = "last choice: three" in blob
        return {"verified": ok, "expected": "last choice: three",
                "seen": [l.strip() for l in lines if "last choice" in l]}
    if kind == "stream":
        ok = "STREAM COMPLETE" in blob
        return {"verified": ok, "expected": "STREAM COMPLETE: 60 lines",
                "seen": [l.strip() for l in lines if "STREAM COMPLETE" in l]}
    return {}


def run(name, use_mcp, kind=None):
    tag = f"{name}-{'mcp' if use_mcp else 'without'}"
    print(f"[{time.strftime('%H:%M:%S')}] {tag}: preparing", flush=True)
    wid = None
    if kind == "menu":
        wid = b.setup_menu()
    elif kind == "stream":
        wid = b.setup_stream()
    if use_mcp:
        shim_off()
        b.set_mcp(True)
    else:
        b.set_mcp(False)
        shim_on()
    time.sleep(2)

    t0 = time.time()
    try:
        p = subprocess.run([b.HERMES, "-z", b.TASKS[name], "-m", b.MODEL, "--provider", b.PROVIDER,
                            "--usage-file", os.path.join(OUT, f"usage-{tag}.json")],
                           capture_output=True, text=True, timeout=b.RUN_TIMEOUT,
                           stdin=subprocess.DEVNULL)
        answer = p.stdout
    except subprocess.TimeoutExpired:
        answer = ""
    dur = round(time.time() - t0, 1)

    verdict = judge(kind, wid) if kind else {}
    usage = {}
    try:
        usage = json.load(open(os.path.join(OUT, f"usage-{tag}.json")))
    except Exception:
        pass
    rec = {"task": name, "condition": "MCP termctl" if use_mcp else "no tool, no command",
           "duration_s": dur, "usage": usage, "answer_chars": len((answer or "").strip()),
           "verdict": verdict, "window": wid}
    json.dump(rec, open(os.path.join(OUT, f"res-{tag}.json"), "w"), ensure_ascii=False, indent=1)
    print(f"[{time.strftime('%H:%M:%S')}] {tag}: {dur}s, {usage.get('total_tokens','?')} token, "
          f"verdict={verdict.get('verified')}", flush=True)
    return rec


def main():
    shim_off()                     # recovery if a previous round died halfway
    results = []
    try:
        for name, kind in (("T1_identify", None), ("T2_stream", "stream"), ("T3_menu", "menu")):
            for use_mcp in (True, False):
                results.append(run(name, use_mcp, kind))
                json.dump(results, open(os.path.join(OUT, "rounds.json"), "w"),
                          ensure_ascii=False, indent=1)
    finally:
        shim_off()
        b.set_mcp(True)
        b.close_titled("stream-bench")
        b.close_titled("menu-bench")
    print("END round 4. Results in", OUT, flush=True)


if __name__ == "__main__":
    main()

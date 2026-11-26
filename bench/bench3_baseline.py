#!/usr/bin/env python3
"""Third round: the REAL comparison — with termctl (MCP tool) versus without termctl at all.

In rounds 1 and 2 the "without" condition still had termctl as a shell command (it is on
PATH), so it measured "MCP tool versus CLI". Here the control condition also removes
the binary from PATH: the model must make do with osascript, i.e. as it happened
this morning. The skill stays readable: it is a severe comparison against the "without",
I state it.
"""
import importlib.util
import os

SPEC = os.path.expanduser("~/.hermes/cache/scratch/bench_mcp_vs_cli.py")
spec = importlib.util.spec_from_file_location("bench", SPEC)
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

b.OUT = os.path.expanduser("~/.hermes/cache/scratch/bench-mcp/round3")
os.makedirs(b.OUT, exist_ok=True)

ORIG = os.environ.get("PATH", "")
PRUNED = ":".join(p for p in ORIG.split(":") if "/.local/bin" not in p)

try:
    for name in ("T1_identify", "T3_menu"):
        # A) without termctl: no MCP tool, and the command does not exist on PATH
        os.environ["PATH"] = PRUNED
        rec = b.run_task(name, b.TASKS[name], False)
        rec["condition"] = "no tool, no CLI"
        # B) with termctl: the MCP tools
        os.environ["PATH"] = ORIG
        b.run_task(name, b.TASKS[name], True)
finally:
    os.environ["PATH"] = ORIG
    b.set_mcp(True)
    b.close_titled("stream-bench")
    b.close_titled("menu-bench")
print("END round 3. Results in", b.OUT, flush=True)

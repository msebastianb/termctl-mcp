#!/usr/bin/env python3
"""Second round of the benchmark: T2 (stream) and T3 (menu) with the fixed guidance.

The only difference from the first round is the instruction: it now says to prefer the
`mcp__termctl__*` tools when present and to wait with the most efficient means instead of
polling on the reads. It measures whether the defect found (225,000 tokens for polling)
is closed.
"""
import importlib.util
import os
import sys

SPEC = os.path.expanduser("~/.hermes/cache/scratch/bench_mcp_vs_cli.py")
spec = importlib.util.spec_from_file_location("bench", SPEC)
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

b.OUT = os.path.expanduser("~/.hermes/cache/scratch/bench-mcp/round2")
os.makedirs(b.OUT, exist_ok=True)

try:
    for name in ("T2_stream", "T3_menu"):
        for cond in (True, False):
            b.run_task(name, b.TASKS[name], cond)
finally:
    b.set_mcp(True)
    b.close_titled("stream-bench")
    b.close_titled("menu-bench")
print("END round 2. Results in", b.OUT, flush=True)

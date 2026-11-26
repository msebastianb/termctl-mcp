#!/usr/bin/env python3
"""Aggregates every benchmark round (with/without termctl) into one table."""
import glob
import json
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "raw")
ROUNDS = [("round 1 · old instructions", ""), ("round 2 · fixed guidance", "round2"),
          ("round 3 · pruned PATH (invalid control)", "round3"), ("round 4 · true absence", "round4")]


def load_recs(sub):
    recs = []
    for p in sorted(glob.glob(os.path.join(ROOT, f"{sub}-res-*.json"))):
        try:
            recs.append(json.load(open(p)))
        except Exception:
            pass
    return recs


def short(cond):
    if "MCP" in cond:
        return "MCP"
    return "without" if "no tool" in cond else "CLI"


def main():
    for label, sub in ROUNDS:
        recs = load_recs(sub)
        if not recs:
            continue
        print(f"\n=== {label} ===")
        print(f"{'task':14} {'cond':6} {'sec':>6} {'calls':>5} {'token':>9} {'verdict':>10}")
        for r in recs:
            u = r.get("usage", {})
            g = r.get("verdict", {})
            verdict = "" if not g else ("PASS" if g.get("verified") else "FAIL")
            print(f"{r['task']:14} {short(r['condition']):6} {r['duration_s']:>6.1f} "
                  f"{str(u.get('api_calls')):>5} {str(u.get('total_tokens')):>9} {verdict:>10}")
    print("\n(independent verdict only in round 4: the judge reads it from the window itself)")


if __name__ == "__main__":
    main()

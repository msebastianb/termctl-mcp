#!/usr/bin/env python3
"""Reads the benchmark results (with/without termctl) and prints the comparison."""
import glob
import json
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "raw")


def load(path, default=None):
    try:
        return json.load(open(path))
    except Exception:
        return default


def row(rec):
    u = rec.get("usage", {})
    l = rec.get("load", {})
    def m(key, field="max"):
        v = l.get(key)
        return v.get(field) if isinstance(v, dict) else None
    return {
        "task": rec["task"], "cond": rec["condition"], "s": rec["duration_s"],
        "calls": u.get("api_calls"), "tok_in": u.get("input_tokens"),
        "tok_out": u.get("output_tokens"), "tok": u.get("total_tokens"),
        "wired": m("wired_gb"), "comp": m("compressor_gb"), "gpu": m("gpu_util_pct"),
        "gpu_mem": m("gpu_mem_mb"), "swap": m("swap_used_mb"),
        "llama_rss": m("llama_rss_gb"), "llama_cpu": m("llama_cpu_pct"),
        "load1": m("load1"), "thermal": l.get("thermal_peak"), "n": rec.get("samples"),
    }


def main():
    base = load(os.path.join(OUT, "baseline.json"), {})
    recs = [load(p) for p in sorted(glob.glob(os.path.join(OUT, "*res-*.json")))]
    recs = [r for r in recs if r]
    if not recs:
        print("no results yet")
        return
    print("IDLE LOAD (reference):", {k: v.get("mean") for k, v in base.items()
                                         if isinstance(v, dict) and k in
                                         ("wired_gb", "compressor_gb", "gpu_util_pct",
                                          "gpu_mem_mb", "swap_used_mb", "llama_rss_gb", "load1")})
    hdr = f"{'task':14} {'condition':14} {'sec':>6} {'calls':>5} {'tok_in':>9} {'tok_out':>8} {'total':>9}"
    hdr += f" {'wired':>6} {'comp':>6} {'gpu%':>5} {'gpuMB':>6} {'swap':>7} {'llamaGB':>8} {'cpu%':>5} {'load1':>5} {'term':>7}"
    print("\n" + hdr)
    for r in recs:
        d = row(r)
        def f(v, w, dec=None):
            if v is None:
                return " " * (w - 1) + "-"
            return f"{v:>{w}.{dec}f}" if dec is not None else f"{v:>{w}}"
        print(f"{d['task']:14} {d['cond']:14} {d['s']:>6.1f} {f(d['calls'],5)} {f(d['tok_in'],9)}"
              f" {f(d['tok_out'],8)} {f(d['tok'],9)} {f(d['wired'],6,1)} {f(d['comp'],6,1)}"
              f" {f(d['gpu'],5)} {f(d['gpu_mem'],6)} {f(d['swap'],7)} {f(d['llama_rss'],8,2)}"
              f" {f(d['llama_cpu'],5,1)} {f(d['load1'],5,2)} {str(d['thermal'] or '-'):>7}")
    print("\n=== answers (for the verdict) ===")
    for r in recs:
        print(f"\n--- {r['task']} / {r['condition']} ---")
        print("\n".join("   " + l for l in ((f"({r.get('answer_chars', 0)} chars, not reproduced)")).splitlines()[:8]))


if __name__ == "__main__":
    main()

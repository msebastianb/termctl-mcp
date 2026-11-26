#!/usr/bin/env python3
"""Benchmark: the local model (Inkling) with and without the termctl MCP tools.

Same model, same prompt, same base toolset: the only difference is whether the
`termctl` MCP server is active. For every run it also samples machine load
(wired/compressor/swap RAM, GPU, thermal state, CPU and RSS of llama-server).

Usage:  python3 bench_mcp_vs_cli.py            (writes everything to ./bench-mcp/)
"""
import json
import os
import re
import statistics
import subprocess
import threading
import time

HERMES = os.path.expanduser("~/.hermes/hermes-agent/.hermes/bin/hermes")
TERMCTL = os.path.expanduser("~/.local/bin/termctl")
MENU = os.path.expanduser("~/.hermes/cache/scratch/termctl-menu.py")
MODEL = "Inkling-2-Mini-UD-Q4_K_XL"
PROVIDER = "inkling-q4"
OUT = os.path.expanduser("~/.hermes/cache/scratch/bench-mcp")
RUN_TIMEOUT = 420

os.makedirs(OUT, exist_ok=True)

TASKS = {
    "T1_identify": ("I have two GitHub Copilot CLI sessions open in Terminal. "
                      "Tell me for each: the window id, the title and whether it is working "
                      "or waiting for input. Answer in English, at most 6 lines."),
    "T2_stream": ("In the Terminal session titled 'stream-bench' a long job is running. "
                  "Follow it to the end and tell me: the last line printed, how many lines "
                  "it printed and whether the job is done. Do not waste repeated reads: wait "
                  "for completion with the most efficient means you have. Answer in English, "
                  "at most 6 lines."),
    "T3_menu": ("In the Terminal session titled 'menu-bench' there is an on-screen menu. "
                "Choose the option 'three' and tell me what appears on screen after the choice. "
                "Answer in English, at most 6 lines."),
}


def sh(cmd, timeout=30):
    try:
        return subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True,
                              text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    except Exception as e:
        return type("R", (), {"stdout": "", "stderr": str(e), "returncode": 1})()


def termctl(*args, timeout=60):
    p = sh([TERMCTL, *args], timeout=timeout)
    for line in reversed((p.stdout or "").strip().splitlines()):
        try:
            return json.loads(line)
        except Exception:
            continue
    return {"ok": False, "raw": (p.stdout or p.stderr or "")[-200:]}


def set_mcp(on):
    sh([HERMES, "config", "set", "mcp_servers.termctl.enabled", "true" if on else "false"])


def _pages(v, name):
    m = re.search(rf"{name}:\s+(\d+)", v)
    return int(m.group(1)) if m else 0


def sample():
    d = {"t": round(time.time(), 1)}
    v = sh("vm_stat").stdout
    m = re.search(r"page size of (\d+)", v)
    ps_ = int(m.group(1)) if m else 4096
    d["wired_gb"] = round(_pages(v, "Pages wired down") * ps_ / 1e9, 2)
    d["compressor_gb"] = round(_pages(v, "Pages occupied by compressor") * ps_ / 1e9, 2)
    d["free_mb"] = round(_pages(v, "Pages free") * ps_ / 1e6)
    m = re.search(r"used = ([\d.]+)M", sh("sysctl vm.swapusage").stdout)
    d["swap_used_mb"] = float(m.group(1)) if m else None
    g = sh("ioreg -r -d 1 -c IOAccelerator | grep -o '\"Device Utilization %\"=[0-9]*'").stdout
    m = re.search(r"=(\d+)", g)
    d["gpu_util_pct"] = int(m.group(1)) if m else None
    g = sh("ioreg -r -d 1 -c IOAccelerator | grep -o '\"In use system memory\"=[0-9]*'").stdout
    m = re.search(r"=(\d+)", g)
    d["gpu_mem_mb"] = round(int(m.group(1)) / 1e6, 1) if m else None
    d["thermal"] = (sh(["/tmp/therm"]).stdout or "?").strip()
    psout = sh("ps -Ao rss=,pcpu=,command= | grep llama-server | grep -v grep").stdout
    tot_rss, tot_cpu = 0, 0.0
    for line in psout.splitlines():
        p = line.split(None, 2)
        if len(p) == 3 and p[0].isdigit():
            tot_rss += int(p[0])
            tot_cpu += float(p[1])
    d["llama_rss_gb"] = round(tot_rss / 1048576, 2) if psout.strip() else None
    d["llama_cpu_pct"] = round(tot_cpu, 1) if psout.strip() else None
    la = sh("sysctl -n vm.loadavg").stdout.split()
    d["load1"] = float(la[1]) if len(la) >= 3 else None
    return d


def close_titled(fragment):
    for s in termctl("list").get("sessions", []):
        if fragment in s["title"]:
            termctl("close", str(s["id"]), "--force")


def setup_stream():
    close_titled("stream-bench")
    out = termctl("new", "--cmd", 'for i in $(seq 1 60); do echo "[pipeline] step $i/60"; '
                                 'sleep 2; done; echo "STREAM COMPLETE: 60 lines"',
                  "--title", "stream-bench", timeout=60)
    return out.get("id")


def setup_menu():
    close_titled("menu-bench")
    out = termctl("new", "--cmd", f"/usr/bin/python3 {MENU}", "--title", "menu-bench", timeout=60)
    time.sleep(3)
    return out.get("id")


def summarise(load):
    if not load:
        return {}
    def agg(key):
        vals = [x[key] for x in load if isinstance(x.get(key), (int, float))]
        if not vals:
            return {}
        return {"mean": round(statistics.mean(vals), 2), "max": round(max(vals), 2)}
    out = {}
    for k in ("wired_gb", "compressor_gb", "gpu_util_pct", "gpu_mem_mb", "swap_used_mb",
              "llama_rss_gb", "llama_cpu_pct", "load1", "free_mb"):
        a = agg(k)
        if a:
            out[k] = a
    thermals = [x["thermal"] for x in load if x.get("thermal")]
    if thermals:
        out["thermal_peak"] = max(thermals, key=lambda t: ["nominal", "fair", "serious",
                                                           "critical"].index(t)
                                  if t in ["nominal", "fair", "serious", "critical"] else 0)
    return out


def run_task(name, prompt, use_mcp):
    tag = f"{name}-{'mcp' if use_mcp else 'cli'}"
    print(f"[{time.strftime('%H:%M:%S')}] {tag}: preparing...", flush=True)
    if name == "T2_stream":
        setup_stream()
    elif name == "T3_menu":
        setup_menu()
    set_mcp(use_mcp)
    time.sleep(2)

    usage_path = os.path.join(OUT, f"usage-{tag}.json")
    load, stop = [], {"done": False}

    def loop():
        while not stop["done"]:
            try:
                load.append(sample())
            except Exception as e:
                load.append({"error": str(e)})
            time.sleep(2)

    th = threading.Thread(target=loop, daemon=True)
    th.start()
    t0 = time.time()
    try:
        p = subprocess.run([HERMES, "-z", prompt, "-m", MODEL, "--provider", PROVIDER,
                            "--usage-file", usage_path],
                           capture_output=True, text=True, timeout=RUN_TIMEOUT,
                           stdin=subprocess.DEVNULL)
        answer, err = p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        answer, err = "", f"timeout after {RUN_TIMEOUT}s"
    duration = round(time.time() - t0, 1)
    stop["done"] = True
    th.join(timeout=10)

    usage = {}
    try:
        usage = json.load(open(usage_path))
    except Exception:
        pass
    rec = {"task": name, "condition": "MCP termctl" if use_mcp else "shell only",
           "duration_s": duration, "usage": usage, "answer_chars": len((answer or "").strip()),
           "stderr_tail": (err or "")[-300:], "load": summarise(load), "samples": len(load)}
    json.dump(rec, open(os.path.join(OUT, f"res-{tag}.json"), "w"), ensure_ascii=False, indent=1)
    print(f"[{time.strftime('%H:%M:%S')}] {tag}: {duration}s, "
          f"{usage.get('total_tokens','?')} token, {usage.get('api_calls','?')} calls", flush=True)
    return rec


def main():
    # idle load, as a reference
    base = summarise([sample() for _ in range(5)])
    json.dump(base, open(os.path.join(OUT, "baseline.json"), "w"), indent=1)
    results = []
    try:
        for name, prompt in TASKS.items():
            for use_mcp in (True, False):
                results.append(run_task(name, prompt, use_mcp))
            json.dump(results, open(os.path.join(OUT, "rounds.json"), "w"),
                      ensure_ascii=False, indent=1)
    finally:
        set_mcp(True)
        close_titled("stream-bench")
        close_titled("menu-bench")
    print("END. Results in", OUT, flush=True)


if __name__ == "__main__":
    main()

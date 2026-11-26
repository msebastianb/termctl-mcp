# termctl — a terminal MCP server

`termctl` gives an agent hands on a **real** terminal session: the one a human is looking at, not
a headless shell. It runs locally on the Mac and speaks MCP over stdio — 17 tools, one per verb —
with the same code also usable as a CLI.

It exists for the case public agent benchmarks skip. Terminal-Bench, TUA-Bench and LongCLI-Bench
all give the agent its own container: an empty shell nobody is watching. The hard part in
practice is different — a `Terminal.app` window that is **already open**, where a coding agent is
mid-conversation, a job is streaming output, a TUI is waiting on an arrow key, and nothing tells
the model which window is which. `termctl` is the interface for that.

This repository also contains the measurement of what it adds, since no public benchmark covers
the case: same model, same tasks, with and without the tool.

## What it does

- **see** — `list` the open windows, `read` what is on their screens, `search` for a text across
  all of them, and `status` to know whether a session is working, parked at a prompt, or blocked
  on a question it is waiting for an answer to;
- **act** — `send` a command or a reply, `run` a shell command and get its exit code alone, `key`
  a single keystroke (arrows, `ctrl-*`, `esc`, `tab`), `choose` an entry in a TUI menu, `new` a
  window from an agent preset, `close` it when done;
- **wait** — `wait_for` a marker to appear in the scrollback, or `watch` the output go quiet, so
  the agent blocks instead of polling in circles.

## Install and connect

Requirements: macOS (it drives `Terminal.app` through AppleScript), Python 3, and the Automation
permission for whichever app hosts the client — Terminal, Claude Desktop, the Copilot CLI —
under *System Settings → Privacy & Security → Automation*. Without it, AppleScript fails with
`-1743`.

```bash
install -m 755 termctl ~/.local/bin/termctl
```

**Claude Code** — one command, `user` scope so it follows you into every project:

```bash
claude mcp add -s user termctl -- /Users/you/.local/bin/termctl mcp
claude mcp list                             # should list termctl as a stdio server
```

**Claude Desktop** — the same server in
`~/Library/Application Support/Claude/claude_desktop_config.json`, then restart the app:

```json
{
  "mcpServers": {
    "termctl": { "command": "/Users/you/.local/bin/termctl", "args": ["mcp"] }
  }
}
```

Already running servers in Claude Desktop and moving to Claude Code? `claude mcp
add-from-claude-desktop` imports them.

**GitHub Copilot CLI** — a local stdio server goes after `--`:

```bash
copilot mcp add termctl -- /Users/you/.local/bin/termctl mcp
copilot mcp list                            # user servers, from ~/.copilot/mcp-config.json
```

The same entry written by hand, in `~/.copilot/mcp-config.json` (user scope) or `.mcp.json` /
`.github/mcp.json` (workspace scope):

```json
{
  "mcpServers": {
    "termctl": {
      "type": "local",
      "command": "/Users/you/.local/bin/termctl",
      "args": ["mcp"],
      "tools": ["*"]
    }
  }
}
```

Copilot calls local stdio servers `local` (not `stdio`) — that is what `copilot mcp add` writes.

**Hermes Agent**, which the measurement below used:

```bash
hermes mcp add termctl --command ~/.local/bin/termctl --args mcp
hermes mcp test termctl                     # transport check
```

**Any other MCP client** — stdio, one executable, no dependencies:

```json
{
  "mcpServers": {
    "termctl": { "command": "/Users/you/.local/bin/termctl", "args": ["mcp"] }
  }
}
```

Or straight from the shell — same verbs, same code:

```bash
termctl list                                # windows: id, tty, busy, title
termctl status 62                           # working / at a prompt / waiting
termctl send 62 "npm test"                  # type and press Return
termctl send 62 "make" --wait-for "Done"    # block until a marker shows up
termctl run 62 "git status"                 # exit code + that command's output only
termctl choose 62 2                         # pick entry 2 of a TUI menu
termctl new --preset claude-yolo            # open a window with a coding agent in it
```

Every call is logged to `~/.local/state/termctl.log` with a timestamp, the verb and the calling
process — so when an agent misbehaves you can see exactly what it asked for, and by whom.

## Tools

| tool | what it does | size |
|---|---|---|
| `list` | open `Terminal.app` windows (id, tty, busy, title) | 160 B |
| `brief` | what a session is, what was last asked of it, its state, last output | 233 B |
| `status` | working, parked at a prompt, or waiting for an answer? state + detail | 276 B |
| `info` | session details: processes on its tty, cwd, which agent, last lines | 233 B |
| `search` | search a text across all sessions, and say which one has it | 235 B |
| `read` | last lines of a session, with optional grep filter and context lines | 294 B |
| `delta` | only the **new** lines since the last read of that session | 253 B |
| `send` | types text and presses Return; with `wait_for`, waits for a marker | 376 B |
| `run` | sends a command to a shell, returns exit code + only its output | 296 B |
| `choose` | answers a TUI menu (entry number, or part of its text) | 271 B |
| `key` | sends a single key (arrows, `ctrl-*`, `esc`, `tab`, …) | 430 B |
| `new` | opens a window (agent preset or shell), returns its id | 416 B |
| `title` | renames a window, so `list` says which one it is | 219 B |
| `close` | closes a window (`force`: also kills the processes running in it) | 232 B |
| `watch` | waits for the output to go quiet (N idle seconds), returns the last lines | 294 B |
| `wait_for` | waits for a marker in that session's scrollback | 343 B |
| `ask` | asks a CLI agent (`claude`, `copilot`) in a window a direct question | 424 B |

The whole surface costs an agent's context **4,985 bytes ≈ 1,246 tokens on every turn** (measured
by asking the server itself: `tools/list`). For a small local model that is worth trimming — all
of these do the same job:

```bash
hermes tools disable termctl:info termctl:watch termctl:title --platform telegram
```

`info`, `watch` and `title` are covered by `brief` / `status` and `send --wait-for`; dropping them
saves ~185 tokens per turn at no cost in capability.

## How it works

- **One gateway to macOS.** Everything AppleScript goes through a single function (`osa()`), plus
  ~9 lines of AppleScript source scattered through the verbs. Out of 1,433 lines of Python that is
  the whole macOS-specific part.
- **State detection reads the screen, not a protocol.** "Working", "at a prompt" and "waiting for
  an answer" are inferred from what is actually rendered — which is why it also works with agents
  that were started by hand, long before the model was invoked.
- **`delta` keeps its own cursor** (`~/.local/state/termctl-state.json`), so an agent can follow a
  session without re-reading the same scrollback and burning context.
- **Keystrokes are written, not typed.** `Terminal.app`'s `do script` always appends a Return, so
  multi-key sequences are sent in a single write, and arrow keys follow the *foreground process's*
  terminfo (`kcud1 = ESC O B` for `xterm-256color`, not the CSI form).
- **No browser, no screenshotting, no OCR.** It is text on the terminal buffer.

## Platform

macOS today, but not by design of the protocol: the MCP surface and the verbs are system-agnostic,
and the macOS coupling is the single `osa()` gateway described above. The natural backend on Linux
is `tmux` (`list-panes`, `capture-pane -p`, `send-keys`), which maps almost verb-by-verb and fits
the premise even better — a tmux session is something a human attaches to and watches. On Windows
it would be ConPTY / Windows Terminal, where screen capture needs a different mechanism.

Porting means putting a backend layer (`applescript` | `tmux`) behind the verb functions: the
screen parsing, the state detection, the MCP server and the CLI are already portable.

## What it is worth (measured)

The tool was measured against the alternative a model actually has without it: hand-written
AppleScript through the shell. Same model, same tasks, same prompt, same base toolset — only the
interface changes. Measured with **`Inkling-2-Mini UD-Q4_K_XL`** (Unsloth GGUF, MoE with ~5.4B
active parameters per token) served locally by `llama.cpp` on Metal: an Apple M5 Pro with 48 GB,
~26 tok/s.

| Task | Without the tool | With the tool |
|---|---|---|
| **Identify which sessions are open** (find the right one) | 155.5 s · 133,099 tokens | **104.7 s · 83,339 tokens** (−33% time, −37% tokens) |
| **Follow a long-running output stream to completion** | never finished within the 420 s cap | **141.4 s · 124,077 tokens** |
| **Answer a menu inside a TUI** | the choice never landed (independent judge: FAIL) | **78.9–98.1 s · 109k–134k tokens**, choice verified |

- The machine load is **identical** with and without the tooling: the cost is the resident model
  (≈28 GB wired, GPU pegged, thermal state `fair`), not the interface.
- Where both routes worked, **answer quality was the same**. The difference is cost — and, in two
  of the three tasks, whether the task can be finished at all.
- The largest single win came from **instructions, not code**: telling the model to prefer the MCP
  tools and to *wait* instead of polling cut one task from 225,124 to 124,077 tokens (−45%).
- The weak link is **tool discovery by a small model**, not the tools: in one-shot CLI runs the
  model sometimes failed to find them and thrashed to a timeout. Naming them in the system prompt
  removed the problem.

### How it was measured

Three tasks, chosen because a human can tell at a glance whether they were done: **identify** (two
live Copilot CLI windows are open — report which is which, and whether each is working or waiting),
**stream** (a 60-step job printing a line every 2 s — follow it to the end), and **menu** (an
arrow-key TUI — pick the entry named `three`; the recorded runs used the Italian fixture, `tre`).

Model, prompt and base toolset are identical in both conditions; the only variable is whether
`termctl` exists at all. Where a verdict could be faked in prose, it is not read from the model's
answer: the fixture window records the choice itself, and the stream fixture prints a completion
marker.

Every run is kept — answers, token usage, machine load sampled every 2 s, verdicts — in
[`results/raw/`](results/raw), with the harnesses in [`bench/`](bench).

### Machine load (sampled every 2 s during every run)

| | Idle | With the tool | Without the tool |
|---|---|---|---|
| RAM wired | 3.8 GB | 27.9–28.7 GB | 28.1–28.7 GB |
| GPU memory in use | 1.2 GB | 25.4–26.2 GB | 25.6 GB |
| GPU utilisation | 39% | 100% | 100% |
| Compressed memory | 15.5 GB | 12.5–15.5 GB | 13.6–13.7 GB |
| Swap used | 4.2 GB | 5.3–6.5 GB | 5.5–6.5 GB |
| llama-server CPU | 0% | 56–67% | 60–70% |
| Load average (1 min) | 4.3 | 4.2–5.6 | 4.2–5.6 |
| Thermal state | nominal | nominal–fair | nominal–fair |

The interface adds no measurable RAM, GPU, thermal or CPU cost: **the price is keeping the model
resident**, and it is paid either way. Charted: [`docs/benchmark.html`](docs/benchmark.html).

### What the measurement changed in the tool

The exercise was not read-only: every finding turned into a change.

1. **A blocked single slot is invisible.** With `--parallel 1`, one stuck request — a leftover
   from a Metal "Insufficient Memory" error — blocks every later request, while `/health` still
   answers `ok`. The diagnosis is `GET /slots`: `is_processing=true` with no progress. The process
   then ignored `SIGTERM` and had to be killed with `-9`.
2. **`status` did not understand a TUI input box.** The control condition read the screen better
   than the tool did: an empty `❯` prompt after a "task complete" banner means the agent is idle
   and waiting for instructions. That case is now detected (`idle_prompt`, `state: waiting_for_input`).
3. **Skill and tools disagreed.** The skill taught the CLI while the MCP tools were also available;
   the model followed the skill and paid for it in tokens. Both now state the rule: *if the
   `mcp__termctl__*` tools exist, use those; the CLI is the fallback.*
4. **MCP calls left no trace.** The audit log (who called what, from which process) now records
   every MCP tool call, which is how the round-4 timeouts were diagnosed.

## Reproducing the measurement

Prerequisites: macOS with `Terminal.app`, the Automation permission granted to the process running
the agent, an OpenAI-compatible endpoint serving the model of your choice (the harness drives the
`hermes` CLI with `--provider`/`--model` pointing at it), and Python 3.9+ — standard library only.

```bash
install -m 755 termctl ~/.local/bin/termctl

python3 bench/bench4_true_baseline.py   # with/without: the tool absent, independent judge
python3 bench/final_report.py           # every round in one table
```

Configuration lives at the top of each script: paths to the agent CLI, the model name, the
provider alias, and the directory for results. The other harnesses in `bench/` are the runs the
"with the tool" timings for the stream and menu tasks come from.

## Repository layout

```
termctl                    the MCP server + CLI (one file, standard library only)
bench/                     the measurement: harnesses + aggregators
  bench4_true_baseline.py  with/without termctl, independent judge, load sampling
  bench_mcp_vs_cli.py      the MCP tools against the same tool through a shell
  bench2_guidance.py       the same comparison, after the instruction fix
  bench3_baseline.py       a control with a pruned PATH that proved invalid (kept as a record)
  report_bench.py          per-run table with load columns
  final_report.py          every round in one table
  fixtures/                the TUI menu and the byte-level keystroke probe
results/
  baseline.json            idle machine load
  raw/                     every raw record: usage, load samples, verdicts
docs/benchmark.html        the charts
```

## License

MIT — see [LICENSE](LICENSE).

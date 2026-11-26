#!/usr/bin/env python3
"""Probe: prints in hex every byte that arrives on stdin (raw mode).

Tells what `termctl key <id> down` / `ctrl-c` really deliver.
"""
import sys
import termios
import tty

fd = sys.stdin.fileno()
old = termios.tcgetattr(fd)
try:
    tty.setraw(fd)
    print("PROBE READY", flush=True)
    while True:
        b = sys.stdin.buffer.read(1)
        if not b:
            break
        if b == b"\x03":
            print("  <- ctrl-c received, exiting", flush=True)
            break
        print(f"  byte {b.hex()}", flush=True)
finally:
    termios.tcsetattr(fd, termios.TCSADRAIN, old)

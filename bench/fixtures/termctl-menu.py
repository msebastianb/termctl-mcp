#!/usr/bin/env python3
"""TUI menu (arrows + Enter) with a selection marker, to exercise status/choose."""
import curses
import os

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "menu-debug.log")
FRECCIA = "\u276f"


def main(scr):
    opts = ["one", "two", "three"]
    idx = 0
    ultima = "-"
    curses.curs_set(2)
    scr.keypad(True)
    with open(LOG, "w") as f:
        f.write("TERM=%r\n" % os.environ.get("TERM"))
    while True:
        scr.clear()
        scr.addstr("Choose an option:\n")
        for i, o in enumerate(opts):
            mark = FRECCIA if i == idx else " "
            scr.addstr(mark + " %d. %s\n" % (i + 1, o))
        scr.addstr("\u2191/\u2193 to navigate \u00b7 enter to select\n")
        scr.addstr("last choice: %s\n" % ultima)
        scr.refresh()
        k = scr.getch()
        with open(LOG, "a") as f:
            f.write("getch=%d\n" % k)
        if k == curses.KEY_DOWN:
            idx = min(idx + 1, len(opts) - 1)
        elif k == curses.KEY_UP:
            idx = max(idx - 1, 0)
        elif k in (10, 13):
            ultima = opts[idx]
            with open(LOG, "a") as f:
                f.write("chosen=%s\n" % ultima)


if __name__ == "__main__":
    curses.wrapper(main)

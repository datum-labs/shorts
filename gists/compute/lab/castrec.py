#!/usr/bin/env python3
"""Record a terminal session as an asciinema cast (asciicast v2) from a scene file, running every command for real.

Scene file lines:
  # text      shown as a typed shell comment (narration)
  $ command   typed at a human pace, then run with bash; its output streams into the cast with real timing
  (blank)     a short pause

`datumctl` inside commands is a shell function for the containerized CLI, the same thing typed at the terminal.
Anything matching REDACT is replaced in the output, so the cast never shows the recorder's home address.

Usage: castrec.py SCENE OUT.cast [--title T] [--cols 100] [--rows 30]
"""
import argparse, json, os, re, select, subprocess, sys, time

TYPING_SECONDS_PER_CHAR = float(os.environ.get("TYPING_SPC", "0.012"))
PAUSE_AFTER_TYPING = 0.25
PAUSE_AFTER_OUTPUT = float(os.environ.get("PAUSE_OUT", "0.6"))
PROMPT = "\x1b[1;32m$\x1b[0m "
COMMENT_STYLE = "\x1b[2;3m{}\x1b[0m"
REDACT = [(re.compile(r"192\.168\.\d+\.\d+"), "<lan-ip>"), (re.compile(r"fd7a:115c:[0-9a-f:]+"), "<ts-ip>")]  # add your own address and email here
ROOT = os.path.dirname(os.path.abspath(__file__))
# From the Istio short's castrec.py. Changed: `docker` runs on a throwaway GCP VM over SSH (nice 19 there), reached as
# docker-host; `datumctl` is ./d.sh, the containerized CLI at nice 19. Recordings run at low priority everywhere.
SHELL_SETUP = f". {ROOT}/env.sh\nexport -f podman datumctl curl\n"


class Cast:
    def __init__(self, path, cols, rows, title):
        self.file = open(path, "w")
        self.clock = 0.0
        header = {"version": 2, "width": cols, "height": rows, "timestamp": int(time.time()), "title": title,
                  "env": {"SHELL": "/bin/bash", "TERM": "xterm-256color"}}
        self.file.write(json.dumps(header) + "\n")

    def out(self, text, advance=0.0):
        self.clock += advance
        for pattern, replacement in REDACT:
            text = pattern.sub(replacement, text)
        self.file.write(json.dumps([round(self.clock, 3), "o", text]) + "\n")

    def type(self, text):
        for ch in text:
            self.out(ch, TYPING_SECONDS_PER_CHAR)


def run_streaming(cast, command):
    """Run one command and stream its output into the cast, keeping the real gaps between chunks."""
    proc = subprocess.Popen(["bash", "-c", SHELL_SETUP + command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    last = time.monotonic()
    seen = []
    while True:
        ready, _, _ = select.select([proc.stdout], [], [], 0.5)
        if ready:
            chunk = os.read(proc.stdout.fileno(), 4096)
            if not chunk:
                break
            now = time.monotonic()
            seen.append(chunk.decode(errors="replace"))
            cast.out(chunk.decode(errors="replace").replace("\n", "\r\n"), now - last)
            last = now
        elif proc.poll() is not None:
            break
    proc.wait()
    cast.clock += time.monotonic() - last
    return "".join(seen)


URL_RE = re.compile(r"https://[A-Za-z0-9.-]+\.datumproxy\.net")


def run_silent(command):
    """Run a setup/wait command: no typing, no output in the cast, no cast-clock advance. Returns its output."""
    proc = subprocess.run(["bash", "-c", SHELL_SETUP + command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
    return proc.stdout.decode(errors="replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene"); ap.add_argument("out")
    ap.add_argument("--title", default=""); ap.add_argument("--cols", type=int, default=100); ap.add_argument("--rows", type=int, default=24)
    args = ap.parse_args()
    cast = Cast(args.out, args.cols, args.rows, args.title)
    url = None
    lines = [l.rstrip("\n") for l in open(args.scene)]
    i = 0
    while i < len(lines):
        line = lines[i]; i += 1
        if not line.strip():
            cast.out("", PAUSE_AFTER_OUTPUT)
        elif line.startswith("# "):
            cast.out(PROMPT, 0.2); cast.type(COMMENT_STYLE.format(line)); cast.out("\r\n", PAUSE_AFTER_TYPING)
        elif line.startswith("~ "):
            command = line[2:]
            while command.endswith(" \\") and i < len(lines):
                command = command[:-2] + " " + lines[i].strip(); i += 1
            if url:
                command = command.replace("$URL", url)
            print(f"  silent: {command[:80]}", file=sys.stderr)
            found = URL_RE.search(run_silent(command))
            if found:
                url = found.group(0)
        elif line.startswith("$ "):
            shown = [line[2:]]
            while shown[-1].endswith(" \\") and i < len(lines):
                nxt = lines[i]; i += 1
                nxt = nxt[2:] if nxt.startswith("$ ") else nxt
                shown.append("  " + nxt.strip())
            if url:
                shown = [x.replace("$URL", url) for x in shown]
            typed = "\r\n".join(shown)
            command = " ".join(x[:-1].rstrip() if x.endswith("\\") else x for x in (y.strip() for y in shown))
            cast.out(PROMPT, 0.2); cast.type(typed); cast.out("\r\n", PAUSE_AFTER_TYPING)
            found = URL_RE.search(run_streaming(cast, command))
            if found:
                url = found.group(0)
            print(f"  ran: {command[:80]}", file=sys.stderr)
    cast.out(PROMPT, PAUSE_AFTER_OUTPUT)
    cast.out("", 2.0)


main()

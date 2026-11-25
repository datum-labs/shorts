#!/usr/bin/env python3
"""Build 13-three-cities.gif: GRAPH + LOGS + CODE panels on one timeline.

Data (all REAL, run 1) read from ./data/:
  anim/timeline.jsonl      instance status samples (t = seconds since deploy start)
  anim/requests.jsonl      40 sequential curl requests (t, http_code, hostname, ms)
  anim/logs.txt            instance startup log lines (UTC timestamps)
  anim/logs-access.txt     ALB access log lines (UTC timestamps), 41 = probe + 40
  20-deploy-3city.txt      deploy output (Rollout complete in 6s ...)
  21-3city-timing.txt      first-200 time (attempt 16, t=22.364 s) and deploy wall

Clock: UTC log timestamps are mapped to "seconds since deploy start" by anchoring the
first access-log line (the first-200 probe, 18:40:13.640) to the probe's measured
t=22.364 s.  Pillow frames are drawn at 2x and downsampled; ffmpeg builds the GIF.
Usage:  nice -n 19 python3 build_three_cities.py
"""
import json, re, subprocess, shutil
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
CAP = HERE / "data"
RUN = ""                      # "" = run 1 ; "-run2" would need its own anchors
FRAMES = HERE / "frames"
OUT_GIF = HERE / "13-three-cities.gif"
OUT_POSTER = HERE / "13-three-cities-poster.png"

W, H, S, FPS = 1000, 562, 2, 15
CREAM, NAVY, LIME, LIME_S = "#F6F5F1", "#0C1D31", "#E6F59B", "#7C8A2E"
GREY, GREY_F = "#8A8E99", "#E4E4E1"
AMBER, AMBER_S = "#F6DFA6", "#B3862A"
PANEL, PANEL_S = "#FFFFFF", "#D6D5CE"
MUTED = "#5A6372"
CITY = {"us-central-1": "DFW", "us-east-1": "IAD", "us-west-1": "SJC"}
CITY_NAME = {"us-central-1": "Dallas", "us-east-1": "Ashburn", "us-west-1": "San Jose"}
ORDER = ["us-central-1", "us-east-1", "us-west-1"]

COMMAND = ("datumctl compute deploy api --image=docker.io/traefik/whoami:v1.10.3 "
           "--city=DFW,IAD,SJC --http-port=80 --runtime-class=general-purpose --yes")
URL_GENERIC = "https://api-xxxxx.datumproxy.net"   # real host deliberately not shown

# ---------- load data ----------
def jl(p):
    out = []
    for l in open(p):
        try: out.append(json.loads(l))
        except Exception: pass
    return out

timeline = jl(CAP / f"timeline{RUN}.jsonl")
requests = jl(CAP / f"requests{RUN}.jsonl")
timing = (CAP / f"21-3city-timing{RUN}.txt").read_text()
deploy_wall = float(re.search(r"deploy_wall_s=([\d.]+)", timing).group(1))
first200 = float(re.search(r"t=([\d.]+) http=200", timing).group(1))
rollout = re.search(r"Rollout complete in (\d+)s", (CAP / f"20-deploy-3city{RUN}.txt").read_text()).group(0)

def tod(s):  # "Nov 25 18:40:13.640" -> seconds of day
    m = re.search(r"(\d\d):(\d\d):(\d\d\.\d+)", s)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))

access = [l.rstrip("\n") for l in open(CAP / f"logs-access{RUN}.txt") if l.strip()]
T0_UTC = tod(access[0]) - first200            # deploy start on the UTC clock

logs = []                                      # (real_t, text, kind)
for l in open(CAP / f"logs{RUN}.txt"):
    m = re.match(r"\[default-(us-[a-z]+-\d)-0/app\]\s+(.*?)\s+(\d\d:\d\d:\d\d\.\d+)\s+.*?(Starting up on port 80)", l)
    if m:
        ts = re.search(r"\d\d:\d\d:\d\d\.\d+", l).group(0)
        logs.append((tod(l) - T0_UTC, f"{CITY[m.group(1)]} {ts} {m.group(4)}", "app"))
for i, l in enumerate(access):
    m = re.match(r".*?(\d\d:\d\d:\d\d\.\d+)\s+(GET)\s+(\d+)\s+(\d+ms)\s+(/)", l)
    rt = first200 if i == 0 else requests[i - 1]["t"]   # line i>0 == request i-1
    logs.append((rt, f"ALB {m.group(1)} {m.group(2)} {m.group(3)} {m.group(4)} {m.group(5)}",
                 "probe" if i == 0 else "req"))
logs.sort(key=lambda x: x[0])
req_t = [r["t"] for r in requests]
req_ms = [r["ms"] for r in requests]

# per-location state transitions from the real samples
def state_at(loc, t):
    st = "Pending"
    for s in timeline:
        if s["t"] > t: break
        for i in s["instances"]:
            if i["location"] == loc:
                a = i["available"]
                st = "Available" if a == "Available" else ("Starting" if a == "Provisioning" else "Pending")
    return st

# ---------- animation clock: real seconds <-> animation seconds ----------
T0 = 2.6                                       # typing pre-roll
BP = [(0, T0), (12.5, T0 + 9.0), (21.5, T0 + 9.9), (22.6, T0 + 11.0),
      (27.3, T0 + 11.8), (req_t[-1] + 0.1, T0 + 11.8 + 3.3)]
SKIPS = [(1, 2, "9 s skipped · 15 curl tries, no 200 yet"),
         (3, 4, "5 s idle")]
HOLD = 3.0
END_A = BP[-1][1]

def to_real(a):
    if a <= T0: return -1.0
    for (r0, a0), (r1, a1) in zip(BP, BP[1:]):
        if a <= a1: return r0 + (r1 - r0) * (a - a0) / (a1 - a0)
    return BP[-1][0]

def to_anim(r):
    for (r0, a0), (r1, a1) in zip(BP, BP[1:]):
        if r <= r1: return a0 + (a1 - a0) * (r - r0) / (r1 - r0)
    return BP[-1][1]

# output lines in the terminal: (real_t when shown, text). Only the "created" line, the
# Rollout line and the URL line have anchors (deploy wall = 11.688); others are approximate.
OUTPUT = [(0.3, "workload/api created", NAVY),
          (7.5, rollout + ".", LIME),
          (11.4, "Backends  3 healthy across us-central-1, us-east-1, us-west-1", "#C9CED6"),
          (11.5, "Edge programmed · Certificate issued", "#C9CED6"),
          (deploy_wall, URL_GENERIC, LIME)]

# ---------- drawing helpers (2x supersampled) ----------
FD = HERE / "fonts"
_fc = {}
def font(name, size):
    k = (name, size)
    if k not in _fc:
        f = {"mono": "JetBrainsMono-Regular.ttf", "monob": "JetBrainsMono-Bold.ttf",
             "sans": "DejaVuSans.ttf", "sansb": "DejaVuSans-Bold.ttf"}[name]
        _fc[k] = ImageFont.truetype(str(FD / f), int(size * S))
    return _fc[k]

class Cv:
    def __init__(s):
        s.im = Image.new("RGB", (W * S, H * S), CREAM)
        s.d = ImageDraw.Draw(s.im)
    def rr(s, box, r, fill=None, outline=None, w=1):
        x0, y0, x1, y1 = [v * S for v in box]
        s.d.rounded_rectangle((x0, y0, x1, y1), r * S, fill=fill, outline=outline, width=int(w * S))
    def text(s, xy, t, f, size, fill=NAVY, anchor="la"):
        s.d.text((xy[0] * S, xy[1] * S), t, font=font(f, size), fill=fill, anchor=anchor)
    def tw(s, t, f, size):
        return s.d.textlength(t, font=font(f, size)) / S
    def line(s, pts, fill, w=2):
        s.d.line([(x * S, y * S) for x, y in pts], fill=fill, width=int(w * S), joint="curve")
    def dash(s, pts, fill, w=2, on=6, off=5):
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            L = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** .5
            n = int(L // (on + off)) + 1
            for k in range(n):
                a, b = k * (on + off), min(k * (on + off) + on, L)
                if a >= L: break
                s.line([(x0 + (x1 - x0) * a / L, y0 + (y1 - y0) * a / L),
                        (x0 + (x1 - x0) * b / L, y0 + (y1 - y0) * b / L)], fill, w)
    def circle(s, c, r, fill, outline=None, w=1):
        s.d.ellipse(((c[0] - r) * S, (c[1] - r) * S, (c[0] + r) * S, (c[1] + r) * S),
                    fill=fill, outline=outline, width=int(w * S))
    def out(s):
        return s.im.resize((W, H), Image.LANCZOS)

# geometry (1x px)
GX0, GX1, PY0, PY1 = 12, 492, 12, 352
LX0, LX1 = 504, 988
CY0, CY1 = 364, 550
URL_BOX = (87, 66, 417, 106)
TILE_CX = {"us-central-1": 90, "us-east-1": 252, "us-west-1": 414}
TILE_Y0, TILE = 174, 64
YMID = 138

def edge_pts(loc):
    cx = TILE_CX[loc]
    return [(252, URL_BOX[3]), (252, YMID), (cx, YMID), (cx, TILE_Y0)]

def along(pts, p):
    segs = [((x1 - x0) ** 2 + (y1 - y0) ** 2) ** .5 for (x0, y0), (x1, y1) in zip(pts, pts[1:])]
    d = p * sum(segs)
    for (a, b), L in zip(zip(pts, pts[1:]), segs):
        if d <= L and L > 0:
            return (a[0] + (b[0] - a[0]) * d / L, a[1] + (b[1] - a[1]) * d / L)
        d -= L
    return pts[-1]

def tile_icon(c, cx, y0, col):
    # small "instance" glyph: three squares, echoing the house icon
    x, y = cx - 14, y0 + 18
    c.rr((x, y, x + 28, y + 28), 3, outline=col, w=3)
    c.rr((x + 7, y + 8, x + 15, y + 16), 1, outline=col, w=2)
    c.rr((x + 15, y + 2, x + 23, y + 10), 1, outline=col, w=2)

def panel(c, box, title, right=None):
    c.rr(box, 10, fill=PANEL, outline=PANEL_S, w=1.5)
    c.text((box[0] + 14, box[1] + 11), title, "sansb", 15)

def frame(a):
    r = to_real(a)
    c = Cv()
    # ================= GRAPH =================
    panel(c, (GX0, PY0, GX1, PY1), "Workload api · 3 locations")
    clock = "t = %4.1f s" % max(r, 0)
    c.text((GX1 - 14, PY0 + 12), clock, "mono", 14, MUTED, "ra")
    url_live = r >= deploy_wall
    c.rr(URL_BOX, 10, fill=NAVY if url_live else GREY_F, outline=NAVY if url_live else GREY, w=1.5)
    c.text((252, 86), URL_GENERIC, "sans", 15, CREAM if url_live else MUTED, "mm")
    srv = {loc: 0 for loc in ORDER}
    srv["us-west-1"] = sum(1 for t in req_t if t <= r)    # every real request hit SJC
    states = {loc: state_at(loc, r) for loc in ORDER}
    n_av = sum(1 for v in states.values() if v == "Available")
    for loc in ORDER:                       # edges
        pts = edge_pts(loc)
        if states[loc] == "Available" and url_live: c.line(pts, NAVY, 2)
        else: c.dash(pts, GREY, 2)
    # request pulses along the SJC edge
    flash = 0.0
    for t in req_t:
        p = (a - to_anim(t)) / 0.30
        if 0 <= p <= 1:
            x, y = along(edge_pts("us-west-1"), p)
            c.circle((x, y), 5.5, LIME, NAVY, 1.5)
        if 0.30 <= (a - to_anim(t)) <= 0.45: flash = 1.0
    for loc in ORDER:                       # tiles
        cx, st = TILE_CX[loc], states[loc]
        fill, stroke = {"Pending": (GREY_F, GREY), "Starting": (AMBER, AMBER_S),
                        "Available": (LIME, LIME_S)}[st]
        w = 2
        if loc == "us-west-1" and flash: w, stroke = 4.5, NAVY
        c.rr((cx - TILE // 2, TILE_Y0, cx + TILE // 2, TILE_Y0 + TILE), 12, fill=fill, outline=stroke, w=w)
        tile_icon(c, cx, TILE_Y0, NAVY if st != "Pending" else GREY)
        c.text((cx, TILE_Y0 + TILE + 20), CITY_NAME[loc], "sansb", 16, NAVY, "mm")
        c.text((cx, TILE_Y0 + TILE + 42), st, "sans", 14, {"Pending": MUTED, "Starting": "#8A6A1C",
                                                           "Available": "#55621B"}[st], "mm")
        c.text((cx, TILE_Y0 + TILE + 62), "requests %d" % srv[loc], "mono", 14,
               NAVY if srv[loc] else MUTED, "mm")
    # skip marker
    for i0, i1, label in SKIPS:
        a0, a1 = BP[i0][1], BP[i1][1]
        if a0 <= a <= a1 + 0.3:
            tw_ = c.tw("⋯ " + label, "sansb", 14) + 24
            c.rr((252 - tw_ / 2, 322, 252 + tw_ / 2, 344), 12, fill=AMBER, outline=AMBER_S, w=1.5)
            c.text((252, 333), "⋯ " + label, "sansb", 14, NAVY, "mm")
    # ================= LOGS =================
    panel(c, (LX0, PY0, LX1, PY1), "Logs · startup + ALB access")
    shown = [l for l in logs if l[0] <= r]
    rows = shown[-9:]
    for k, (lt, txt, kind) in enumerate(rows):
        y = 44 + k * 21
        newest = (k == len(rows) - 1)
        if newest: c.rr((LX0 + 8, y - 2, LX1 - 8, y + 19), 4, fill=LIME)
        tag, rest = txt.split(" ", 1)
        c.text((LX0 + 14, y), tag, "monob", 14, NAVY if kind != "app" else "#55621B")
        c.text((LX0 + 14 + 4 * 8.4 + 0.5, y), rest, "mono", 14, NAVY if newest or kind == "probe" else MUTED)
        if kind == "probe":
            c.text((LX1 - 14, y), "first 200", "monob", 14, "#55621B", "ra")
    # sparkline
    sx0, sx1, sy0, sy1 = LX0 + 16, LX1 - 16, 272, 332
    c.line([(LX0 + 8, 244), (LX1 - 8, 244)], PANEL_S, 1)
    n = sum(1 for t in req_t if t <= r)
    c.text((LX0 + 14, 250), "Request latency (ms)", "sansb", 14)
    c.text((LX1 - 14, 250), "%d / 40  ·  %d-%d ms" % (n, min(req_ms), max(req_ms)), "mono", 14, MUTED, "ra")
    lo, hi = 40, 80
    c.line([(sx0, sy1), (sx1, sy1)], PANEL_S, 1)
    pts = []
    for i in range(n):
        x = sx0 + (sx1 - sx0) * i / 39
        y = sy1 - (sy1 - sy0) * (min(req_ms[i], hi) - lo) / (hi - lo)
        pts.append((x, y))
    if len(pts) > 1: c.line(pts, NAVY, 2)
    if pts: c.circle(pts[-1], 4, LIME, NAVY, 1.5)
    # ================= CODE =================
    c.rr((GX0, CY0, LX1, CY1), 10, fill=NAVY)
    c.text((GX0 + 14, CY0 + 9), "Terminal", "sansb", 14, "#9FA8B5")
    cmd_lines = ["$ datumctl compute deploy api --image=docker.io/traefik/whoami:v1.10.3 --city=DFW,IAD,SJC",
                 "    --http-port=80 --runtime-class=general-purpose --yes"]
    full = "\n".join(cmd_lines)
    typed = len(full) if a >= T0 - 0.3 else int(len(full) * max(0, a - 0.3) / (T0 - 0.8))
    typed = min(typed, len(full))
    shown_cmd = full[:typed].split("\n")
    y = CY0 + 32
    for k, ln in enumerate(shown_cmd):
        c.text((GX0 + 14, y + k * 21), ln, "mono", 14, "#F6F5F1")
    if a < T0 + 0.6 and int(a * 3) % 2 == 0 or typed < len(full):
        k = len(shown_cmd) - 1
        c.rr((GX0 + 14 + 8.4 * len(shown_cmd[k]) + 1, y + k * 21 + 1,
              GX0 + 14 + 8.4 * len(shown_cmd[k]) + 9, y + k * 21 + 19), 1, fill=LIME)
    oy = y + 2 * 21 + 6
    for (rt, txt, col) in OUTPUT:
        if r >= rt:
            c.text((GX0 + 14, oy), txt, "mono", 14, "#F6F5F1" if col == NAVY else col)
            oy += 21
    # counter strip + chips (right side)
    cx0 = 640
    chip = lambda y0, label, on, w: (
        c.rr((cx0, y0, cx0 + w, y0 + 30), 15, fill=LIME if on else "#1E3048",
             outline=None if on else "#3A4B63"),
        c.text((cx0 + w / 2, y0 + 15), label, "sansb", 16, NAVY if on else "#9FA8B5", "mm"))
    chip(CY0 + 56, "Available %d/3" % n_av, n_av == 3, 190)
    # progress ticks 1/3 · 2/3 · 3/3
    for i in range(3):
        c.circle((cx0 + 214 + i * 24, CY0 + 71), 8, LIME if n_av > i else "#1E3048",
                 None if n_av > i else "#3A4B63", 1.5)
    if r >= first200:
        chip(CY0 + 94, "first 200 · %d s" % round(first200), True, 190)
        c.text((cx0 + 206, CY0 + 109), "run 1", "mono", 14, "#9FA8B5", "lm")
    if r >= 0 and r >= 7.5:
        c.text((cx0, CY0 + 140), "rollout reported 6 s", "mono", 14, "#C9CED6")
    if n >= 40:
        c.text((cx0, CY0 + 160), "40/40 answered by SJC", "monob", 14, LIME)
    return c.out()

def main():
    shutil.rmtree(FRAMES, ignore_errors=True); FRAMES.mkdir()
    total = END_A + HOLD
    n = int(total * FPS)
    for i in range(n):
        a = min(i / FPS, END_A + 0.0) if i / FPS < END_A else END_A
        frame(a if i / FPS < END_A else END_A).save(FRAMES / f"f{i:04d}.png")
    last = frame(END_A)
    last.save(OUT_POSTER)
    pal = FRAMES / "pal.png"
    nice = ["nice", "-n", "19"]
    subprocess.run(nice + ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i",
                           str(FRAMES / "f%04d.png"), "-vf", "palettegen=max_colors=128:stats_mode=diff",
                           str(pal)], check=True)
    subprocess.run(nice + ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i",
                           str(FRAMES / "f%04d.png"), "-i", str(pal), "-lavfi",
                           "paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
                           "-loop", "0", str(OUT_GIF)], check=True)
    print(n, "frames,", n / FPS, "s,", OUT_GIF.stat().st_size // 1024, "KB")

if __name__ == "__main__":
    main()

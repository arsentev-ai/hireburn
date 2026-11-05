#!/usr/bin/env python3
"""Render assets/readme/demo.gif: a terminal session on the synthetic example company.

Needs rsvg-convert and ffmpeg. Runs the real CLI, so the GIF always shows real output.
    python3 scripts/make_demo_gif.py
"""
import html
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EX = ROOT / "examples" / "example-company"
COLS, ROWS, FS, LH, CW = 104, 30, 15, 20, 9.0
W, H = int(COLS * CW + 48), ROWS * LH + 76

SESSION = [
    ("hireburn funnel funnel.csv", ["funnel", "funnel.csv"]),
    ("hireburn labels candidates.csv --day 30", ["labels", "candidates.csv", "--day", "30"]),
    ("hireburn outreach draft outreach.csv --templates templates.yaml -o /tmp/drafts.json",
     ["outreach", "draft", "outreach.csv", "--templates", "templates.yaml", "-o", "{tmp}/drafts.json"]),
    ("hireburn outreach plan /tmp/drafts.json --start 2026-01-05T09:00 --seed 7",
     ["outreach", "plan", "{tmp}/drafts.json", "--start", "2026-01-05T09:00", "--seed", "7"]),
]


def run(args, tmp):
    args = [a.replace("{tmp}", tmp) for a in args]
    r = subprocess.run([sys.executable, "-m", "hireburn", *args], cwd=EX, capture_output=True, text=True,
                       env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"})
    return [ln for ln in r.stdout.splitlines()]


def color(line):
    if line.startswith("$ "):
        return "#FF6A1A"
    if line.startswith("#"):
        return "#F2EFE8"
    if "⚠" in line:
        return "#E8B04A"
    if line.startswith("|"):
        return "#C9CDD3"
    return "#8A8F98"


def frame_svg(lines):
    shown = lines[-ROWS:]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">',
           f'<rect width="{W}" height="{H}" rx="14" fill="#0B0C0E"/>',
           '<circle cx="26" cy="22" r="6" fill="#3A3D43"/><circle cx="46" cy="22" r="6" fill="#3A3D43"/>'
           '<circle cx="66" cy="22" r="6" fill="#3A3D43"/>',
           f'<text x="{W/2}" y="27" text-anchor="middle" fill="#5A5F68" font-family="DejaVu Sans Mono, monospace" '
           f'font-size="13">hireburn · synthetic example company</text>']
    for i, ln in enumerate(shown):
        t = ln if len(ln) <= COLS else ln[: COLS - 1] + "…"
        out.append(f'<text x="24" y="{62 + i * LH}" fill="{color(ln)}" font-family="DejaVu Sans Mono, monospace" '
                   f'font-size="{FS}" xml:space="preserve">{html.escape(t)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def main():
    for tool in ("rsvg-convert", "ffmpeg"):
        if not shutil.which(tool):
            sys.exit(f"{tool} not found")
    with tempfile.TemporaryDirectory() as tmp:
        frames = []  # (lines, seconds)
        screen = []
        for shown, args in SESSION:
            prompt = "$ "
            for k in range(0, len(shown) + 1, 3):
                frames.append((screen + [prompt + shown[:k] + "▌"], 0.04))
            frames.append((screen + [prompt + shown], 0.4))
            screen = screen + [prompt + shown]
            out = run(args, tmp)
            for k in range(0, len(out), 3):
                frames.append((screen + out[: k + 3], 0.07))
            screen = screen + out + [""]
            frames.append((screen, 2.6))
        d = Path(tmp)
        concat = []
        for n, (lines, sec) in enumerate(frames):
            svg, png = d / f"f{n:04d}.svg", d / f"f{n:04d}.png"
            svg.write_text(frame_svg(lines), encoding="utf-8")
            subprocess.run(["rsvg-convert", "-o", str(png), str(svg)], check=True)
            concat.append(f"file '{png}'\nduration {sec}")
        concat.append(f"file '{d / f'f{len(frames) - 1:04d}.png'}'")
        (d / "list.txt").write_text("\n".join(concat) + "\n")
        out = ROOT / "assets" / "readme" / "demo.gif"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(d / "list.txt"),
                        "-fps_mode", "vfr", "-vf", "split[a][b];[a]palettegen=max_colors=24[p];[b][p]paletteuse=dither=none:diff_mode=rectangle",
                        "-loop", "0", str(out)], check=True)
        print(f"wrote {out} ({out.stat().st_size // 1024} KB, {len(frames)} frames)")


if __name__ == "__main__":
    main()

"""Renderiza una salida de terminal (archivo .txt) como imagen PNG estilo consola.

Uso:
    python render_terminal.py --in salidas/01-nodo.txt --out capturas/01-nodo.png --title "PowerShell"
    python render_terminal.py --all salidas capturas          # convierte todos los .txt
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\CascadiaMono.ttf",
    r"C:\Windows\Fonts\consola.ttf",
    r"C:\Windows\Fonts\cour.ttf",
]
FONT_SIZE = 17
LINE_H = 24
PAD_X = 22
PAD_Y = 16
BAR_H = 38
MAX_COLS = 112

BG = (12, 12, 12)
BAR = (50, 50, 51)
FG = (225, 225, 225)
PROMPT = (95, 211, 252)
COMMENT = (156, 220, 254)
OK = (78, 201, 176)
ERR = (255, 107, 107)
WARN = (255, 189, 46)
DIM = (150, 150, 150)


def pick_font() -> ImageFont.FreeTypeFont:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return ImageFont.truetype(p, FONT_SIZE)
    return ImageFont.load_default()


def color_for(line: str) -> tuple[int, int, int]:
    s = line.strip()
    if line.startswith("$ ") or line.startswith("PS "):
        return FG
    if s.startswith("#"):
        return COMMENT
    low = s.lower()
    if any(w in low for w in ("error", "failed", "crashloop", "notready", "refused")):
        return ERR
    if any(w in low for w in ("running", " ready", "successfully rolled out", "deployment.apps/", "created", "deleted", "scaled", "rolled back", "configured")):
        return OK
    if any(w in low for w in ("terminating", "pending", "containercreating", "waiting")):
        return WARN
    return FG


def wrap(line: str, cols: int) -> list[str]:
    if len(line) <= cols:
        return [line]
    out, cur = [], line
    while len(cur) > cols:
        cut = cur.rfind(" ", int(cols * 0.6), cols)
        if cut <= 0:
            cut = cols
        out.append(cur[:cut].rstrip())
        cur = "    " + cur[cut:].lstrip()
    out.append(cur)
    return out


def render(text: str, out: Path, title: str) -> None:
    font = pick_font()
    raw_lines = text.rstrip("\n").split("\n")
    lines: list[tuple[str, tuple[int, int, int]]] = []
    for ln in raw_lines:
        c = color_for(ln)
        for piece in wrap(ln.rstrip(), MAX_COLS):
            lines.append((piece, c))

    char_w = font.getlength("M")
    longest = max((len(l) for l, _ in lines), default=40)
    width = int(PAD_X * 2 + char_w * max(60, min(longest, MAX_COLS)))
    height = BAR_H + PAD_Y * 2 + LINE_H * len(lines)

    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, width, BAR_H], fill=BAR)
    for i, col in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        x = 16 + i * 22
        d.ellipse([x, 12, x + 14, 26], fill=col)
    d.text((90, 10), title, fill=(210, 210, 210), font=font)

    y = BAR_H + PAD_Y
    for ln, col in lines:
        if ln.startswith("$ ") or ln.startswith("PS "):
            prefix, rest = (ln[:2], ln[2:]) if ln.startswith("$ ") else (ln.split(">", 1)[0] + ">", ln.split(">", 1)[1] if ">" in ln else "")
            d.text((PAD_X, y), prefix, fill=PROMPT, font=font)
            d.text((PAD_X + font.getlength(prefix), y), rest, fill=FG, font=font)
        else:
            d.text((PAD_X, y), ln, fill=col, font=font)
        y += LINE_H

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(f"ok: {out} ({width}x{height})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp")
    ap.add_argument("--out")
    ap.add_argument("--title", default="Terminal (bash) - riesgo-credito-mlops")
    ap.add_argument("--all", nargs=2, metavar=("SRC_DIR", "DST_DIR"))
    a = ap.parse_args()

    if a.all:
        src, dst = Path(a.all[0]), Path(a.all[1])
        for f in sorted(src.glob("*.txt")):
            render(f.read_text(encoding="utf-8"), dst / (f.stem + ".png"), a.title)
        return 0
    if not (a.inp and a.out):
        ap.error("se requiere --in y --out, o --all SRC DST")
    render(Path(a.inp).read_text(encoding="utf-8"), Path(a.out), a.title)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Renderiza una salida de terminal (archivo .txt guardado por cap.sh) como imagen PNG que reproduce
la ventana de Git Bash (MINGW64) en Windows 11, que es el terminal donde se ejecutaron los comandos.

Cada linea "$ comando" del .txt se dibuja con el prompt real de Git Bash
(usuario@equipo MINGW64 /ruta (rama)) y debajo el comando; el resto es la salida tal cual se guardo.

Uso:
    python render_terminal.py --in salidas/01-x.txt --out capturas/01-x.png
    python render_terminal.py --all docs/evidencia/salidas docs/evidencia/capturas
"""
from __future__ import annotations

import argparse
import os
import socket
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
PAD_Y = 14
BAR_H = 36
MAX_COLS = 112

RAIZ = Path(__file__).resolve().parent.parent.parent
RUTA_MINGW = "/" + str(RAIZ).replace("\\", "/").replace(":", "", 1).lower()[:1] + str(RAIZ).replace("\\", "/")[2:]
USUARIO = os.environ.get("USERNAME", "usuario")
EQUIPO = socket.gethostname()
RAMA = "main"

BG = (12, 12, 12)
BAR = (32, 32, 32)
BAR_TEXT = (220, 220, 220)
FG = (225, 225, 225)
P_USER = (85, 214, 85)      # verde: usuario@equipo
P_MINGW = (214, 85, 214)    # magenta: MINGW64
P_RUTA = (230, 210, 60)     # amarillo: ruta
P_RAMA = (90, 215, 230)     # cian: (main)
COMMENT = (156, 220, 254)
OK = (78, 201, 176)
ERR = (255, 107, 107)
WARN = (255, 189, 46)


def pick_font() -> ImageFont.FreeTypeFont:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return ImageFont.truetype(p, FONT_SIZE)
    return ImageFont.load_default()


def color_for(line: str) -> tuple[int, int, int]:
    s = line.strip()
    if s.startswith("#"):
        return COMMENT
    low = s.lower()
    if any(w in low for w in ("error", "failed", "crashloop", "notready", "refused", "rechazado", "rojo")):
        return ERR
    if any(w in low for w in ("running", " ready", "successfully rolled out", "deployment.apps/", "created", "deleted",
                              "scaled", "rolled back", "configured", "passed", "aprobado", "verde", "ok:")):
        return OK
    if any(w in low for w in ("terminating", "pending", "containercreating", "waiting", "amarillo")):
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


def render(text: str, out: Path, title: str | None = None) -> None:
    font = pick_font()
    title = title or f"MINGW64:{RUTA_MINGW}"
    prompt_partes = [(f"{USUARIO}@{EQUIPO} ", P_USER), ("MINGW64 ", P_MINGW), (RUTA_MINGW + " ", P_RUTA), (f"({RAMA})", P_RAMA)]

    # Construir las lineas a dibujar: ("prompt", None) | ("cmd", texto) | ("out", texto, color)
    lineas: list[tuple] = []
    for ln in text.rstrip("\n").split("\n"):
        if ln.startswith("$ "):
            lineas.append(("prompt",))
            for k, piece in enumerate(wrap(ln[2:].rstrip(), MAX_COLS - 2)):
                lineas.append(("cmd", ("$ " if k == 0 else "  ") + piece))
        else:
            c = color_for(ln)
            for piece in wrap(ln.rstrip(), MAX_COLS):
                lineas.append(("out", piece, c))

    char_w = font.getlength("M")
    longest = max([len(l[1]) for l in lineas if l[0] != "prompt"], default=60)
    ancho_prompt = sum(len(p) for p, _ in prompt_partes) + 1      # el prompt entero siempre entra
    width = int(PAD_X * 2 + char_w * max(70, min(longest, MAX_COLS), ancho_prompt))
    height = BAR_H + PAD_Y * 2 + LINE_H * (len(lineas) + 1)

    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)

    # Barra de titulo estilo Windows 11: icono, titulo a la izquierda y los controles a la derecha
    d.rectangle([0, 0, width, BAR_H], fill=BAR)
    d.rectangle([12, 10, 28, 26], outline=(200, 200, 200), width=1)
    d.text((16, 9), ">", fill=(200, 200, 200), font=font)
    d.text((40, 8), title, fill=BAR_TEXT, font=font)
    controles = ["—", "☐", "×"]
    x = width - 44 * 3 - 10
    for c in controles:
        d.text((x + 14, 7), c, fill=BAR_TEXT, font=font)
        x += 44

    y = BAR_H + PAD_Y
    for l in lineas:
        if l[0] == "prompt":
            x = PAD_X
            for texto, col in prompt_partes:
                d.text((x, y), texto, fill=col, font=font)
                x += font.getlength(texto)
        elif l[0] == "cmd":
            d.text((PAD_X, y), l[1], fill=FG, font=font)
        else:
            d.text((PAD_X, y), l[1], fill=l[2], font=font)
        y += LINE_H
    # prompt final vacio, como queda la terminal al terminar
    x = PAD_X
    for texto, col in prompt_partes:
        d.text((x, y), texto, fill=col, font=font)
        x += font.getlength(texto)

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(f"ok: {out} ({width}x{height})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp")
    ap.add_argument("--out")
    ap.add_argument("--title", default=None)
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

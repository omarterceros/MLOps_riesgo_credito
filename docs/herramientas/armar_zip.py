"""Arma el zip de entrega (riesgo-credito-mlops_entrega.zip, en la raiz del repositorio) con la
misma estructura de carpetas que el repositorio, para que los enlaces relativos del README y de
ARQUITECTURA.md (docs/diagramas/..., docs/postman/..., docs/evidencia/...) funcionen al abrirlo.

Contenido: README.md, ARQUITECTURA.md, docs/Informe_ProyectoFinal_MLOps.docx, docs/diagramas/,
docs/evidencia/ y docs/postman/.

Uso (desde cualquier carpeta):  python docs/herramientas/armar_zip.py
"""
from __future__ import annotations

import os
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
SALIDA = RAIZ / "riesgo-credito-mlops_entrega.zip"
ARCHIVOS = ["README.md", "ARQUITECTURA.md", "docs/Informe_ProyectoFinal_MLOps.docx"]
CARPETAS = ["docs/diagramas", "docs/evidencia", "docs/postman"]


def main() -> int:
    n = 0
    with zipfile.ZipFile(SALIDA, "w", zipfile.ZIP_DEFLATED) as z:
        for a in ARCHIVOS:
            z.write(RAIZ / a, a)
            n += 1
        for c in CARPETAS:
            for ruta in sorted((RAIZ / c).rglob("*")):
                if ruta.is_file():
                    z.write(ruta, ruta.relative_to(RAIZ).as_posix())
                    n += 1
    print(f"ok: {SALIDA} ({n} archivos, {os.path.getsize(SALIDA) / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

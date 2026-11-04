"""Descarga el dataset publico y lo guarda como datos/credito.csv.

Uso: python datos/descargar.py

Fuente: OpenML id 42477, "default-of-credit-card-clients" (UCI). Las columnas
X1..X23 se renombran con los nombres del repositorio UCI (ver comun/esquema.py)
y la variable objetivo pasa a llamarse `mora`.
"""
import hashlib
import sys
from pathlib import Path

import pandas as pd
from sklearn.datasets import fetch_openml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from comun.esquema import FEATURES, OBJETIVO  # noqa: E402

ARCHIVO = Path(__file__).resolve().parent / "credito.csv"


def md5(ruta: Path) -> str:
    return hashlib.md5(ruta.read_bytes()).hexdigest()


def main() -> None:
    print("Descargando OpenML id 42477 (default-of-credit-card-clients)...")
    datos = fetch_openml(data_id=42477, as_frame=True, parser="liac-arff")
    X = datos.data.copy()
    y = datos.target

    if list(X.columns)[:3] != FEATURES[:3]:            # OpenML los llama x1..x23
        X.columns = FEATURES
    X = X.astype("int64")
    X[OBJETIVO] = pd.to_numeric(y.astype(str)).astype("int64")   # viene como categoria "0"/"1"

    ARCHIVO.parent.mkdir(exist_ok=True)
    X.to_csv(ARCHIVO, index=False)
    print(f"OK: {len(X)} filas x {X.shape[1]} columnas -> {ARCHIVO}")
    print(f"Tasa de mora: {X[OBJETIVO].mean():.4f}")
    print(f"MD5: {md5(ARCHIVO)}")


if __name__ == "__main__":
    main()

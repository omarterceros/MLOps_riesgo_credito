"""Convierte el CSV de Kaggle al esquema del proyecto y lo guarda como datos/credito.csv.

Dataset: "Default of Credit Card Clients Dataset" (Yeh y Lien, 2009; UCI Machine Learning
Repository id 350), publicado en Kaggle por UCI Machine Learning:
    https://www.kaggle.com/datasets/uciml/default-of-credit-card-clients-dataset

Como obtenerlo (hace falta una cuenta de Kaggle):
    a) Desde la web: boton Download -> descomprimir -> UCI_Credit_Card.csv
    b) Con la CLI de Kaggle (pip install kaggle y el token kaggle.json configurado):
       kaggle datasets download -d uciml/default-of-credit-card-clients-dataset --unzip -p datos

Uso: python datos/descargar.py [ruta_al_csv]        (por defecto datos/UCI_Credit_Card.csv)

El archivo de Kaggle trae una columna ID y el objetivo `default.payment.next.month`; aqui se
quita el ID, se renombra el objetivo a `mora` y se dejan las 23 variables con los nombres del
UCI (comun/esquema.py). El resultado, datos/credito.csv, esta versionado en el repositorio y su
MD5 se guarda como tag de cada run de MLflow.
"""
import argparse
import hashlib
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from comun.esquema import FEATURES, OBJETIVO  # noqa: E402

CARPETA = Path(__file__).resolve().parent
ARCHIVO = CARPETA / "credito.csv"
ARCHIVO_KAGGLE = CARPETA / "UCI_Credit_Card.csv"
URL_KAGGLE = "https://www.kaggle.com/datasets/uciml/default-of-credit-card-clients-dataset"
NOMBRES_OBJETIVO = ["default.payment.next.month", "default payment next month", "default", OBJETIVO]


def md5(ruta: Path) -> str:
    return hashlib.md5(ruta.read_bytes()).hexdigest()


def convertir(ruta: Path) -> pd.DataFrame:
    """Quita ID, renombra el objetivo y ordena las columnas segun comun/esquema.py."""
    d = pd.read_csv(ruta)
    d.columns = [c.strip() for c in d.columns]
    objetivo = next((c for c in NOMBRES_OBJETIVO if c in d.columns), None)
    if objetivo is None:
        sys.exit(f"no encuentro la columna objetivo; esperaba alguna de {NOMBRES_OBJETIVO}")
    faltan = [c for c in FEATURES if c not in d.columns]
    if faltan:
        sys.exit(f"faltan columnas: {faltan}")
    X = d[FEATURES].astype("int64")
    X[OBJETIVO] = d[objetivo].astype("int64")
    return X


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="?", default=str(ARCHIVO_KAGGLE), help="CSV descargado de Kaggle")
    a = ap.parse_args()

    origen = Path(a.csv)
    if not origen.exists():
        sys.exit(f"No encuentro {origen}.\nDescargalo de {URL_KAGGLE} (UCI_Credit_Card.csv) o con:\n"
                 f"  kaggle datasets download -d uciml/default-of-credit-card-clients-dataset --unzip -p datos")
    print(f"Leyendo {origen}...")
    X = convertir(origen)
    X.to_csv(ARCHIVO, index=False)
    print(f"OK: {len(X)} filas x {X.shape[1]} columnas -> {ARCHIVO}")
    print(f"Tasa de mora: {X[OBJETIVO].mean():.4f}")
    print(f"MD5: {md5(ARCHIVO)}")


if __name__ == "__main__":
    main()

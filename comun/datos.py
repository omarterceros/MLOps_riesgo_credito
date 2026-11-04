"""Carga del dataset y particion train/test reproducible.

La MISMA particion la usan el entrenamiento (para entrenar y medir), el monitoreo
(el conjunto de entrenamiento es el baseline del data drift; el de prueba es la
fuente de los lotes "nuevos") y las pruebas automatizadas.
"""
import hashlib
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from comun.esquema import FEATURES, OBJETIVO, SEMILLA, TEST_SIZE

ARCHIVO_DATOS = Path(__file__).resolve().parent.parent / "datos" / "credito.csv"


def md5_datos(ruta: Path = ARCHIVO_DATOS) -> str:
    """Huella del archivo de datos: se guarda como tag del run (trazabilidad datos <-> modelo)."""
    return hashlib.md5(Path(ruta).read_bytes()).hexdigest()


def cargar_datos(ruta: Path = ARCHIVO_DATOS) -> pd.DataFrame:
    datos = pd.read_csv(ruta)
    faltan = [c for c in FEATURES + [OBJETIVO] if c not in datos.columns]
    if faltan:
        raise ValueError(f"al archivo de datos le faltan columnas: {faltan}")
    return datos


def particion(datos: pd.DataFrame | None = None):
    """Division 80/20 estratificada por la variable objetivo, con semilla fija (42).

    Devuelve X_train, X_test, y_train, y_test. Siempre la misma particion.
    """
    if datos is None:
        datos = cargar_datos()
    X = datos[FEATURES]
    y = datos[OBJETIVO]
    return train_test_split(X, y, test_size=TEST_SIZE, random_state=SEMILLA, stratify=y)

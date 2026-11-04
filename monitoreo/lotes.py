"""Genera los lotes "nuevos" con los que se prueban los detectores de drift.

Uso: python monitoreo/lotes.py            -> escribe monitoreo/lotes/*.csv

- lote_normal.csv   : 1.500 clientes tomados al azar del conjunto de prueba. Mismo
                      origen que el entrenamiento -> el detector debe dar VERDE.
- lote_derivado.csv : los mismos 1.500 clientes con drift inyectado a proposito
                      (ver inyectar_drift) -> el detector debe dar ROJO.
Los dos conservan la columna `mora` para poder medir tambien el concept drift.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from comun.datos import particion  # noqa: E402
from comun.esquema import OBJETIVO  # noqa: E402

CARPETA = RAIZ / "monitoreo" / "lotes"
N_LOTE = 1500
SEMILLA_LOTE = 7


def lote_mismo_origen(n: int = N_LOTE, semilla: int = SEMILLA_LOTE) -> pd.DataFrame:
    _, X_test, _, y_test = particion()
    lote = X_test.copy()
    lote[OBJETIVO] = y_test
    return lote.sample(n=n, random_state=semilla).reset_index(drop=True)


def inyectar_drift(lote: pd.DataFrame, semilla: int = SEMILLA_LOTE) -> pd.DataFrame:
    """Escenario: cambio de mercado. La cartera envejece, el banco recorta limites,
    cambia el perfil educativo y mas clientes se atrasan un mes.

    - AGE        : +12 anios (numerica, desplazamiento de media)
    - LIMIT_BAL  : x0.6 (numerica, cambio de escala)
    - BILL_AMT1  : x1.8 (numerica, cola derecha mas pesada)
    - EDUCATION  : la mitad de los clientes pasa a 3 = secundaria (categorica)
    - PAY_0      : el 40 % se atrasa un mes mas (ordinal)
    """
    rng = np.random.default_rng(semilla)
    d = lote.copy()
    d["AGE"] = d["AGE"] + 12
    d["LIMIT_BAL"] = (d["LIMIT_BAL"] * 0.6).round(-3).astype("int64")
    d["BILL_AMT1"] = (d["BILL_AMT1"] * 1.8).round().astype("int64")
    mitad = rng.random(len(d)) < 0.5
    d.loc[mitad, "EDUCATION"] = 3
    atraso = rng.random(len(d)) < 0.4
    d.loc[atraso, "PAY_0"] = (d.loc[atraso, "PAY_0"] + 1).clip(upper=8)
    return d


if __name__ == "__main__":
    CARPETA.mkdir(parents=True, exist_ok=True)
    normal = lote_mismo_origen()
    derivado = inyectar_drift(normal)
    normal.to_csv(CARPETA / "lote_normal.csv", index=False)
    derivado.to_csv(CARPETA / "lote_derivado.csv", index=False)
    print(f"OK: {len(normal)} filas en lote_normal.csv y lote_derivado.csv ({CARPETA})")
    print(f"AGE media: {normal['AGE'].mean():.1f} -> {derivado['AGE'].mean():.1f}; "
          f"LIMIT_BAL media: {normal['LIMIT_BAL'].mean():,.0f} -> {derivado['LIMIT_BAL'].mean():,.0f}")

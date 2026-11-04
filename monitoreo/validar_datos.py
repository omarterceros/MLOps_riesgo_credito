"""Validacion de datos: el segundo pilar (codigo, DATOS, modelo).

Antes de entrenar o de evaluar drift con un lote, se verifica que los datos sirvan:
esquema (las 23 columnas, numericas), sin nulos, rangos del diccionario de datos y un
minimo de filas. Si hay problemas, el proceso termina con codigo 1 y el pipeline se detiene:
con datos basura se entrena basura, y un lote roto no debe disparar ni silenciar una alarma.

Uso: python monitoreo/validar_datos.py <archivo.csv> [--minimo-filas 100]
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from comun.esquema import FEATURES, OBJETIVO  # noqa: E402

# Rangos validos (los del diccionario de datos UCI y los que exige la API en servicio/api.py)
RANGOS = {
    "LIMIT_BAL": (0, None), "SEX": (1, 2), "EDUCATION": (0, 6), "MARRIAGE": (0, 3), "AGE": (18, 100),
    **{f"PAY_{k}": (-2, 9) for k in (0, 2, 3, 4, 5, 6)},
    **{f"PAY_AMT{k}": (0, None) for k in range(1, 7)},
    OBJETIVO: (0, 1),
}
MINIMO_FILAS = 100


def validar(datos: pd.DataFrame, minimo_filas: int = MINIMO_FILAS) -> list[str]:
    """Devuelve la lista de problemas (vacia si los datos estan bien)."""
    faltan = [c for c in FEATURES if c not in datos.columns]
    if faltan:
        return [f"faltan columnas: {faltan}"]
    problemas = []
    no_numericas = [c for c in FEATURES if not pd.api.types.is_numeric_dtype(datos[c])]
    if no_numericas:
        return [f"columnas con valores no numericos: {no_numericas}"]
    if len(datos) < minimo_filas:
        problemas.append(f"hay {len(datos)} filas y se necesitan al menos {minimo_filas}")
    nulos = datos[FEATURES].isna().sum()
    if nulos.sum():
        problemas.append(f"hay {int(nulos.sum())} celdas vacias en {nulos[nulos > 0].index.tolist()}")
    for columna, (minimo, maximo) in RANGOS.items():
        if columna not in datos.columns:
            continue
        serie = datos[columna].dropna()
        fuera = ((serie < minimo) if minimo is not None else False) | ((serie > maximo) if maximo is not None else False)
        if fuera.any():
            problemas.append(f"{columna}: {int(fuera.sum())} valores fuera del rango [{minimo}, {maximo}]")
    return problemas


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Valida esquema, nulos, rangos y tamanio de un archivo de datos.")
    ap.add_argument("archivo")
    ap.add_argument("--minimo-filas", type=int, default=MINIMO_FILAS)
    a = ap.parse_args()
    problemas = validar(pd.read_csv(a.archivo), a.minimo_filas)
    for p in problemas:
        print(f"ERROR: {p}")
    if problemas:
        sys.exit(1)
    print(f"OK: {a.archivo} paso la validacion de datos (esquema, nulos, rangos, filas)")

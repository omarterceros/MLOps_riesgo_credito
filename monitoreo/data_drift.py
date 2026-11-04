"""Deteccion de DATA DRIFT: cambio en la distribucion de las variables de entrada.

Compara cada variable de un lote nuevo contra el baseline (el conjunto de
entrenamiento, la misma particion con la que se entreno el champion).

Pruebas por tipo de variable
----------------------------
- Numericas (LIMIT_BAL, AGE, BILL_AMT*, PAY_AMT*): prueba de Kolmogorov-Smirnov de
  dos muestras + PSI (indice de estabilidad poblacional) sobre 10 deciles del
  baseline. KS es no parametrica (no supone normalidad; los montos son muy
  asimetricos) y mide la mayor distancia D entre las dos distribuciones
  acumuladas. PSI resume cuanto se movio la masa de probabilidad entre deciles.
- Categoricas y ordinales (SEX, EDUCATION, MARRIAGE, PAY_0..PAY_6): prueba
  chi-cuadrado de homogeneidad sobre la tabla de contingencia baseline/lote + PSI
  por categoria. KS no aplica a categorias; chi-cuadrado compara proporciones por
  categoria, y la V de Cramer da el tamanio del efecto.

Umbrales (de donde salen)
-------------------------
- PSI < 0.10 sin cambio; 0.10-0.25 cambio moderado (vigilar); >= 0.25 cambio
  importante. Son los cortes clasicos de la industria del credit scoring
  (Siddiqi, "Credit Risk Scorecards", 2006), de donde sale el dataset.
- alfa = 0.01 para KS y chi-cuadrado. Con 23 variables se hacen 23 pruebas; con
  alfa 0.05 se esperaria mas de un falso positivo por lote, con 0.01 cerca de 0.2.
- Tamanio de efecto minimo: D >= 0.10 (KS) o V de Cramer >= 0.10. Con lotes de
  miles de filas una p chica aparece con cambios irrelevantes; para ponerse en
  ROJO el cambio tiene que ser significativo Y de tamanio practico.

Estado por variable: ROJO si PSI >= 0.25 o (p < alfa y efecto >= minimo);
AMARILLO si PSI >= 0.10 o p < alfa; VERDE en otro caso. Estado del lote: el peor.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from comun.datos import particion  # noqa: E402
from comun.esquema import COLUMNAS, FEATURES  # noqa: E402

ALFA = 0.01
PSI_VIGILAR = 0.10
PSI_CRITICO = 0.25
EFECTO_MINIMO = 0.10
N_BINS = 10
FRACCION_MINIMA = 0.01   # categorias con menos del 1 % en el baseline se agrupan en "otros"
ORDEN_ESTADOS = {"verde": 0, "amarillo": 1, "rojo": 2}


def psi(frac_ref: np.ndarray, frac_nuevo: np.ndarray, eps: float = 1e-4) -> float:
    """Population Stability Index: sum((nuevo - ref) * ln(nuevo / ref))."""
    r = np.clip(frac_ref, eps, None)
    n = np.clip(frac_nuevo, eps, None)
    return float(np.sum((n - r) * np.log(n / r)))


def fracciones_numericas(ref: pd.Series, nuevo: pd.Series, n_bins: int = N_BINS):
    bordes = np.unique(np.quantile(ref, np.linspace(0, 1, n_bins + 1)))
    bordes[0], bordes[-1] = -np.inf, np.inf
    fr = np.histogram(ref, bordes)[0] / len(ref)
    fn = np.histogram(nuevo, bordes)[0] / len(nuevo)
    return fr, fn


def fracciones_categoricas(ref: pd.Series, nuevo: pd.Series, minimo: float = FRACCION_MINIMA):
    """Proporcion por categoria en baseline y lote.

    Las categorias raras del baseline (< 1 %) y las que solo aparecen en el lote se
    agrupan en "otros": chi-cuadrado necesita frecuencias esperadas razonables en cada
    celda y el PSI se dispara con celdas casi vacias (p. ej. PAY_5 = 8 con 2 clientes).
    """
    frecuencias_ref = ref.value_counts(normalize=True)
    raras = set(frecuencias_ref[frecuencias_ref < minimo].index) | (set(nuevo.unique()) - set(frecuencias_ref.index))

    def agrupar(serie: pd.Series) -> pd.Series:
        return serie.astype(str).where(~serie.isin(raras), "otros")

    r, n = agrupar(ref), agrupar(nuevo)
    categorias = sorted(set(r.unique()) | set(n.unique()))
    fr = r.value_counts(normalize=True).reindex(categorias, fill_value=0).to_numpy()
    fn = n.value_counts(normalize=True).reindex(categorias, fill_value=0).to_numpy()
    return fr, fn, categorias


def estado_de(psi_valor: float, p_valor: float, efecto: float) -> str:
    if psi_valor >= PSI_CRITICO or (p_valor < ALFA and efecto >= EFECTO_MINIMO):
        return "rojo"
    if psi_valor >= PSI_VIGILAR or p_valor < ALFA:
        return "amarillo"
    return "verde"


def evaluar_numerica(ref: pd.Series, nuevo: pd.Series) -> dict:
    ks = stats.ks_2samp(ref, nuevo)
    fr, fn = fracciones_numericas(ref, nuevo)
    valor_psi = psi(fr, fn)
    return {
        "prueba": "KS + PSI",
        "estadistico": float(ks.statistic),      # D: distancia maxima entre acumuladas
        "p_valor": float(ks.pvalue),
        "psi": valor_psi,
        "estado": estado_de(valor_psi, ks.pvalue, ks.statistic),
        "detalle": f"media {ref.mean():,.0f} -> {nuevo.mean():,.0f}",
    }


def evaluar_categorica(ref: pd.Series, nuevo: pd.Series) -> dict:
    fr, fn, categorias = fracciones_categoricas(ref, nuevo)
    tabla = np.array([fr * len(ref), fn * len(nuevo)])
    tabla = tabla[:, tabla.sum(axis=0) > 0]
    if tabla.shape[1] > 1:
        chi2, p_valor, _, _ = stats.chi2_contingency(tabla)
        v_cramer = float(np.sqrt(chi2 / tabla.sum()))   # con 2 filas, min(k-1, r-1) = 1
    else:
        chi2, p_valor, v_cramer = 0.0, 1.0, 0.0
    valor_psi = psi(fr, fn)
    moda_ref = categorias[int(np.argmax(fr))]
    moda_nuevo = categorias[int(np.argmax(fn))]
    return {
        "prueba": "chi2 + PSI",
        "estadistico": v_cramer,                  # V de Cramer: tamanio del efecto
        "p_valor": float(p_valor),
        "psi": valor_psi,
        "estado": estado_de(valor_psi, p_valor, v_cramer),
        "detalle": f"moda {moda_ref} ({fr.max():.0%}) -> {moda_nuevo} ({fn.max():.0%})",
    }


def evaluar_lote(referencia: pd.DataFrame, lote: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Evalua todas las variables. Devuelve (tabla por variable, estado global del lote)."""
    filas = []
    for columna in FEATURES:
        tipo = COLUMNAS[columna]
        ref, nuevo = referencia[columna], lote[columna]
        r = evaluar_numerica(ref, nuevo) if tipo == "numerica" else evaluar_categorica(ref, nuevo)
        filas.append({"variable": columna, "tipo": tipo, **r})
    tabla = pd.DataFrame(filas)
    estado_global = max(tabla["estado"], key=ORDEN_ESTADOS.get)
    return tabla, estado_global


def referencia_entrenamiento() -> pd.DataFrame:
    """El baseline: exactamente el conjunto con el que se entreno el modelo."""
    X_train, _, _, _ = particion()
    return X_train


def resumen(tabla: pd.DataFrame, estado_global: str) -> str:
    rojas = tabla.loc[tabla["estado"] == "rojo", "variable"].tolist()
    amarillas = tabla.loc[tabla["estado"] == "amarillo", "variable"].tolist()
    partes = [f"ESTADO DEL LOTE: {estado_global.upper()}"]
    if rojas:
        partes.append(f"{len(rojas)} variable(s) con drift: {', '.join(rojas)}")
    if amarillas:
        partes.append(f"{len(amarillas)} a vigilar: {', '.join(amarillas)}")
    return " | ".join(partes)


def formatear(tabla: pd.DataFrame) -> str:
    t = tabla.copy()
    t["estadistico"] = t["estadistico"].map(lambda v: f"{v:.3f}")
    t["p_valor"] = t["p_valor"].map(lambda v: f"{v:.2e}" if v < 0.001 else f"{v:.3f}")
    t["psi"] = t["psi"].map(lambda v: f"{v:.3f}")
    t["estado"] = t["estado"].str.upper()
    return t.to_string(index=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Evalua data drift de un lote contra el baseline de entrenamiento.")
    ap.add_argument("--lote", required=True, help="CSV con las variables de entrada del lote nuevo")
    ap.add_argument("--salida", help="carpeta donde guardar el reporte (csv + json)")
    args = ap.parse_args()

    lote = pd.read_csv(args.lote)
    tabla, estado_global = evaluar_lote(referencia_entrenamiento(), lote)
    print(f"Lote: {args.lote} ({len(lote)} filas) contra baseline de entrenamiento")
    print(f"Umbrales: alfa={ALFA}, PSI vigilar>={PSI_VIGILAR}, PSI critico>={PSI_CRITICO}, efecto minimo>={EFECTO_MINIMO}\n")
    print(formatear(tabla))
    print()
    print(resumen(tabla, estado_global))

    if args.salida:
        carpeta = Path(args.salida)
        carpeta.mkdir(parents=True, exist_ok=True)
        nombre = Path(args.lote).stem
        tabla.to_csv(carpeta / f"data_drift_{nombre}.csv", index=False)
        (carpeta / f"data_drift_{nombre}.json").write_text(
            json.dumps({"lote": args.lote, "estado": estado_global, "variables": tabla.to_dict("records")},
                       indent=2, ensure_ascii=False), encoding="utf-8")
    sys.exit(1 if estado_global == "rojo" else 0)

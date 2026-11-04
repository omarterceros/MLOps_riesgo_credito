"""Deteccion de CONCEPT DRIFT: cambia la relacion entre las entradas y la variable objetivo.

Uso: python monitoreo/concept_drift.py [--tracking-uri ...] [--salida monitoreo/salidas]

Simulacion
----------
Se construyen 12 lotes mensuales (500 clientes cada uno, sin reposicion: los 6.000
clientes del conjunto de prueba, que el modelo nunca vio al entrenar). Los lotes 1-6 conservan las etiquetas reales. Desde el lote 7
cambia la REGLA del mundo sin tocar las entradas X: un shock economico hace que
clientes que venian pagando al dia (PAY_0 <= 0) caigan en mora. Se reasigna la
etiqueta mora=1 a una fraccion creciente de esos clientes (25 %, 35 %, 45 %, 55 %,
60 %, 60 %). El detector de data drift NO lo ve (X es identico); solo se nota al
comparar las predicciones con las etiquetas reales cuando llegan.

Criterio de reentrenamiento
---------------------------
- Metrica principal: roc_auc del lote, comparada con la referencia (el roc_auc del
  champion sobre el conjunto de prueba al entrenarlo).
- Alarma si la caida es mayor que CAIDA_MAXIMA = 0.05 absoluto durante
  LOTES_SOSTENIDOS = 3 lotes consecutivos. Por que 0.05: con n = 500 y una tasa de
  mora del 22 % el error estandar del AUC es ~0.025 (Hanley-McNeil), asi que 0.05
  esta a 2 errores estandar y no es ruido de muestreo. Por que 3 lotes: un mes malo puede ser
  estacional o un problema de datos; tres meses seguidos es un cambio sostenido y
  el costo de reentrenar (horas) es menor que el de operar tres meses mas con un
  modelo malo.
- Alarma inmediata (sin esperar 3 lotes) si la caida supera CAIDA_CRITICA = 0.10.

Retraso de etiquetas
--------------------
La mora "del mes siguiente" se conoce recien 30-90 dias despues de predecir. Por
eso el reporte incluye senales que NO necesitan etiqueta y se calculan el mismo
dia: PSI de la distribucion de probabilidades predichas y tasa de positivos
predicha. Mientras no llegan las etiquetas, esas senales son el radar temprano;
cuando llegan, se cierra el lote y se evalua la metrica real con retraso.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import f1_score, roc_auc_score  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from comun.datos import particion  # noqa: E402
from comun.esquema import FEATURES  # noqa: E402
from monitoreo.data_drift import psi  # noqa: E402

N_LOTES = 12
N_POR_LOTE = 500                                        # 12 x 500 = los 6.000 clientes del conjunto de prueba
INICIO_DRIFT = 7                                        # primer lote con la regla nueva
FRACCION_REASIGNADA = [0.25, 0.35, 0.45, 0.55, 0.60, 0.60]   # lotes 7..12
CAIDA_MAXIMA = 0.05
CAIDA_CRITICA = 0.10
LOTES_SOSTENIDOS = 3
PSI_SCORE_ALERTA = 0.10
SEMILLA = 2026

# Colores (paleta de referencia del skill dataviz; una sola serie por panel + estado)
AZUL, NARANJA, GRIS, ROJO, AMBAR = "#2a78d6", "#eb6834", "#898781", "#d03b3b", "#fab219"


def simular_lotes(X_test: pd.DataFrame, y_test: pd.Series, con_drift: bool = True, semilla: int = SEMILLA):
    """Devuelve una lista de (X_lote, y_lote). Si con_drift, desde INICIO_DRIFT cambia la regla."""
    rng = np.random.default_rng(semilla)
    indices = rng.permutation(len(X_test))[: N_LOTES * N_POR_LOTE]
    lotes = []
    for k in range(N_LOTES):
        idx = indices[k * N_POR_LOTE:(k + 1) * N_POR_LOTE]
        X = X_test.iloc[idx].reset_index(drop=True)
        y = y_test.iloc[idx].reset_index(drop=True).copy()
        numero = k + 1
        if con_drift and numero >= INICIO_DRIFT:
            fraccion = FRACCION_REASIGNADA[numero - INICIO_DRIFT]
            candidatos = np.flatnonzero((X["PAY_0"] <= 0).to_numpy() & (y.to_numpy() == 0))
            elegidos = rng.choice(candidatos, size=int(len(candidatos) * fraccion), replace=False)
            y.iloc[elegidos] = 1                        # la regla cambio: estos ahora caen en mora
        lotes.append((X, y))
    return lotes


def evaluar_lotes(modelo, lotes, prob_referencia: np.ndarray, umbral: float = 0.5) -> pd.DataFrame:
    """Metricas con etiqueta (roc_auc, f1) y senales sin etiqueta (PSI del score, tasa de positivos)."""
    bordes = np.quantile(prob_referencia, np.linspace(0, 1, 11))
    bordes[0], bordes[-1] = 0.0, 1.0
    frac_ref = np.histogram(prob_referencia, bordes)[0] / len(prob_referencia)
    filas = []
    for k, (X, y) in enumerate(lotes, start=1):
        prob = modelo.predict_proba(X[FEATURES])[:, 1]
        frac = np.histogram(prob, bordes)[0] / len(prob)
        filas.append({
            "lote": k,
            "n": len(X),
            "roc_auc": roc_auc_score(y, prob),
            "f1": f1_score(y, (prob >= umbral).astype(int)),
            "tasa_mora_real": float(y.mean()),
            "tasa_positivos_predicha": float((prob >= umbral).mean()),
            "prob_media": float(prob.mean()),
            "psi_score": psi(frac_ref, frac),
        })
    return pd.DataFrame(filas)


def detectar(aucs, auc_referencia: float, caida=CAIDA_MAXIMA, sostenidos=LOTES_SOSTENIDOS,
             critica=CAIDA_CRITICA):
    """Devuelve (lote de alarma o None, lista de booleanos 'por debajo del umbral')."""
    umbral = auc_referencia - caida
    debajo = [float(a) < umbral for a in aucs]
    racha = 0
    for k, (a, d) in enumerate(zip(aucs, debajo), start=1):
        if float(a) < auc_referencia - critica:
            return k, debajo                    # caida critica: alarma inmediata
        racha = racha + 1 if d else 0
        if racha >= sostenidos:
            return k, debajo
    return None, debajo


def graficar(tabla: pd.DataFrame, auc_referencia: float, alarma, salida: Path) -> None:
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 7.2), sharex=True,
                                   gridspec_kw={"height_ratios": [1.25, 1], "hspace": 0.12})
    fig.patch.set_facecolor("#fcfcfb")
    umbral = auc_referencia - CAIDA_MAXIMA
    lotes = tabla["lote"]

    for ax in (ax1, ax2):
        ax.set_facecolor("#fcfcfb")
        ax.axvspan(INICIO_DRIFT - 0.5, N_LOTES + 0.5, color="#f0efec", zorder=0)
        ax.grid(axis="y", color="#e1e0d9", linewidth=0.8)
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)
        ax.spines["left"].set_color("#c3c2b7")
        ax.spines["bottom"].set_color("#c3c2b7")
        ax.tick_params(colors="#52514e")

    # Panel 1: la metrica principal lote a lote
    ax1.axhline(auc_referencia, color=GRIS, linewidth=1.2, linestyle="--")
    ax1.axhline(umbral, color=ROJO, linewidth=1.2, linestyle=":")
    ax1.plot(lotes, tabla["roc_auc"], color=AZUL, linewidth=2, marker="o", markersize=6, zorder=3)
    ax1.text(0.6, auc_referencia + 0.004, f"referencia (test al entrenar) = {auc_referencia:.3f}", color="#52514e", fontsize=9)
    ax1.text(0.6, umbral - 0.014, f"umbral de alarma = referencia - {CAIDA_MAXIMA:.2f}", color=ROJO, fontsize=9)
    ax1.text(INICIO_DRIFT - 0.4, ax1.get_ylim()[1] if False else tabla["roc_auc"].max() + 0.012,
             "regla nueva desde el lote 7\n(etiquetas reasignadas, X identico)", color="#52514e", fontsize=9, va="bottom")
    if alarma is not None:
        y_alarma = float(tabla.loc[tabla["lote"] == alarma, "roc_auc"].iloc[0])
        ax1.scatter([alarma], [y_alarma], s=160, facecolors="none", edgecolors=ROJO, linewidths=2, zorder=4)
        ax1.annotate(f"ALARMA en el lote {alarma}:\n{LOTES_SOSTENIDOS} lotes seguidos bajo el umbral -> reentrenar",
                     (alarma, y_alarma), xytext=(alarma - 3.2, y_alarma - 0.07), color=ROJO, fontsize=9,
                     arrowprops={"arrowstyle": "->", "color": ROJO})
    for k, v in zip(lotes, tabla["roc_auc"]):
        if k in (1, INICIO_DRIFT, N_LOTES) or k == alarma:
            ax1.annotate(f"{v:.3f}", (k, v), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=8, color="#0b0b0b")
    ax1.set_ylabel("roc_auc del lote", color="#52514e")
    ax1.set_title("Concept drift: degradacion de la metrica principal en lotes mensuales sucesivos",
                  loc="left", fontsize=11, color="#0b0b0b")
    ax1.set_ylim(min(tabla["roc_auc"].min(), umbral) - 0.09, max(tabla["roc_auc"].max(), auc_referencia) + 0.05)

    # Panel 2: senales sin etiqueta vs la realidad que llega con retraso
    ax2.plot(lotes, tabla["tasa_mora_real"], color=NARANJA, linewidth=2, marker="o", markersize=6, label="tasa de mora real (llega con retraso)")
    ax2.plot(lotes, tabla["tasa_positivos_predicha"], color=AZUL, linewidth=2, marker="s", markersize=5, label="tasa de positivos predicha (sin etiqueta)")
    ax2.text(N_LOTES + 0.15, tabla["tasa_mora_real"].iloc[-1], "real", color=NARANJA, fontsize=9, va="center")
    ax2.text(N_LOTES + 0.15, tabla["tasa_positivos_predicha"].iloc[-1], "predicha", color=AZUL, fontsize=9, va="center")
    ax2.set_ylabel("proporcion de clientes", color="#52514e")
    ax2.set_xlabel("lote mensual", color="#52514e")
    ax2.set_xticks(list(lotes))
    ax2.set_xlim(0.5, N_LOTES + 1.2)
    ax2.legend(loc="upper left", frameon=False, fontsize=9)
    ax2.set_title("Las entradas no cambian: la tasa predicha se mantiene mientras la real se dispara",
                  loc="left", fontsize=10, color="#52514e")

    salida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(salida, dpi=150, bbox_inches="tight")
    plt.close(fig)


def cargar_champion(tracking_uri: str):
    import mlflow
    import mlflow.sklearn
    from mlflow import MlflowClient

    mlflow.set_tracking_uri(tracking_uri)
    cliente = MlflowClient()
    mv = cliente.get_model_version_by_alias("riesgo-credito", "champion")
    modelo = mlflow.sklearn.load_model(f"models:/riesgo-credito/{mv.version}")
    run = cliente.get_run(mv.run_id)
    return modelo, {"version": int(mv.version), "run_id": mv.run_id, "run_name": run.info.run_name,
                    "roc_auc_referencia": run.data.metrics["roc_auc"]}


def main() -> int:
    ap = argparse.ArgumentParser(description="Simula concept drift y evalua el criterio de reentrenamiento.")
    ap.add_argument("--tracking-uri", default=os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5050"))
    ap.add_argument("--salida", default=str(RAIZ / "monitoreo" / "salidas"))
    args = ap.parse_args()

    modelo, info = cargar_champion(args.tracking_uri)
    auc_ref = info["roc_auc_referencia"]
    print(f"Champion: version {info['version']} (run {info['run_id']}, {info['run_name']}), roc_auc de referencia {auc_ref:.4f}")

    _, X_test, _, y_test = particion()
    prob_ref = modelo.predict_proba(X_test[FEATURES])[:, 1]
    tabla = evaluar_lotes(modelo, simular_lotes(X_test, y_test, con_drift=True), prob_ref)
    alarma, debajo = detectar(tabla["roc_auc"], auc_ref)
    tabla["bajo_umbral"] = debajo
    tabla["regla_nueva"] = tabla["lote"] >= INICIO_DRIFT

    pd.set_option("display.width", 160)
    print(f"\nCriterio: caida > {CAIDA_MAXIMA} durante {LOTES_SOSTENIDOS} lotes seguidos (o > {CAIDA_CRITICA} en uno). Umbral = {auc_ref - CAIDA_MAXIMA:.4f}\n")
    print(tabla.round(4).to_string(index=False))
    if alarma is None:
        print("\nSin alarma: el modelo sigue sirviendo.")
    else:
        print(f"\nALARMA DE CONCEPT DRIFT en el lote {alarma}: se dispara el reentrenamiento (challenger).")
    lotes_psi = tabla.loc[tabla["psi_score"] >= PSI_SCORE_ALERTA, "lote"].tolist()
    print(f"Senal sin etiqueta (PSI del score >= {PSI_SCORE_ALERTA}): {'lotes ' + str(lotes_psi) if lotes_psi else 'ninguna'} "
          f"-> el drift de concepto puro no se ve en las entradas ni en los scores.")

    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(salida / "concept_drift.csv", index=False)
    (salida / "concept_drift.json").write_text(json.dumps({**info, "alarma_en_lote": alarma, "caida_maxima": CAIDA_MAXIMA,
                                                           "lotes_sostenidos": LOTES_SOSTENIDOS}, indent=2), encoding="utf-8")
    graficar(tabla, auc_ref, alarma, salida / "concept_drift.png")
    print(f"Grafica: {salida / 'concept_drift.png'}")
    return 1 if alarma is not None else 0


if __name__ == "__main__":
    sys.exit(main())

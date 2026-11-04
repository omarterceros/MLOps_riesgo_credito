"""Entrena varios modelos de riesgo crediticio y registra todo el ciclo en MLflow.

Uso: python entrenamiento/entrenar.py [--tracking-uri http://127.0.0.1:5050]

- Semilla fija (42) y division train/test 80/20 estratificada (comun/datos.py).
- 8 ejecuciones (runs) con distintos algoritmos e hiperparametros, comparables entre
  si porque usan exactamente la misma particion y las mismas metricas.
- Cada run guarda: parametros, metricas (roc_auc es la principal), tags (dataset,
  md5 de los datos, familia de modelo), la matriz de confusion y el reporte de
  clasificacion como artefactos, el dataset de entrenamiento como input y el modelo
  empaquetado (flavor sklearn) con firma y ejemplo de entrada.
"""
import argparse
import os
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import mlflow  # noqa: E402
import mlflow.sklearn  # noqa: E402
import pandas as pd  # noqa: E402
from mlflow.models import infer_signature  # noqa: E402
from sklearn.compose import ColumnTransformer  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    ConfusionMatrixDisplay,
    accuracy_score,
    average_precision_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import OneHotEncoder, StandardScaler  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from comun.datos import ARCHIVO_DATOS, cargar_datos, md5_datos, particion  # noqa: E402
from comun.esquema import FEATURES, OBJETIVO, SEMILLA, TEST_SIZE  # noqa: E402

EXPERIMENTO = "riesgo-credito"
NOMBRE_MODELO_EN_RUN = "modelo"
NOMINALES = ["SEX", "EDUCATION", "MARRIAGE"]   # se codifican one-hot; el resto se escala
TRACKING_URI_DEFECTO = "http://127.0.0.1:5050"

# (nombre del run, familia, hiperparametros). De lo mas simple a lo mas complejo.
CONFIGURACIONES = [
    ("logreg_C0.01", "regresion_logistica", {"C": 0.01}),
    ("logreg_C0.1", "regresion_logistica", {"C": 0.1}),
    ("logreg_C1", "regresion_logistica", {"C": 1.0}),
    ("rf_100arboles_prof8", "random_forest", {"n_estimators": 100, "max_depth": 8}),
    ("rf_200arboles_prof12", "random_forest", {"n_estimators": 200, "max_depth": 12}),
    ("hgb_lr0.05_200it", "hist_gradient_boosting", {"learning_rate": 0.05, "max_iter": 200}),
    ("hgb_lr0.1_200it", "hist_gradient_boosting", {"learning_rate": 0.1, "max_iter": 200}),
    ("hgb_lr0.1_400it_prof4", "hist_gradient_boosting", {"learning_rate": 0.1, "max_iter": 400, "max_depth": 4}),
]


def construir_estimador(familia: str, hiperparametros: dict):
    if familia == "regresion_logistica":
        return LogisticRegression(max_iter=3000, random_state=SEMILLA, **hiperparametros)
    if familia == "random_forest":
        return RandomForestClassifier(random_state=SEMILLA, n_jobs=-1, **hiperparametros)
    if familia == "hist_gradient_boosting":
        return HistGradientBoostingClassifier(random_state=SEMILLA, **hiperparametros)
    raise ValueError(f"familia desconocida: {familia}")


def construir_pipeline(estimador) -> Pipeline:
    """Preprocesamiento + modelo en un solo objeto: lo que se empaqueta es el pipeline completo."""
    resto = [c for c in FEATURES if c not in NOMINALES]
    preprocesamiento = ColumnTransformer([
        ("nominales", OneHotEncoder(handle_unknown="ignore", sparse_output=False), NOMINALES),
        ("numericas", StandardScaler(), resto),
    ])
    return Pipeline([("preprocesamiento", preprocesamiento), ("modelo", estimador)])


def metricas(y_real, prob, umbral: float = 0.5) -> dict:
    pred = (prob >= umbral).astype(int)
    return {
        "roc_auc": roc_auc_score(y_real, prob),           # metrica principal (no depende del umbral)
        "pr_auc": average_precision_score(y_real, prob),
        "accuracy": accuracy_score(y_real, pred),
        "f1": f1_score(y_real, pred),
        "precision": precision_score(y_real, pred, zero_division=0),
        "recall": recall_score(y_real, pred),
    }


def entrenar_todo(tracking_uri: str) -> pd.DataFrame:
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(EXPERIMENTO)

    datos = cargar_datos()
    X_train, X_test, y_train, y_test = particion(datos)
    huella = md5_datos()
    dataset_train = mlflow.data.from_pandas(
        pd.concat([X_train, y_train], axis=1), source=str(ARCHIVO_DATOS), name="credito_train", targets=OBJETIVO
    )
    print(f"Datos: {len(datos)} filas, md5 {huella}. Train {len(X_train)} / test {len(X_test)} (semilla {SEMILLA}).")

    resumen = []
    for nombre, familia, hiperparametros in CONFIGURACIONES:
        with mlflow.start_run(run_name=nombre) as run:
            pipeline = construir_pipeline(construir_estimador(familia, hiperparametros))

            t0 = time.perf_counter()
            pipeline.fit(X_train, y_train)
            segundos = time.perf_counter() - t0

            prob = pipeline.predict_proba(X_test)[:, 1]
            m = metricas(y_test, prob)

            # --- Que se registra en el run ---
            mlflow.log_input(dataset_train, context="training")
            mlflow.set_tags({
                "dataset": "UCI default of credit card clients (OpenML 42477)",
                "datos_md5": huella,
                "familia": familia,
                "metrica_principal": "roc_auc",
            })
            mlflow.log_params({
                "familia": familia,
                **hiperparametros,
                "semilla": SEMILLA,
                "test_size": TEST_SIZE,
                "estratificado_por": OBJETIVO,
                "n_train": len(X_train),
                "n_test": len(X_test),
                "n_features": len(FEATURES),
            })
            mlflow.log_metrics({**m, "segundos_entrenamiento": segundos})

            fig, ax = plt.subplots(figsize=(4, 4))
            ConfusionMatrixDisplay.from_predictions(y_test, (prob >= 0.5).astype(int), ax=ax, colorbar=False)
            ax.set_title(f"{nombre} (umbral 0.5)")
            mlflow.log_figure(fig, "matriz_confusion.png")
            plt.close(fig)
            mlflow.log_text(classification_report(y_test, (prob >= 0.5).astype(int)), "reporte_clasificacion.txt")

            firma = infer_signature(X_train.head(100), pipeline.predict_proba(X_train.head(100)))
            info = mlflow.sklearn.log_model(
                sk_model=pipeline,
                name=NOMBRE_MODELO_EN_RUN,
                signature=firma,
                input_example=X_train.head(3),
                pyfunc_predict_fn="predict_proba",
            )
            mlflow.set_tag("modelo_id", info.model_id)

            resumen.append({"run_name": nombre, "run_id": run.info.run_id, "familia": familia, **m,
                            "segundos": round(segundos, 1)})
            print(f"  {nombre:<24} roc_auc={m['roc_auc']:.4f}  f1={m['f1']:.4f}  acc={m['accuracy']:.4f}  ({segundos:.1f} s)")

    tabla = pd.DataFrame(resumen).sort_values("roc_auc", ascending=False).reset_index(drop=True)
    return tabla


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tracking-uri", default=os.getenv("MLFLOW_TRACKING_URI", TRACKING_URI_DEFECTO))
    args = ap.parse_args()

    tabla = entrenar_todo(args.tracking_uri)
    pd.set_option("display.width", 160)
    print("\nRuns ordenados por roc_auc (metrica principal):")
    print(tabla[["run_name", "familia", "roc_auc", "pr_auc", "f1", "accuracy", "segundos", "run_id"]].to_string(index=False))
    print(f"\nMejor run: {tabla.iloc[0]['run_name']} ({tabla.iloc[0]['run_id']}) roc_auc={tabla.iloc[0]['roc_auc']:.4f}")

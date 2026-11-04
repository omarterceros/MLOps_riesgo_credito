"""Registra el modelo en el Model Registry de MLflow y marca cual esta en produccion.

Uso: python entrenamiento/registrar.py [--tracking-uri http://127.0.0.1:5050]

Estrategia champion / challenger (la que explico el docente):
  - Version 1 = la mejor regresion logistica: el modelo base, simple e interpretable,
    que fue el primer "champion". Queda con alias `baseline` para poder volver atras.
  - Version 2 = el mejor run del experimento por roc_auc (el "challenger"). Como le
    gana al base en la metrica principal, se promueve: alias `champion`.
El servicio de inferencia carga `models:/riesgo-credito@champion`; nunca una ruta
de archivo. Este script tambien escribe entrenamiento/modelo_desplegado.json, que
es la referencia que cita el documento de arquitectura.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import mlflow
from mlflow import MlflowClient

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from entrenamiento.entrenar import EXPERIMENTO, NOMBRE_MODELO_EN_RUN, TRACKING_URI_DEFECTO  # noqa: E402

NOMBRE_REGISTRO = "riesgo-credito"
ALIAS_PRODUCCION = "champion"
ALIAS_BASE = "baseline"
ARCHIVO_DESPLEGADO = RAIZ / "entrenamiento" / "modelo_desplegado.json"


def uri_del_modelo(run) -> str:
    modelo_id = run.data.tags.get("modelo_id")
    return f"models:/{modelo_id}" if modelo_id else f"runs:/{run.info.run_id}/{NOMBRE_MODELO_EN_RUN}"


def version_existente(cliente: MlflowClient, run_id: str):
    for mv in cliente.search_model_versions(f"name='{NOMBRE_REGISTRO}'"):
        if mv.run_id == run_id:
            return mv
    return None


def registrar_run(cliente: MlflowClient, run, motivo: str):
    """Registra el modelo del run como nueva version (o reutiliza la version si ya existe)."""
    mv = version_existente(cliente, run.info.run_id)
    if mv is None:
        mv = mlflow.register_model(model_uri=uri_del_modelo(run), name=NOMBRE_REGISTRO)
    auc = run.data.metrics["roc_auc"]
    cliente.update_model_version(
        NOMBRE_REGISTRO, mv.version,
        description=f"{motivo}. Run '{run.info.run_name}' ({run.info.run_id}), roc_auc={auc:.4f}, "
                    f"familia={run.data.tags.get('familia')}, datos md5 {run.data.tags.get('datos_md5')}.",
    )
    cliente.set_model_version_tag(NOMBRE_REGISTRO, mv.version, "run_name", run.info.run_name)
    cliente.set_model_version_tag(NOMBRE_REGISTRO, mv.version, "roc_auc", f"{auc:.4f}")
    return cliente.get_model_version(NOMBRE_REGISTRO, mv.version)


def main(tracking_uri: str) -> None:
    mlflow.set_tracking_uri(tracking_uri)
    cliente = MlflowClient()
    experimento = cliente.get_experiment_by_name(EXPERIMENTO)
    if experimento is None:
        sys.exit(f"No existe el experimento '{EXPERIMENTO}': primero corre entrenamiento/entrenar.py")

    runs = cliente.search_runs([experimento.experiment_id], order_by=["metrics.roc_auc DESC"], max_results=100)
    runs = [r for r in runs if "roc_auc" in r.data.metrics]
    mejor = runs[0]
    mejor_logistica = next(r for r in runs if r.data.tags.get("familia") == "regresion_logistica")

    try:
        cliente.create_registered_model(
            NOMBRE_REGISTRO,
            description="Probabilidad de mora el mes siguiente para clientes de tarjeta de credito "
                        "(UCI default of credit card clients). Alias: champion = en produccion, baseline = modelo base.",
        )
    except mlflow.exceptions.MlflowException:
        pass  # ya existe

    v_base = registrar_run(cliente, mejor_logistica, "Modelo base (regresion logistica)")
    v_prod = registrar_run(cliente, mejor, "Mejor run del experimento por roc_auc: promovido a produccion")

    cliente.set_registered_model_alias(NOMBRE_REGISTRO, ALIAS_BASE, v_base.version)
    cliente.set_registered_model_alias(NOMBRE_REGISTRO, ALIAS_PRODUCCION, v_prod.version)

    desplegado = {
        "nombre_registro": NOMBRE_REGISTRO,
        "alias": ALIAS_PRODUCCION,
        "uri": f"models:/{NOMBRE_REGISTRO}@{ALIAS_PRODUCCION}",
        "version": int(v_prod.version),
        "run_id": mejor.info.run_id,
        "run_name": mejor.info.run_name,
        "experimento": EXPERIMENTO,
        "roc_auc": round(mejor.data.metrics["roc_auc"], 4),
        "familia": mejor.data.tags.get("familia"),
        "datos_md5": mejor.data.tags.get("datos_md5"),
        "baseline": {"alias": ALIAS_BASE, "version": int(v_base.version), "run_id": mejor_logistica.info.run_id,
                     "run_name": mejor_logistica.info.run_name,
                     "roc_auc": round(mejor_logistica.data.metrics["roc_auc"], 4)},
    }
    ARCHIVO_DESPLEGADO.write_text(json.dumps(desplegado, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Modelo registrado: '{NOMBRE_REGISTRO}'")
    print(f"{'version':>8}  {'alias':<9} {'run_name':<24} {'roc_auc':>8}  run_id")
    for mv in sorted(cliente.search_model_versions(f"name='{NOMBRE_REGISTRO}'"), key=lambda v: int(v.version)):
        alias = ", ".join(mv.aliases) if mv.aliases else "-"
        print(f"{mv.version:>8}  {alias:<9} {mv.tags.get('run_name', ''):<24} {mv.tags.get('roc_auc', ''):>8}  {mv.run_id}")
    print(f"\nEl servicio consume: {desplegado['uri']}  ->  version {v_prod.version}, run {mejor.info.run_id}")
    print(f"Referencia escrita en {ARCHIVO_DESPLEGADO.relative_to(RAIZ)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tracking-uri", default=os.getenv("MLFLOW_TRACKING_URI", TRACKING_URI_DEFECTO))
    main(ap.parse_args().tracking_uri)

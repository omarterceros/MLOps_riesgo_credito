"""Mueve el alias `champion` del registro a otra version (promocion o rollback).

Uso: python scripts/cambiar_champion.py <version> [--tracking-uri http://127.0.0.1:5050]

Despues de mover el alias, los pods toman la version nueva al reiniciarse:
    kubectl rollout restart deployment/riesgo-credito-api -n riesgo-credito
(con maxSurge 1 / maxUnavailable 0 el servicio no se corta). No hace falta reconstruir la imagen.
"""
import argparse
import os

import mlflow
from mlflow import MlflowClient

NOMBRE = "riesgo-credito"
ALIAS = "champion"

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("version")
    ap.add_argument("--tracking-uri", default=os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5050"))
    a = ap.parse_args()
    mlflow.set_tracking_uri(a.tracking_uri)
    cliente = MlflowClient()
    antes = cliente.get_model_version_by_alias(NOMBRE, ALIAS)
    cliente.set_registered_model_alias(NOMBRE, ALIAS, a.version)
    ahora = cliente.get_model_version_by_alias(NOMBRE, ALIAS)
    print(f"alias {ALIAS}: version {antes.version} (run {antes.run_id}) -> version {ahora.version} (run {ahora.run_id})")

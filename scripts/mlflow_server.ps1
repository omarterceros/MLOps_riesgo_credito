# Levanta el servidor de MLflow (tracking + model registry + UI) en http://localhost:5050
# Escucha en 0.0.0.0 para que los pods de Kubernetes lleguen por host.docker.internal.
# --workers 1: con SQLite como backend, varios procesos se bloquean entre si al escribir
# (el endpoint logged-models se colgaba 120 s con los 4 workers por defecto).
# Ejecutar desde la raiz del repositorio:  .\scripts\mlflow_server.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force -Path mlflow | Out-Null
& .\.venv\Scripts\mlflow.exe server `
    --backend-store-uri sqlite:///mlflow/mlflow.db `
    --artifacts-destination ./mlflow/artefactos `
    --host 0.0.0.0 --port 5050 --workers 1

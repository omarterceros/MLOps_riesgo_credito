# Fase 1: descarga los datos (si faltan), corre los 8 experimentos y registra el modelo.
# Requiere el servidor de MLflow levantado (scripts\mlflow_server.ps1).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path datos\credito.csv)) { & $py datos\descargar.py }
& $py monitoreo\validar_datos.py datos\credito.csv      # pilar de datos: si falla, no se entrena
if ($LASTEXITCODE -ne 0) { throw "los datos no pasaron la validacion" }
& $py entrenamiento\entrenar.py
& $py entrenamiento\registrar.py                         # incluye la compuerta de calidad

"""Servicio de inferencia: API REST (FastAPI) que sirve el modelo registrado en MLflow.

El modelo NO viaja dentro de la imagen ni se lee de una ruta de archivo: al arrancar,
el servicio resuelve el alias `champion` del modelo `riesgo-credito` en el Model
Registry y descarga esa version exacta. Cada respuesta informa que pod atendio la
peticion y que version/run del registro la produjo (trazabilidad de extremo a extremo).

Variables de entorno:
  MLFLOW_TRACKING_URI   servidor de MLflow (p. ej. http://host.docker.internal:5050)
  MODELO_NOMBRE         nombre en el registro (riesgo-credito)
  MODELO_ALIAS          alias que se despliega (champion)
  POD_NAME              lo inyecta Kubernetes (metadata.name); si falta, el hostname
  UMBRAL_MORA           probabilidad a partir de la cual se declara mora (0.5)
  CARGAR_MODELO_AL_INICIO  "0" para no cargar el modelo (solo pruebas unitarias)
"""
import asyncio
import logging
import os
import socket
from contextlib import asynccontextmanager

import mlflow
import mlflow.sklearn
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from mlflow import MlflowClient
from pydantic import BaseModel, Field

from comun.esquema import COLUMNAS, EJEMPLO_ALTO_RIESGO, EJEMPLO_BAJO_RIESGO, FEATURES

log = logging.getLogger("uvicorn.error")

MODELO_NOMBRE = os.getenv("MODELO_NOMBRE", "riesgo-credito")
MODELO_ALIAS = os.getenv("MODELO_ALIAS", "champion")
MODELO_URI = f"models:/{MODELO_NOMBRE}@{MODELO_ALIAS}"
POD = os.getenv("POD_NAME") or socket.gethostname()
UMBRAL = float(os.getenv("UMBRAL_MORA", "0.5"))
REINTENTO_S = float(os.getenv("REINTENTO_CARGA_S", "10"))

# Estado del proceso: el modelo cargado y de donde salio.
estado = {"modelo": None, "version": None, "run_id": None, "run_name": None, "error": None}


def cargar_modelo() -> None:
    """Resuelve el alias en el registro y carga esa version exacta (flavor sklearn)."""
    cliente = MlflowClient()
    mv = cliente.get_model_version_by_alias(MODELO_NOMBRE, MODELO_ALIAS)
    modelo = mlflow.sklearn.load_model(f"models:/{MODELO_NOMBRE}/{mv.version}")
    run = cliente.get_run(mv.run_id)
    estado.update(modelo=modelo, version=int(mv.version), run_id=mv.run_id, run_name=run.info.run_name, error=None)
    log.info("Modelo cargado: %s -> version %s, run %s (%s)", MODELO_URI, mv.version, mv.run_id, run.info.run_name)


async def cargar_con_reintentos() -> None:
    while estado["modelo"] is None:
        try:
            await asyncio.to_thread(cargar_modelo)
        except Exception as exc:  # el servidor de MLflow puede no estar listo todavia
            estado["error"] = f"{type(exc).__name__}: {exc}"
            log.warning("No se pudo cargar %s (%s); reintento en %.0f s", MODELO_URI, estado["error"], REINTENTO_S)
            await asyncio.sleep(REINTENTO_S)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    tarea = None
    if os.getenv("CARGAR_MODELO_AL_INICIO", "1") == "1":
        tarea = asyncio.create_task(cargar_con_reintentos())
    yield
    if tarea:
        tarea.cancel()


app = FastAPI(
    title="API de Riesgo Crediticio",
    description="Predice la probabilidad de mora el mes siguiente. Modelo servido desde el Model Registry de MLflow.",
    version="1.0",
    lifespan=ciclo_de_vida,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class Solicitante(BaseModel):
    """Las 23 variables del dataset UCI. Los rangos son los del diccionario de datos."""
    LIMIT_BAL: int = Field(..., ge=0, description="Limite de credito")
    SEX: int = Field(..., ge=1, le=2, description="1 hombre, 2 mujer")
    EDUCATION: int = Field(..., ge=0, le=6, description="1 posgrado, 2 universidad, 3 secundaria, 4 otros")
    MARRIAGE: int = Field(..., ge=0, le=3, description="1 casado, 2 soltero, 3 otros")
    AGE: int = Field(..., ge=18, le=100)
    PAY_0: int = Field(..., ge=-2, le=9, description="Estado de pago septiembre (-2..0 al dia, 1..9 meses de atraso)")
    PAY_2: int = Field(..., ge=-2, le=9)
    PAY_3: int = Field(..., ge=-2, le=9)
    PAY_4: int = Field(..., ge=-2, le=9)
    PAY_5: int = Field(..., ge=-2, le=9)
    PAY_6: int = Field(..., ge=-2, le=9)
    BILL_AMT1: int
    BILL_AMT2: int
    BILL_AMT3: int
    BILL_AMT4: int
    BILL_AMT5: int
    BILL_AMT6: int
    PAY_AMT1: int = Field(..., ge=0)
    PAY_AMT2: int = Field(..., ge=0)
    PAY_AMT3: int = Field(..., ge=0)
    PAY_AMT4: int = Field(..., ge=0)
    PAY_AMT5: int = Field(..., ge=0)
    PAY_AMT6: int = Field(..., ge=0)

    model_config = {"json_schema_extra": {"examples": [EJEMPLO_BAJO_RIESGO, EJEMPLO_ALTO_RIESGO]}}


def info_modelo() -> dict:
    return {"nombre": MODELO_NOMBRE, "alias": MODELO_ALIAS, "uri": MODELO_URI,
            "version": estado["version"], "run_id": estado["run_id"], "run_name": estado["run_name"]}


@app.get("/", include_in_schema=False)
def raiz():
    return RedirectResponse("/docs")


@app.get("/vivo")
def vivo():
    """Liveness: el proceso atiende peticiones. No depende de MLflow: si el modelo no esta
    cargado es /health (readiness) la que deja al pod fuera del Service, sin reiniciarlo."""
    return {"status": "vivo", "pod": POD}


@app.get("/health")
def health():
    """Readiness: listo solo cuando el modelo esta cargado; hasta entonces el pod no recibe trafico."""
    if estado["modelo"] is None:
        return JSONResponse(status_code=503, content={"status": "cargando_modelo", "pod": POD, "error": estado["error"]})
    return {"status": "ok", "pod": POD, "modelo": info_modelo()}


@app.get("/info")
def info():
    return {"pod": POD, "mlflow_tracking_uri": mlflow.get_tracking_uri(), "umbral": UMBRAL, "modelo": info_modelo()}


@app.get("/esquema")
def esquema():
    """Lo usa la interfaz web para construir el formulario."""
    return {"columnas": [{"nombre": c, "tipo": t} for c, t in COLUMNAS.items()],
            "ejemplos": {"bajo_riesgo": EJEMPLO_BAJO_RIESGO, "alto_riesgo": EJEMPLO_ALTO_RIESGO}}


@app.post("/predecir")
def predecir(solicitante: Solicitante):
    if estado["modelo"] is None:
        raise HTTPException(status_code=503, detail=f"modelo no disponible todavia: {estado['error']}")
    X = pd.DataFrame([solicitante.model_dump()])[FEATURES]
    probabilidad = float(estado["modelo"].predict_proba(X)[0][1])
    return {
        "mora": int(probabilidad >= UMBRAL),
        "probabilidad_mora": round(probabilidad, 4),
        "umbral": UMBRAL,
        "pod": POD,
        "modelo": info_modelo(),
    }

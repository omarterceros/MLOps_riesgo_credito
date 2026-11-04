"""Pruebas del servicio de inferencia (sin MLflow: se inyecta un modelo falso)."""
import numpy as np
import pytest
from fastapi.testclient import TestClient

from comun.esquema import EJEMPLO_ALTO_RIESGO, EJEMPLO_BAJO_RIESGO, FEATURES
from servicio import api


class ModeloFalso:
    def predict_proba(self, X):
        assert list(X.columns) == FEATURES
        p = 0.9 if X.iloc[0]["PAY_0"] >= 2 else 0.1
        return np.array([[1 - p, p]])


@pytest.fixture
def cliente():
    api.estado.update(modelo=ModeloFalso(), version=2, run_id="abc123", run_name="hgb", error=None)
    with TestClient(api.app) as c:
        yield c
    api.estado.update(modelo=None, version=None, run_id=None, run_name=None)


def test_health_ok_con_modelo_cargado(cliente):
    r = cliente.get("/health")
    assert r.status_code == 200
    assert r.json()["modelo"]["version"] == 2


def test_health_503_sin_modelo():
    api.estado.update(modelo=None, error="sin conexion")
    with TestClient(api.app) as c:
        r = c.get("/health")
    assert r.status_code == 503


def test_predecir_bajo_riesgo(cliente):
    r = cliente.post("/predecir", json=EJEMPLO_BAJO_RIESGO)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["mora"] == 0 and cuerpo["probabilidad_mora"] == 0.1
    assert {"pod", "modelo", "umbral"} <= cuerpo.keys()
    assert cuerpo["modelo"]["run_id"] == "abc123"


def test_predecir_alto_riesgo(cliente):
    cuerpo = cliente.post("/predecir", json=EJEMPLO_ALTO_RIESGO).json()
    assert cuerpo["mora"] == 1


def test_rechaza_valores_invalidos(cliente):
    invalido = {**EJEMPLO_BAJO_RIESGO, "SEX": 3, "AGE": 10}
    r = cliente.post("/predecir", json=invalido)
    assert r.status_code == 422
    campos = {e["loc"][-1] for e in r.json()["detail"]}
    assert campos == {"SEX", "AGE"}


def test_rechaza_campos_faltantes(cliente):
    incompleto = {k: v for k, v in EJEMPLO_BAJO_RIESGO.items() if k != "LIMIT_BAL"}
    assert cliente.post("/predecir", json=incompleto).status_code == 422


def test_esquema_expone_las_23_variables(cliente):
    cuerpo = cliente.get("/esquema").json()
    assert [c["nombre"] for c in cuerpo["columnas"]] == FEATURES

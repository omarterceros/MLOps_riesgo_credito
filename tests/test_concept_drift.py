"""Pruebas del detector de concept drift (monitoreo/concept_drift.py).

Usan un modelo rapido entrenado aqui mismo (no dependen del servidor de MLflow):
sin cambio de regla no hay alarma; con la regla nueva la alarma salta a los 3 lotes.
"""
import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from comun.esquema import FEATURES
from monitoreo.concept_drift import (
    CAIDA_MAXIMA,
    INICIO_DRIFT,
    LOTES_SOSTENIDOS,
    detectar,
    evaluar_lotes,
    simular_lotes,
)


@pytest.fixture(scope="module")
def modelo_y_referencia(datos_particionados):
    X_train, X_test, y_train, y_test = datos_particionados
    modelo = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, random_state=42))
    modelo.fit(X_train[FEATURES], y_train)
    prob = modelo.predict_proba(X_test[FEATURES])[:, 1]
    return modelo, roc_auc_score(y_test, prob), prob


def test_detectar_sin_caida_no_alarma():
    assert detectar([0.78, 0.77, 0.79, 0.76], auc_referencia=0.78)[0] is None


def test_detectar_exige_caida_sostenida():
    aucs = [0.78, 0.70, 0.78, 0.70, 0.70, 0.70, 0.78]     # dos bajas aisladas, luego tres seguidas
    alarma, debajo = detectar(aucs, auc_referencia=0.78)
    assert alarma == 6
    assert debajo == [False, True, False, True, True, True, False]


def test_detectar_caida_critica_es_inmediata():
    assert detectar([0.78, 0.60], auc_referencia=0.78)[0] == 2


def test_sin_cambio_de_regla_no_hay_alarma(datos_particionados, modelo_y_referencia):
    _, X_test, _, y_test = datos_particionados
    modelo, auc_ref, prob_ref = modelo_y_referencia
    tabla = evaluar_lotes(modelo, simular_lotes(X_test, y_test, con_drift=False), prob_ref)
    alarma, debajo = detectar(tabla["roc_auc"], auc_ref)
    assert alarma is None
    # con n = 500 un lote aislado puede caer bajo el umbral por azar; lo que no debe haber es una racha
    assert sum(debajo) <= 2


def test_con_regla_nueva_la_alarma_salta(datos_particionados, modelo_y_referencia):
    _, X_test, _, y_test = datos_particionados
    modelo, auc_ref, prob_ref = modelo_y_referencia
    tabla = evaluar_lotes(modelo, simular_lotes(X_test, y_test, con_drift=True), prob_ref)
    alarma, debajo = detectar(tabla["roc_auc"], auc_ref)
    assert alarma is not None
    assert alarma >= INICIO_DRIFT                       # nunca antes del cambio de regla
    assert all(debajo[alarma - LOTES_SOSTENIDOS:alarma])   # los 3 lotes previos a la alarma estan bajo el umbral
    estables = tabla.loc[tabla["lote"] < INICIO_DRIFT, "roc_auc"].mean()
    derivados = tabla.loc[tabla["lote"] >= INICIO_DRIFT, "roc_auc"].mean()
    assert estables - derivados > CAIDA_MAXIMA


def test_el_concept_drift_no_se_ve_en_las_entradas(datos_particionados, modelo_y_referencia):
    """Las X son identicas con y sin drift: el PSI del score no cambia (por eso hacen falta etiquetas)."""
    _, X_test, _, y_test = datos_particionados
    modelo, _, prob_ref = modelo_y_referencia
    sin = evaluar_lotes(modelo, simular_lotes(X_test, y_test, con_drift=False), prob_ref)
    con = evaluar_lotes(modelo, simular_lotes(X_test, y_test, con_drift=True), prob_ref)
    assert np.allclose(sin["psi_score"], con["psi_score"])
    assert np.allclose(sin["tasa_positivos_predicha"], con["tasa_positivos_predicha"])

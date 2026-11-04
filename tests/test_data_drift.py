"""Pruebas del detector de data drift (monitoreo/data_drift.py).

Verifican el detector en si: VERDE con datos del mismo origen y ROJO con drift inyectado.
"""
import numpy as np

from monitoreo.data_drift import PSI_CRITICO, evaluar_lote, psi
from monitoreo.lotes import inyectar_drift, lote_mismo_origen


def test_psi_es_cero_si_las_distribuciones_son_iguales():
    f = np.array([0.1, 0.2, 0.3, 0.4])
    assert psi(f, f) == 0.0


def test_psi_crece_con_el_cambio():
    ref = np.array([0.25, 0.25, 0.25, 0.25])
    assert psi(ref, np.array([0.7, 0.1, 0.1, 0.1])) > PSI_CRITICO


def test_lote_del_mismo_origen_da_verde(referencia):
    tabla, estado = evaluar_lote(referencia, lote_mismo_origen())
    assert estado == "verde", tabla[tabla["estado"] != "verde"]


def test_lote_con_drift_inyectado_da_rojo(referencia):
    tabla, estado = evaluar_lote(referencia, inyectar_drift(lote_mismo_origen()))
    assert estado == "rojo"
    rojas = set(tabla.loc[tabla["estado"] == "rojo", "variable"])
    assert {"AGE", "LIMIT_BAL", "EDUCATION", "PAY_0"} <= rojas   # las variables que se derivaron
    assert "SEX" not in rojas                                    # una que no se toco sigue verde


def test_cada_tipo_de_variable_usa_su_prueba(referencia):
    tabla, _ = evaluar_lote(referencia, lote_mismo_origen())
    assert (tabla.loc[tabla["tipo"] == "numerica", "prueba"] == "KS + PSI").all()
    assert (tabla.loc[tabla["tipo"] != "numerica", "prueba"] == "chi2 + PSI").all()
    assert (tabla["p_valor"].between(0, 1)).all()


def test_un_desplazamiento_pequeno_no_es_rojo(referencia):
    """Mover la edad 1 anio puede ser significativo (p < alfa) pero no tiene tamanio practico: nunca ROJO."""
    lote = lote_mismo_origen()
    lote["AGE"] = lote["AGE"] + 1
    tabla, _ = evaluar_lote(referencia, lote)
    assert tabla.set_index("variable").loc["AGE", "estado"] != "rojo"

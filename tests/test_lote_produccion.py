"""Puerta de calidad de datos: el lote que llega NO debe tener data drift.

    pytest tests/test_lote_produccion.py --lote monitoreo/lotes/lote_normal.csv    -> VERDE (pasa)
    pytest tests/test_lote_produccion.py --lote monitoreo/lotes/lote_derivado.csv  -> ROJO (falla)

Es la prueba que un pipeline de CT ejecutaria con cada lote nuevo: si falla, se
detiene el flujo y se investiga antes de seguir confiando en el modelo.
"""
import pandas as pd
import pytest

from monitoreo.data_drift import evaluar_lote, formatear, resumen


def test_el_lote_no_tiene_data_drift(request, referencia):
    ruta = request.config.getoption("--lote")
    lote = pd.read_csv(ruta)
    tabla, estado = evaluar_lote(referencia, lote)
    print(f"\nLote evaluado: {ruta} ({len(lote)} filas)\n{formatear(tabla)}\n{resumen(tabla, estado)}")
    if estado == "rojo":
        pytest.fail(f"DATA DRIFT en {ruta}: {resumen(tabla, estado)}")
    assert estado in ("verde", "amarillo")

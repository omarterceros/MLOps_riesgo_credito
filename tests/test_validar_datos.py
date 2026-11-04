"""Pruebas de la validacion de datos (pilar de datos)."""
import pandas as pd

from comun.datos import cargar_datos
from monitoreo.lotes import lote_mismo_origen
from monitoreo.validar_datos import validar


def test_el_dataset_del_repositorio_es_valido():
    assert validar(cargar_datos()) == []


def test_los_lotes_de_prueba_son_validos():
    assert validar(pd.read_csv("monitoreo/lotes/lote_normal.csv")) == []
    assert validar(pd.read_csv("monitoreo/lotes/lote_derivado.csv")) == []


def test_detecta_nulos_y_rangos():
    lote = lote_mismo_origen()
    lote.loc[:4, "AGE"] = None            # sensor roto: celdas vacias
    lote.loc[5:9, "SEX"] = 7              # codigo que no existe
    lote.loc[10:12, "PAY_AMT1"] = -100    # pago negativo
    problemas = validar(lote)
    assert any("celdas vacias" in p for p in problemas)
    assert any(p.startswith("SEX:") for p in problemas)
    assert any(p.startswith("PAY_AMT1:") for p in problemas)


def test_detecta_columnas_faltantes_y_pocas_filas():
    lote = lote_mismo_origen()
    assert "faltan columnas" in validar(lote.drop(columns=["LIMIT_BAL"]))[0]
    assert "filas" in validar(lote.head(20))[0]

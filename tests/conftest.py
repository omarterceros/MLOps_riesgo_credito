"""Configuracion comun de las pruebas.

Opcion de linea de comandos:
  --lote <csv>   lote que evalua tests/test_lote_produccion.py (por defecto el lote normal).
"""
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("CARGAR_MODELO_AL_INICIO", "0")   # las pruebas unitarias no necesitan MLflow

from comun.datos import particion  # noqa: E402

LOTE_POR_DEFECTO = RAIZ / "monitoreo" / "lotes" / "lote_normal.csv"


def pytest_addoption(parser):
    parser.addoption("--lote", default=str(LOTE_POR_DEFECTO), help="CSV del lote a evaluar")


@pytest.fixture(scope="session")
def datos_particionados():
    return particion()


@pytest.fixture(scope="session")
def referencia(datos_particionados):
    return datos_particionados[0]

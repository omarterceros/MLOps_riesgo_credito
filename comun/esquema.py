"""Esquema de las variables de entrada del modelo de riesgo crediticio.

Dataset: "Default of Credit Card Clients" (Yeh & Lien, 2009), UCI Machine Learning
Repository, publicado en OpenML con id 42477. 30.000 clientes de tarjetas de credito
de Taiwan y 23 variables de entrada. Objetivo: `mora` = 1 si el cliente no pago el
mes siguiente (default payment next month).

Este archivo es la UNICA fuente de verdad sobre las columnas: lo usan el
entrenamiento, el servicio de inferencia, la UI y las pruebas de drift.
"""

# Nombres originales del dataset UCI (X1..X23) y el tipo que usamos en el monitoreo.
#   numerica    -> prueba de Kolmogorov-Smirnov + PSI por deciles
#   categorica  -> prueba chi-cuadrado de homogeneidad + PSI por categoria
#   ordinal     -> se trata como categorica (pocos valores enteros con orden)
COLUMNAS = {
    "LIMIT_BAL": "numerica",   # limite de credito (NT$)
    "SEX": "categorica",       # 1 = hombre, 2 = mujer
    "EDUCATION": "categorica", # 1 = posgrado, 2 = universidad, 3 = secundaria, 4 = otros, 0/5/6 = desconocido
    "MARRIAGE": "categorica",  # 1 = casado, 2 = soltero, 3 = otros, 0 = desconocido
    "AGE": "numerica",         # edad en anios
    "PAY_0": "ordinal",        # estado de pago en septiembre: -2/-1/0 al dia, 1..9 = meses de atraso
    "PAY_2": "ordinal",        # agosto
    "PAY_3": "ordinal",        # julio
    "PAY_4": "ordinal",        # junio
    "PAY_5": "ordinal",        # mayo
    "PAY_6": "ordinal",        # abril
    "BILL_AMT1": "numerica",   # monto del estado de cuenta, septiembre
    "BILL_AMT2": "numerica",
    "BILL_AMT3": "numerica",
    "BILL_AMT4": "numerica",
    "BILL_AMT5": "numerica",
    "BILL_AMT6": "numerica",
    "PAY_AMT1": "numerica",    # monto pagado, septiembre
    "PAY_AMT2": "numerica",
    "PAY_AMT3": "numerica",
    "PAY_AMT4": "numerica",
    "PAY_AMT5": "numerica",
    "PAY_AMT6": "numerica",
}

OBJETIVO = "mora"
FEATURES = list(COLUMNAS)
NUMERICAS = [c for c, t in COLUMNAS.items() if t == "numerica"]
CATEGORICAS = [c for c, t in COLUMNAS.items() if t in ("categorica", "ordinal")]

SEMILLA = 42
TEST_SIZE = 0.2

# Dos solicitantes de ejemplo (los usan la API, la UI y las pruebas).
EJEMPLO_BAJO_RIESGO = {
    "LIMIT_BAL": 200000, "SEX": 2, "EDUCATION": 1, "MARRIAGE": 2, "AGE": 35,
    "PAY_0": -1, "PAY_2": -1, "PAY_3": -1, "PAY_4": -1, "PAY_5": -1, "PAY_6": -1,
    "BILL_AMT1": 3000, "BILL_AMT2": 2500, "BILL_AMT3": 2800, "BILL_AMT4": 2600,
    "BILL_AMT5": 2400, "BILL_AMT6": 2200,
    "PAY_AMT1": 3000, "PAY_AMT2": 2500, "PAY_AMT3": 2800, "PAY_AMT4": 2600,
    "PAY_AMT5": 2400, "PAY_AMT6": 2200,
}
EJEMPLO_ALTO_RIESGO = {
    "LIMIT_BAL": 20000, "SEX": 1, "EDUCATION": 3, "MARRIAGE": 1, "AGE": 45,
    "PAY_0": 3, "PAY_2": 2, "PAY_3": 2, "PAY_4": 2, "PAY_5": 2, "PAY_6": 2,
    "BILL_AMT1": 19500, "BILL_AMT2": 19000, "BILL_AMT3": 18800, "BILL_AMT4": 18500,
    "BILL_AMT5": 18200, "BILL_AMT6": 18000,
    "PAY_AMT1": 0, "PAY_AMT2": 0, "PAY_AMT3": 500, "PAY_AMT4": 0,
    "PAY_AMT5": 0, "PAY_AMT6": 0,
}

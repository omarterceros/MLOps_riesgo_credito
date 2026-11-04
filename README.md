# riesgo-credito-mlops

Proyecto final del módulo **ML-Ops y Puesta en Producción** (MIAV1E414, Maestría en IA, UAGRM).
Autor: **Omar Terceros Vallejos** (trabajo individual).

Un modelo que predice si un cliente de tarjeta de crédito **entrará en mora el mes siguiente**,
llevado desde el entrenamiento hasta un despliegue reproducible y observable:

| Fase | Qué hay | Dónde |
|---|---|---|
| 1. MLflow | 8 runs comparables, Model Registry con 2 versiones y alias `champion` / `baseline` | `entrenamiento/` |
| 2. Docker | Imagen propia del servicio de inferencia (FastAPI) que carga `models:/riesgo-credito@champion` | `Dockerfile`, `servicio/` |
| 3. Kubernetes | Namespace, Deployment con 3 réplicas, Service NodePort, probes, requests/limits | `k8s/` |
| 4. Drift | Pruebas automatizadas de data drift (KS, chi², PSI) y concept drift (lotes, gráfica, criterio de reentrenamiento) | `monitoreo/`, `tests/` |
| Extra | Interfaz web (HTML + JS en nginx) que consume la API a través del Service del clúster | `ui/`, `k8s/05-ui.yaml` |

El documento de arquitectura está en [ARQUITECTURA.md](ARQUITECTURA.md). El informe con
las evidencias (capturas y registros de terminal) está en `docs/`.

## Datos

*Default of Credit Card Clients* (Yeh & Lien, 2009), UCI Machine Learning Repository, publicado
en OpenML con id 42477: 30.000 clientes, 23 variables de entrada (límite de crédito, edad, sexo,
educación, estado civil, historial de pago de 6 meses, montos facturados y pagados) y la variable
objetivo `mora` (22,1 % de positivos). `datos/descargar.py` lo baja y lo guarda como
`datos/credito.csv` (MD5 `a4963930271a5ae46fb801ca0cba130b`); el archivo está versionado en el repositorio para que
el entrenamiento sea reproducible sin red.

División train/test: 80/20 estratificada por `mora`, semilla 42 (`comun/datos.py`). La misma
partición la usan el entrenamiento, el baseline del data drift y los lotes de concept drift.

## Cómo reproducirlo

Requisitos: Python 3.13, Docker Desktop con Kubernetes activado, `kubectl`. Todo lo demás se instala
en un entorno virtual con versiones fijadas (`requirements.txt`).

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt

# 1) Servidor de MLflow (tracking + registry + UI): http://localhost:5050   (dejarlo abierto)
.\scripts\mlflow_server.ps1

# 2) Fase 1: datos, 8 runs y registro del champion (otra terminal)
.\scripts\entrenar_y_registrar.ps1

# 3) Fases 2 y 3: imagen Docker + despliegue en Kubernetes
.\scripts\desplegar_k8s.ps1
#    API:  http://localhost:30080/docs      UI: http://localhost:30081

# 4) Fase 4: drift
.\.venv\Scripts\python monitoreo\lotes.py
.\.venv\Scripts\python monitoreo\data_drift.py --lote monitoreo\lotes\lote_normal.csv     # VERDE (exit 0)
.\.venv\Scripts\python monitoreo\data_drift.py --lote monitoreo\lotes\lote_derivado.csv   # ROJO  (exit 1)
.\.venv\Scripts\python monitoreo\concept_drift.py                                         # gráfica + alarma
.\.venv\Scripts\pytest                                                                     # 20 pruebas
.\.venv\Scripts\pytest tests\test_lote_produccion.py --lote monitoreo\lotes\lote_derivado.csv   # falla (rojo)
```

Solo con Docker, sin Kubernetes:

```powershell
docker build -t riesgo-credito-api:1.0 .
docker run --rm -p 8000:8000 riesgo-credito-api:1.0      # toma el modelo de http://host.docker.internal:5050
curl http://localhost:8000/health
```

## Estructura

```
riesgo-credito-mlops/
├── comun/            esquema.py (23 variables, tipos, ejemplos) · datos.py (carga, md5, partición)
├── datos/            descargar.py · credito.csv
├── entrenamiento/    entrenar.py (8 runs) · registrar.py (registry, alias) · modelo_desplegado.json
├── servicio/         api.py (FastAPI: /predecir, /health, /info, /esquema)
├── Dockerfile        imagen del servicio (python:3.13-slim, usuario sin privilegios)
├── k8s/              00 namespace · 01 configmap · 02 deployment · 03 service · 04-05 UI
├── ui/               index.html + nginx.conf (proxy /api/ -> Service)
├── monitoreo/        data_drift.py · lotes.py · concept_drift.py · lotes/*.csv
├── tests/            20 pruebas (API, data drift, concept drift, puerta del lote)
├── scripts/          mlflow_server · entrenar_y_registrar · desplegar_k8s · demo_balanceo
└── docs/             informe (Word), evidencia (capturas y salidas de terminal), herramientas
```

## Demostraciones de Kubernetes (fase 3)

```bash
kubectl get pods -n riesgo-credito -o wide                      # 3 réplicas Running
scripts/demo_balanceo.sh 12                                      # cada petición dice qué pod la atendió
kubectl delete pod -n riesgo-credito <uno de los pods>           # autorreparación: aparece otro
kubectl scale deployment riesgo-credito-api -n riesgo-credito --replicas=5
```

## Pruebas automatizadas

```
pytest                       -> 20 pruebas (API con modelo falso, detector de data drift, concept drift, lote normal)
pytest tests/test_lote_produccion.py --lote monitoreo/lotes/lote_derivado.csv  -> ROJO: la prueba falla
```

## Reparto de trabajo

Trabajo individual: todos los componentes (datos y MLflow, servicio y Docker, Kubernetes y UI,
monitoreo de drift, documentación) fueron construidos por Omar Terceros Vallejos. El historial
de commits (`git log`) muestra el avance por componente.

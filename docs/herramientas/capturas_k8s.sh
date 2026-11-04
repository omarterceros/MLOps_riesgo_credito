#!/usr/bin/env bash
# Ejecuta la demostracion completa de las fases 2 y 3 (Docker y Kubernetes) y guarda cada
# salida de terminal en docs/evidencia/salidas/NN-*.txt (despues se renderizan a PNG).
# Requisitos: servidor de MLflow con el champion registrado, imagen riesgo-credito-api:1.0.
# Uso: bash docs/herramientas/capturas_k8s.sh
set -u
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CAP="$AQUI/cap.sh"
NS=riesgo-credito
PY=".venv/Scripts/python.exe"
CUERPO='{"LIMIT_BAL":20000,"SEX":1,"EDUCATION":3,"MARRIAGE":1,"AGE":45,"PAY_0":3,"PAY_2":2,"PAY_3":2,"PAY_4":2,"PAY_5":2,"PAY_6":2,"BILL_AMT1":19500,"BILL_AMT2":19000,"BILL_AMT3":18800,"BILL_AMT4":18500,"BILL_AMT5":18200,"BILL_AMT6":18000,"PAY_AMT1":0,"PAY_AMT2":0,"PAY_AMT3":500,"PAY_AMT4":0,"PAY_AMT5":0,"PAY_AMT6":0}'

# --- Fase 2: Docker -------------------------------------------------------------------
bash "$CAP" 03-docker-build \
  "docker build -t riesgo-credito-api:1.0 ." \
  "docker images riesgo-credito-api"

bash "$CAP" 04-docker-run \
  "docker run -d --name credito-prueba -p 8001:8000 riesgo-credito-api:1.0" \
  "for i in \$(seq 1 30); do curl -s -o /dev/null -w '%{http_code}' http://localhost:8001/health | grep -q 200 && break; sleep 2; done; echo \"listo tras \$i intentos\"" \
  "curl -s http://localhost:8001/health" \
  "curl -s -X POST http://localhost:8001/predecir -H 'Content-Type: application/json' -d '$CUERPO'" \
  "docker logs credito-prueba 2>&1 | grep -E 'Modelo cargado|Uvicorn running'" \
  "docker rm -f credito-prueba"

# --- Fase 3: Kubernetes ---------------------------------------------------------------
bash "$CAP" 05-k8s-despliegue \
  "kubectl apply -f k8s/" \
  "kubectl rollout status deployment/riesgo-credito-api -n $NS --timeout=300s" \
  "kubectl get all -n $NS"

bash "$CAP" 06-k8s-replicas-running \
  "kubectl get pods -n $NS -l app=riesgo-credito-api -o wide" \
  "kubectl get endpointslices -n $NS -l kubernetes.io/service-name=riesgo-credito-api"

bash "$CAP" 07-k8s-balanceo \
  "bash scripts/demo_balanceo.sh 12"

bash "$CAP" 08-k8s-autorreparacion \
  "bash scripts/demo_autorreparacion.sh" \
  "sleep 20; kubectl get pods -n $NS -l app=riesgo-credito-api"

bash "$CAP" 09-k8s-escalado \
  "kubectl scale deployment riesgo-credito-api -n $NS --replicas=5" \
  "kubectl rollout status deployment/riesgo-credito-api -n $NS --timeout=300s" \
  "kubectl get pods -n $NS -l app=riesgo-credito-api" \
  "bash scripts/demo_balanceo.sh 10" \
  "kubectl scale deployment riesgo-credito-api -n $NS --replicas=3" \
  "sleep 8; kubectl get pods -n $NS -l app=riesgo-credito-api"

bash "$CAP" 10-k8s-trazabilidad \
  "curl -s http://localhost:30080/info | python -m json.tool" \
  "cat entrenamiento/modelo_desplegado.json"

bash "$CAP" 16-k8s-cambio-version \
  "bash scripts/demo_cambio_version.sh"

echo "Listo: salidas en docs/evidencia/salidas/"

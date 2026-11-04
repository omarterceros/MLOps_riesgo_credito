#!/usr/bin/env bash
# Demostracion de cambio de version en produccion SIN reconstruir la imagen:
# rollback del alias champion a la version 1 (baseline), rolling update, y vuelta a la version 2.
# Uso: scripts/demo_cambio_version.sh [namespace]
NS="${1:-riesgo-credito}"; URL="http://localhost:30080"
# python del entorno virtual del proyecto (tiene mlflow); se puede sobrescribir con PY=...
PY="${PY:-$(cd "$(dirname "$0")/.." && pwd)/.venv/Scripts/python.exe}"

version_servida() {   # reintenta: justo despues del rollout el Service puede devolver una respuesta vacia
  for _ in $(seq 1 15); do
    v=$(curl -s --max-time 5 "$URL/info" | sed -n -E 's/.*"version":([0-9]+).*"run_id":"([^"]+)".*/version \1, run \2/p')
    [ -n "$v" ] && { echo "$v"; return; }
    sleep 1
  done
  echo "sin respuesta"
}

echo "Antes:   /info -> $(version_servida)"
echo "--- rollback: alias champion -> version 1 ---"
$PY scripts/cambiar_champion.py 1
kubectl rollout restart deployment/riesgo-credito-api -n "$NS" >/dev/null
kubectl rollout status deployment/riesgo-credito-api -n "$NS" --timeout=300s
echo "Ahora:   /info -> $(version_servida)"
echo "--- promocion: alias champion -> version 2 ---"
$PY scripts/cambiar_champion.py 2
kubectl rollout restart deployment/riesgo-credito-api -n "$NS" >/dev/null
kubectl rollout status deployment/riesgo-credito-api -n "$NS" --timeout=300s
echo "Final:   /info -> $(version_servida)"
sleep 8
kubectl get pods -n "$NS" -l app=riesgo-credito-api

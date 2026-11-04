#!/usr/bin/env bash
# Demostracion de cambio de version en produccion SIN reconstruir la imagen:
# rollback del alias champion a la version 1 (baseline), rolling update, y vuelta a la version 2.
# Uso: scripts/demo_cambio_version.sh [namespace]
NS="${1:-riesgo-credito}"; URL="http://localhost:30080"
PY="${PY:-python}"

version_servida() { curl -s "$URL/info" | sed -E 's/.*"version":([0-9]+).*"run_id":"([^"]+)".*/version \1, run \2/'; }

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
kubectl get pods -n "$NS" -l app=riesgo-credito-api

#!/usr/bin/env bash
# Demostracion de autorreparacion CON trafico concurrente: un bucle en segundo plano manda
# peticiones al Service (hora, codigo HTTP y pod que atendio) mientras se elimina un pod.
# Uso: scripts/demo_autorreparacion.sh [namespace]
NS="${1:-riesgo-credito}"; URL="http://localhost:30080"
CUERPO='{"LIMIT_BAL":200000,"SEX":2,"EDUCATION":1,"MARRIAGE":2,"AGE":35,"PAY_0":-1,"PAY_2":-1,"PAY_3":-1,"PAY_4":-1,"PAY_5":-1,"PAY_6":-1,"BILL_AMT1":3000,"BILL_AMT2":2500,"BILL_AMT3":2800,"BILL_AMT4":2600,"BILL_AMT5":2400,"BILL_AMT6":2200,"PAY_AMT1":3000,"PAY_AMT2":2500,"PAY_AMT3":2800,"PAY_AMT4":2600,"PAY_AMT5":2400,"PAY_AMT6":2200}'

POD=$(kubectl get pods -n "$NS" -l app=riesgo-credito-api -o jsonpath='{.items[0].metadata.name}')
echo "Pods antes:"; kubectl get pods -n "$NS" -l app=riesgo-credito-api
echo "Se eliminara: $POD (mientras llegan peticiones cada 0,5 s)"

( for i in $(seq 1 24); do
    r=$(curl -s --max-time 5 -w $'\n%{http_code}' -X POST "$URL/predecir" -H 'Content-Type: application/json' -d "$CUERPO")
    code=${r##*$'\n'}; pod=$(printf '%s' "${r%$'\n'*}" | sed -E 's/.*"pod":"([^"]+)".*/\1/')
    printf '%s  peticion %2d  HTTP %s  -> %s\n' "$(date +%T)" "$i" "$code" "$pod"
    sleep 0.5
  done ) &
BUCLE=$!
sleep 2
echo "$(date +%T)  >>> kubectl delete pod $POD --wait=false"
kubectl delete pod "$POD" -n "$NS" --wait=false
sleep 3
kubectl get pods -n "$NS" -l app=riesgo-credito-api
wait "$BUCLE"
echo "Pods despues:"; kubectl get pods -n "$NS" -l app=riesgo-credito-api

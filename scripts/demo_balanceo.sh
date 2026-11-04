#!/usr/bin/env bash
# Manda N peticiones al Service y muestra que pod atendio cada una.
# Uso: scripts/demo_balanceo.sh [N] [URL]
N="${1:-12}"; URL="${2:-http://localhost:30080}"
CUERPO='{"LIMIT_BAL":200000,"SEX":2,"EDUCATION":1,"MARRIAGE":2,"AGE":35,"PAY_0":-1,"PAY_2":-1,"PAY_3":-1,"PAY_4":-1,"PAY_5":-1,"PAY_6":-1,"BILL_AMT1":3000,"BILL_AMT2":2500,"BILL_AMT3":2800,"BILL_AMT4":2600,"BILL_AMT5":2400,"BILL_AMT6":2200,"PAY_AMT1":3000,"PAY_AMT2":2500,"PAY_AMT3":2800,"PAY_AMT4":2600,"PAY_AMT5":2400,"PAY_AMT6":2200}'
for i in $(seq 1 "$N"); do
  respuesta=$(curl -s -X POST "$URL/predecir" -H 'Content-Type: application/json' -d "$CUERPO")
  pod=$(printf '%s' "$respuesta" | sed -E 's/.*"pod":"([^"]+)".*/\1/')
  prob=$(printf '%s' "$respuesta" | sed -E 's/.*"probabilidad_mora":([0-9.]+).*/\1/')
  printf 'peticion %2d -> %s  (probabilidad_mora=%s)\n' "$i" "$pod" "$prob"
done | tee /dev/stderr | awk '{c[$4]++} END {print "---"; for (p in c) print c[p], "peticiones atendidas por", p}'

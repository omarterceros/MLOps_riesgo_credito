#!/usr/bin/env bash
# Ejecuta uno o varios comandos, muestra su salida y la guarda en salidas/<nombre>.txt
# con el formato "$ comando" + salida, listo para render_terminal.py.
#
# Uso:  cap.sh <nombre-salida> "<comando 1>" ["<comando 2>" ...]
# Ej.:  cap.sh 01-nodo-ready "kubectl get nodes" "kubectl cluster-info"
set -u
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAIZ="$(cd "$BASE/.." && pwd)"   # raiz del repositorio: los comandos corren desde ahi
OUTDIR="$BASE/evidencia/salidas"
export PATH="$RAIZ/.venv/Scripts:$PATH"   # python y pytest del entorno virtual del proyecto
export PYTHONIOENCODING=utf-8 PYTHONWARNINGS=ignore MLFLOW_DISABLE_AGENT_HINT=1
mkdir -p "$OUTDIR"
name="$1"; shift
file="$OUTDIR/$name.txt"
: > "$file"
for cmd in "$@"; do
  printf '$ %s\n' "$cmd" | tee -a "$file"
  (cd "$RAIZ" && bash -c "$cmd") 2>&1 | tee -a "$file"
  printf '\n' | tee -a "$file"
done

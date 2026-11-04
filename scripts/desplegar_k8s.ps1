# Fases 2 y 3: construye la imagen y despliega todo en el Kubernetes de Docker Desktop.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
docker build -t riesgo-credito-api:1.0 .
kubectl apply -f k8s/
kubectl rollout status deployment/riesgo-credito-api -n riesgo-credito --timeout=300s
kubectl get pods -n riesgo-credito -o wide
Write-Host "API:  http://localhost:30080/docs"
Write-Host "UI:   http://localhost:30081"

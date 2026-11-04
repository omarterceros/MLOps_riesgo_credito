# Regenera k8s/04-ui-configmap.yaml a partir de ui/index.html y ui/nginx.conf
Set-Location (Split-Path $PSScriptRoot -Parent)
kubectl create configmap ui-archivos --namespace riesgo-credito `
    --from-file=index.html=ui/index.html --from-file=nginx.conf=ui/nginx.conf `
    --dry-run=client -o yaml | Out-File -Encoding utf8 k8s/04-ui-configmap.yaml
Write-Host "OK: k8s/04-ui-configmap.yaml"

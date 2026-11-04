# Publica el repositorio en GitHub (o GitLab) y completa el enlace en el README y el informe.
# Antes: crear en la web un repositorio VACIO (sin README ni .gitignore) y copiar su URL.
# Uso:  .\scripts\publicar_repo.ps1 -Url https://github.com/<usuario>/riesgo-credito-mlops
param([Parameter(Mandatory = $true)][string]$Url)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

# 1) Enlace en docs/REPO_URL.txt (lo lee build_informe.js) y en el README
Set-Content -Path docs\REPO_URL.txt -Value $Url -Encoding utf8 -NoNewline
$readme = Get-Content README.md -Raw -Encoding utf8
$readme = $readme -replace 'Repositorio: _\(pendiente de publicar;[^\r\n]*\)_', "Repositorio: $Url"
Set-Content -Path README.md -Value $readme -Encoding utf8 -NoNewline

# 2) Regenerar el informe Word con el enlace real
Push-Location docs\herramientas
node build_informe.js
Pop-Location

# 3) Commit y push de todo el historial
git add docs\REPO_URL.txt README.md docs\Informe_ProyectoFinal_MLOps.docx
git commit -m "docs: enlace al repositorio publicado"
if (-not (git remote | Select-String -Quiet '^origin$')) { git remote add origin $Url }
git push -u origin main
Write-Host "Publicado en $Url"

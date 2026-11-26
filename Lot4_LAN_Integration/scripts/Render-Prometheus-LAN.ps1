param([Parameter(Mandatory=$true)][string]$CentralIP,[Parameter(Mandatory=$true)][string]$FogAIP,[Parameter(Mandatory=$true)][string]$FogBIP,[Parameter(Mandatory=$true)][string]$FogCIP)
$ErrorActionPreference = 'Stop'
$Root = (Get-Location).Path
$Template = Join-Path $Root 'Lot4_LAN_Integration\monitoring\prometheus-lan.template.yml'
$Output = Join-Path $Root 'Lot4_LAN_Integration\monitoring\prometheus-lan.yml'
if (!(Test-Path $Template)) { throw "Template missing: $Template" }
$content = Get-Content $Template -Raw
$content = $content.Replace('${CENTRAL_LAN_IP}', $CentralIP).Replace('${FOG_A_IP}', $FogAIP).Replace('${FOG_B_IP}', $FogBIP).Replace('${FOG_C_IP}', $FogCIP)
Set-Content -Path $Output -Value $content -Encoding utf8
Write-Host "Prometheus LAN config rendered: $Output" -ForegroundColor Green

param([string]$EnvFile=".env")
$ErrorActionPreference="Stop"
$Compose=Join-Path $PSScriptRoot "..\compose\fog-node.compose.yml"
docker compose -f $Compose --env-file $EnvFile up -d
if ($LASTEXITCODE -ne 0) { throw "Fog node compose start failed" }
docker compose -f $Compose --env-file $EnvFile ps

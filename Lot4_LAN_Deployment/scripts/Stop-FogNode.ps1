param([string]$EnvFile=".env")
$ErrorActionPreference="Stop"
$Compose=Join-Path $PSScriptRoot "..\compose\fog-node.compose.yml"
docker compose -f $Compose --env-file $EnvFile down

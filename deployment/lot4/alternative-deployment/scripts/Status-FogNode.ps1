param([string]$EnvFile=".env", [int]$Port=8001)
$Compose=Join-Path $PSScriptRoot "..\compose\fog-node.compose.yml"
docker compose -f $Compose --env-file $EnvFile ps
try { Invoke-RestMethod "http://localhost:$Port/health" -TimeoutSec 3 | ConvertTo-Json -Depth 5 } catch { Write-Warning "Health endpoint failed: $($_.Exception.Message)" }

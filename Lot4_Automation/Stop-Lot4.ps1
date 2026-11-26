[CmdletBinding()]
param([Parameter(Mandatory=$true)][ValidateSet("central","fog-a","fog-b","fog-c","all-local-sim")][string]$Role)
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Bundle = Join-Path $RepoRoot "Lot4_LAN_Integration"
$MP2 = Join-Path $RepoRoot "Real-Time-Predictive-Maintenance"
switch ($Role) {
    "central" {
        $envFile=Join-Path $Bundle "central\.env"
        docker compose --env-file $envFile -f (Join-Path $MP2 "docker-compose.yml") -f (Join-Path $Bundle "central\docker-compose.lan-central.yml") stop scheduler mosquitto
    }
    {$_ -in "fog-a","fog-b","fog-c"} {
        $envFile=Join-Path $Bundle "fog-node\.env.fog"
        docker compose --env-file $envFile -f (Join-Path $Bundle "fog-node\docker-compose.fog-remote.yml") --profile $Role stop
    }
    "all-local-sim" {
        docker stop mp2-scheduler-lan-sim mp2-fog-a-lan-sim mp2-fog-b-lan-sim mp2-fog-c-lan-sim 2>$null
    }
}
Write-Host "Stop requested for $Role." -ForegroundColor Yellow

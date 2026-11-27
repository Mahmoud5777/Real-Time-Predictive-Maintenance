[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$CentralIP,
    [Parameter(Mandatory=$true)][string]$FogAIP,
    [Parameter(Mandatory=$true)][string]$FogBIP,
    [Parameter(Mandatory=$true)][string]$FogCIP
)
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$Bundle = Join-Path $RepoRoot "deployment\lot4\core"
foreach ($ip in @($CentralIP,$FogAIP,$FogBIP,$FogCIP)) {
    $parsed = $null
    if (-not [System.Net.IPAddress]::TryParse($ip,[ref]$parsed) -or $parsed.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) {
        throw "Invalid IPv4 address: $ip"
    }
}
@"
CENTRAL_LAN_IP=$CentralIP
FOG_A_IP=$FogAIP
FOG_B_IP=$FogBIP
FOG_C_IP=$FogCIP
"@ | Set-Content (Join-Path $Bundle "central\.env") -Encoding ascii

"CENTRAL_LAN_IP=$CentralIP" | Set-Content (Join-Path $Bundle "fog-node\.env.fog") -Encoding ascii
Write-Host "Lot4 IP configuration generated successfully." -ForegroundColor Green

[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][ValidateSet('central','fog-a','fog-b','fog-c')][string]$Role,
  [string]$TrustedRemote = 'LocalSubnet',
  [switch]$Apply
)
$script = Join-Path (Join-Path (Split-Path $PSScriptRoot -Parent) 'scripts') 'Set-Lot4-Firewall.ps1'
if (-not (Test-Path -LiteralPath $script)) { throw "Firewall script introuvable: $script" }
$mappedRole = switch ($Role) { 'central' {'Central'} 'fog-a' {'FogA'} 'fog-b' {'FogB'} 'fog-c' {'FogC'} }
& $script -Role $mappedRole -TrustedRemote $TrustedRemote -Apply:$Apply

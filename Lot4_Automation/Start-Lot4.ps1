[CmdletBinding()]
param([Parameter(Mandatory=$true)][ValidateSet("central","fog-a","fog-b","fog-c")][string]$Role)
& (Join-Path $PSScriptRoot "Deploy-Lot4.ps1") -Role $Role
if ($LASTEXITCODE -ne 0) { throw "Deployment failed." }

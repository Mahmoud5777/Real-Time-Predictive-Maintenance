[CmdletBinding(SupportsShouldProcess=$true)]
param(
  [Parameter(Mandatory=$true)][ValidateSet('Central','FogA','FogB','FogC')][string]$Role,
  [string]$TrustedRemote = 'LocalSubnet',
  [switch]$Apply
)
$ErrorActionPreference = 'Stop'
if ($TrustedRemote -ne 'LocalSubnet' -and $TrustedRemote -notmatch '^(\d{1,3}\.){3}\d{1,3}(/\d{1,2})?(,(\d{1,3}\.){3}\d{1,3}(/\d{1,2})?)*$') {
  throw 'TrustedRemote doit etre LocalSubnet ou une liste IPv4/CIDR separee par des virgules.'
}
$rules = switch ($Role) {
  'Central' { @(@{Name='Lot4 MQTT LAN';Port=1883},@{Name='Lot4 Scheduler API';Port=8100},@{Name='Lot4 MP4 Dashboard';Port=3001}) }
  'FogA' { @(@{Name='Lot4 Fog A API';Port=8101}) }
  'FogB' { @(@{Name='Lot4 Fog B API';Port=8102}) }
  'FogC' { @(@{Name='Lot4 Fog C API';Port=8103}) }
}
Write-Host "Regles prevues pour $Role depuis $TrustedRemote : $((($rules | ForEach-Object { $_.Port }) -join ', '))"
if (-not $Apply) { Write-Host 'Aucune modification effectuee. Relancer avec -Apply dans une console admin pour appliquer.' -ForegroundColor Yellow; return }
foreach ($rule in $rules) {
  if (-not $PSCmdlet.ShouldProcess("TCP $($rule.Port)","Creer la regle de pare-feu '$($rule.Name)'")) { continue }
  Get-NetFirewallRule -DisplayName $rule.Name -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction Stop
  New-NetFirewallRule -DisplayName $rule.Name -Direction Inbound -Action Allow -Protocol TCP -LocalPort $rule.Port -RemoteAddress $TrustedRemote -Profile Private | Out-Null
}
Write-Host "Regles Lot 4 appliquees pour le role $Role." -ForegroundColor Green

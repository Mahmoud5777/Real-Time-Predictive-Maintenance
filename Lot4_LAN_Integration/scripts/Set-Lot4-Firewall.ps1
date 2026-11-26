# Run elevated on the respective PC. Restrict scope to trusted local network/central IP.
param(
 [ValidateSet("Central","FogA","FogB","FogC")][string]$Role,
 [string]$TrustedRemote = "LocalSubnet"
)
$rules = switch ($Role) {
 "Central" { @(@{Name="Lot4 MQTT LAN"; Port=1883}, @{Name="Lot4 Scheduler API";Port=8100}) }
 "FogA" { @(@{Name="Lot4 Fog A API";Port=8101}) }
 "FogB" { @(@{Name="Lot4 Fog B API";Port=8102}) }
 "FogC" { @(@{Name="Lot4 Fog C API";Port=8103}) }
}
foreach($r in $rules) {
  $ruleName = $r.Name
  Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
  New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $r.Port -RemoteAddress $TrustedRemote -Profile Private
}
Write-Host "Firewall rules created for role $Role (scope $TrustedRemote)." -ForegroundColor Green

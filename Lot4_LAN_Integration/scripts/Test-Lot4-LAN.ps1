[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$CentralIP,
  [Parameter(Mandatory=$true)][string]$FogAIP,
  [Parameter(Mandatory=$true)][string]$FogBIP,
  [Parameter(Mandatory=$true)][string]$FogCIP
)
$ErrorActionPreference = 'Continue'
$checks = New-Object System.Collections.Generic.List[object]
foreach ($entry in @(@('CentralIP',$CentralIP),@('FogAIP',$FogAIP),@('FogBIP',$FogBIP),@('FogCIP',$FogCIP))) {
  $parsed = $null
  if (-not [System.Net.IPAddress]::TryParse($entry[1],[ref]$parsed) -or $parsed.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { throw "$($entry[0]) doit etre une IPv4 valide: $($entry[1])" }
}
$endpoints = @(
  @{Name='Scheduler MP2';Url="http://${CentralIP}:8100/health"},
  @{Name='Fog A';Url="http://${FogAIP}:8101/health"},
  @{Name='Fog B';Url="http://${FogBIP}:8102/health"},
  @{Name='Fog C';Url="http://${FogCIP}:8103/health"}
)
foreach ($endpoint in $endpoints) {
  try {
    $response = Invoke-RestMethod -Uri $endpoint.Url -TimeoutSec 5
    $checks.Add([pscustomobject]@{Name=$endpoint.Name;Check='HTTP /health';Result='PASS';Detail=$endpoint.Url})
  } catch { $checks.Add([pscustomobject]@{Name=$endpoint.Name;Check='HTTP /health';Result='FAIL';Detail=$_.Exception.Message}) }
}
foreach ($entry in @(@('MQTT central',$CentralIP,1883),@('Scheduler MP2',$CentralIP,8100),@('Fog A',$FogAIP,8101),@('Fog B',$FogBIP,8102),@('Fog C',$FogCIP,8103))) {
  $tcp = Test-NetConnection -ComputerName $entry[1] -Port $entry[2] -InformationLevel Quiet -WarningAction SilentlyContinue
  $checks.Add([pscustomobject]@{Name=$entry[0];Check="TCP $($entry[2])";Result=$(if($tcp){'PASS'}else{'FAIL'});Detail="$($entry[1]):$($entry[2])"})
}
$checks | Format-Table -AutoSize
if (@($checks | Where-Object Result -eq 'FAIL').Count) { exit 1 }
Write-Host 'Connectivite LAN confirmee. Aucune tache metier MP2 n a ete executee.' -ForegroundColor Green

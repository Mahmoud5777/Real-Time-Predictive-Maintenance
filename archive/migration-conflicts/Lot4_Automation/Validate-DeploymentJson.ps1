[CmdletBinding()]
param([string]$ConfigPath = (Join-Path $PSScriptRoot 'config\deployment.json'))
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) { throw "Configuration JSON introuvable: $ConfigPath" }
try { $cfg = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json -ErrorAction Stop } catch { throw "JSON invalide: $($_.Exception.Message)" }
foreach ($key in @('schemaVersion','project','network','centralIp','fogAIp','fogBIp','fogCIp','addressesConfirmed','schedulerPort','fogPorts','roles','monitoring','deployment')) {
  if ($null -eq $cfg.PSObject.Properties[$key]) { throw "Clé JSON obligatoire absente: $key" }
}
if ($cfg.schemaVersion -ne 1) { throw "schemaVersion non supportée: $($cfg.schemaVersion)" }
if ($cfg.addressesConfirmed -isnot [bool]) { throw 'addressesConfirmed doit être un booléen.' }
$cidr = [string]$cfg.network.subnetCidr
if ($cidr -notmatch '^((?:\d{1,3}\.){3}\d{1,3})/(\d|[12]\d|3[0-2])$') { throw "network.subnetCidr invalide: $cidr" }
$networkIp = $null
if (-not [Net.IPAddress]::TryParse($Matches[1], [ref]$networkIp) -or $networkIp.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork) { throw "Sous-réseau IPv4 invalide: $cidr" }
$prefix = [int]$Matches[2]
$networkBytes = $networkIp.GetAddressBytes()
$ips = [ordered]@{ central=$cfg.centralIp; 'fog-a'=$cfg.fogAIp; 'fog-b'=$cfg.fogBIp; 'fog-c'=$cfg.fogCIp }
$seen = @{}
foreach ($entry in $ips.GetEnumerator()) {
  $parsed = $null
  if (-not [Net.IPAddress]::TryParse([string]$entry.Value,[ref]$parsed) -or $parsed.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork) { throw "Adresse IPv4 invalide pour $($entry.Key): $($entry.Value)" }
  if ($seen.ContainsKey($parsed.ToString())) { throw "Adresse IP dupliquée: $($parsed.ToString())" }
  $seen[$parsed.ToString()] = $entry.Key
  $bytes = $parsed.GetAddressBytes(); $full = [math]::Floor($prefix / 8); $rem = $prefix % 8
  for ($i=0; $i -lt $full; $i++) { if ($bytes[$i] -ne $networkBytes[$i]) { throw "$($entry.Key) ($parsed) est hors du sous-réseau $cidr" } }
  if ($rem) {
    $mask = 256 - (1 -shl (8-$rem))
    if (($bytes[$full] -band $mask) -ne ($networkBytes[$full] -band $mask)) { throw "$($entry.Key) ($parsed) est hors du sous-réseau $cidr" }
  }
}
function Assert-Port([string]$Name, $Value) { $n=0; if (-not [int]::TryParse([string]$Value,[ref]$n) -or $n -lt 1 -or $n -gt 65535) { throw "Port invalide pour ${Name}: $Value" } }
$ports = @([pscustomobject]@{Name='mqtt';Value=$cfg.network.mqttPort},[pscustomobject]@{Name='scheduler';Value=$cfg.schedulerPort})
foreach ($r in @('fog-a','fog-b','fog-c')) { if ($null -eq $cfg.fogPorts.PSObject.Properties[$r]) { throw "Port absent pour $r" }; $ports += [pscustomobject]@{Name=$r;Value=$cfg.fogPorts.$r} }
foreach ($key in @('prometheusPort','grafanaPort','blackboxPort')) { if ($cfg.monitoring.enabled) { if ($null -eq $cfg.monitoring.PSObject.Properties[$key]) { throw "Port monitoring absent: $key" }; $ports += [pscustomobject]@{Name=$key;Value=$cfg.monitoring.$key} } }
foreach ($p in $ports) { Assert-Port $p.Name $p.Value }
if (($ports | Group-Object { [int]$_.Value } | Where-Object Count -gt 1).Count) { throw 'Deux services utilisent le même port hôte.' }
foreach ($role in @('central','fog-a','fog-b','fog-c')) { if ($null -eq $cfg.roles.PSObject.Properties[$role]) { throw "Rôle absent: $role" } }
if ($cfg.roles.central.host -ne 'central' -or $cfg.roles.'fog-a'.host -ne 'fog-a' -or $cfg.roles.'fog-b'.host -ne 'fog-b' -or $cfg.roles.'fog-c'.host -ne 'fog-c' -or $cfg.roles.'fog-a'.fogId -ne 'fog-a' -or $cfg.roles.'fog-b'.fogId -ne 'fog-b' -or $cfg.roles.'fog-c'.fogId -ne 'fog-c') { throw 'Les hôtes/fogId des rôles ne correspondent pas aux rôles Lot 4.' }
if ([string]::IsNullOrWhiteSpace([string]$cfg.deployment.dockerComposeProjectPrefix) -or $cfg.deployment.dockerComposeProjectPrefix -notmatch '^[a-z0-9][a-z0-9_-]*$') { throw 'deployment.dockerComposeProjectPrefix invalide.' }
if ($cfg.deployment.automaticRemoteExecution -ne $false) { throw 'automaticRemoteExecution doit rester false.' }
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$requiredFiles = @('Real-Time-Predictive-Maintenance\Dockerfile','Real-Time-Predictive-Maintenance\mosquitto\mosquitto.conf','Lot4_LAN_Integration\monitoring\prometheus-lan.template.yml','Lot4_LAN_Integration\monitoring\alert_rules.yml','Lot4_LAN_Integration\monitoring\blackbox.yml')
foreach ($relative in $requiredFiles) { if (-not (Test-Path -LiteralPath (Join-Path $repoRoot $relative) -PathType Leaf)) { throw "Dépendance requise absente: $relative" } }
$requiredDirs = @('mp1-simulator','Lot4_LAN_Integration\monitoring\grafana\provisioning\dashboards','Lot4_LAN_Integration\monitoring\grafana\provisioning\datasources')
foreach ($relative in $requiredDirs) { if (-not (Test-Path -LiteralPath (Join-Path $repoRoot $relative) -PathType Container)) { throw "Dépendance requise absente: $relative" } }
Write-Host 'deployment.json: VALID' -ForegroundColor Green

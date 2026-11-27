[CmdletBinding()]
param(
  [string]$CentralIP,
  [string]$FogAIP,
  [string]$FogBIP,
  [string]$FogCIP,
  [string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')).Path,
  [string]$OutputPath,
  [string]$ConfigPath
)
$ErrorActionPreference = 'Stop'
$template = Join-Path $RepositoryRoot 'deployment\lot4\core\monitoring\prometheus-lan.template.yml'
if (-not (Test-Path -LiteralPath $template)) { throw "Template Prometheus introuvable: $template" }
if (-not $ConfigPath) {
  $localConfig = Join-Path $RepositoryRoot 'deployment\lot4\core\central\.env'
  if (Test-Path -LiteralPath $localConfig) { $ConfigPath = $localConfig }
  else { $ConfigPath = Join-Path $RepositoryRoot 'deployment\lot4\core\central\.env.central.example' }
}
$settings = @{}
foreach ($line in Get-Content -LiteralPath $ConfigPath) {
  if ($line -match '^\s*([A-Z_]+)\s*=\s*(.*?)\s*$') { $settings[$matches[1]] = $matches[2] }
}
$requiredKeys = @('CENTRAL_LAN_IP','FOG_A_IP','FOG_B_IP','FOG_C_IP')
if (@($requiredKeys | Where-Object { -not $settings.ContainsKey($_) -or -not $settings[$_] }).Count) {
  throw "Configuration incomplete dans $ConfigPath. Renseigner les quatre IPv4 ou passer -ConfigPath central\.env.central.example pour un rendu d'exemple explicite."
}
if (-not $CentralIP) { $CentralIP = $settings['CENTRAL_LAN_IP'] }
if (-not $FogAIP) { $FogAIP = $settings['FOG_A_IP'] }
if (-not $FogBIP) { $FogBIP = $settings['FOG_B_IP'] }
if (-not $FogCIP) { $FogCIP = $settings['FOG_C_IP'] }
if (-not $CentralIP -or -not $FogAIP -or -not $FogBIP -or -not $FogCIP) { throw "Les adresses CENTRAL_LAN_IP et FOG_A_IP/FOG_B_IP/FOG_C_IP manquent dans $ConfigPath." }
foreach ($entry in @(@('CentralIP',$CentralIP),@('FogAIP',$FogAIP),@('FogBIP',$FogBIP),@('FogCIP',$FogCIP))) {
  $parsed = $null
  if (-not [System.Net.IPAddress]::TryParse($entry[1], [ref]$parsed) -or $parsed.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) {
    throw "$($entry[0]) doit etre une adresse IPv4 valide: $($entry[1])"
  }
}
if (-not $OutputPath) { $OutputPath = Join-Path $RepositoryRoot 'deployment\lot4\core\monitoring\prometheus-lan.yml' }
$content = Get-Content -LiteralPath $template -Raw
$content = $content.Replace('${CENTRAL_LAN_IP}', $CentralIP).Replace('${FOG_A_IP}', $FogAIP).Replace('${FOG_B_IP}', $FogBIP).Replace('${FOG_C_IP}', $FogCIP)
if ($content -match '\$\{[A-Z_]+\}') { throw 'Le rendu Prometheus contient encore des variables non remplacees.' }
$content = $content.TrimEnd([char[]]@("`r","`n"))
Set-Content -LiteralPath $OutputPath -Value $content -Encoding UTF8
Write-Host "Configuration Prometheus LAN generee: $OutputPath" -ForegroundColor Green

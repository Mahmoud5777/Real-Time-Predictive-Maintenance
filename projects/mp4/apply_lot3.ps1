$ErrorActionPreference = "Stop"

$Frontend = Join-Path $PSScriptRoot "frontend"
$AppPath = Join-Path $Frontend "src\App.jsx"
$CssPath = Join-Path $Frontend "src\index.css"
$ComponentPath = Join-Path $Frontend "src\components\AnalyticsPanel.jsx"

foreach ($File in @($AppPath, $CssPath, $ComponentPath)) {
    if (-not (Test-Path $File)) {
        throw "Fichier introuvable : $File"
    }
}

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
Copy-Item $AppPath "$AppPath.backup-$Timestamp"
Copy-Item $CssPath "$CssPath.backup-$Timestamp"

$App = Get-Content $AppPath -Raw

$Import = 'import AnalyticsPanel from "./components/AnalyticsPanel";'
if (-not $App.Contains($Import)) {
    $Anchor = 'import TaskEventsPanel from "./components/TaskEventsPanel";'
    if (-not $App.Contains($Anchor)) {
        throw "Import TaskEventsPanel introuvable."
    }
    $App = $App.Replace($Anchor, $Anchor + "`r`n" + $Import)
}

$Style = 'import "./analytics.css";'
if (-not $App.Contains($Style)) {
    $Anchor = 'import "./App.css";'
    if (-not $App.Contains($Anchor)) {
        throw "Import App.css introuvable."
    }
    $App = $App.Replace($Anchor, $Anchor + "`r`n" + $Style)
}

if (-not $App.Contains("<AnalyticsPanel />")) {
    $Pattern = '(?m)^([ \t]*)<section className="overview-section">\s*\r?\n[ \t]*<div className="overview-section-heading">\s*\r?\n[ \t]*<h2>État des zones industrielles</h2>'

    if (-not [regex]::IsMatch($App, $Pattern)) {
        throw "Section État des zones industrielles introuvable."
    }

    $App = [regex]::Replace(
        $App,
        $Pattern,
        '$1<AnalyticsPanel />' + "`r`n`r`n" + '$1<section className="overview-section">' + "`r`n" + '$1  <div className="overview-section-heading">' + "`r`n" + '$1    <h2>État des zones industrielles</h2>',
        1
    )
}

Set-Content -Path $AppPath -Value $App -Encoding utf8

$Css = Get-Content $CssPath -Raw
$RootPattern = '(?s)#root\s*\{.*?\n\}'

if (-not [regex]::IsMatch($Css, $RootPattern)) {
    throw "Bloc CSS #root introuvable."
}

$RootCss = "#root {`r`n  width: 100%;`r`n  max-width: none;`r`n  margin: 0;`r`n  text-align: left;`r`n  border: 0;`r`n  min-height: 100vh;`r`n  display: block;`r`n  box-sizing: border-box;`r`n}"

$Css = [regex]::Replace($Css, $RootPattern, $RootCss, 1)
Set-Content -Path $CssPath -Value $Css -Encoding utf8

if (-not (Select-String -Path $AppPath -SimpleMatch $Import -Quiet)) {
    throw "Import Analytics absent après modification."
}
if (-not (Select-String -Path $AppPath -SimpleMatch "<AnalyticsPanel />" -Quiet)) {
    throw "Composant Analytics absent après modification."
}

Write-Host "Intégration Analytics effectuée." -ForegroundColor Green
Write-Host "Sauvegardes créées : App.jsx et index.css." -ForegroundColor Green

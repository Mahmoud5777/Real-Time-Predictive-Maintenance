# Lot4 Automation Pack

Pack de prÃ©paration et de dÃ©ploiement pour l'architecture 4 PC :
Central + Fog A + Fog B + Fog C. Il rÃ©utilise les fichiers Compose MP2/Lot4 existants et ne modifie pas les tests fonctionnels MP2.

## PrÃ©requis sur chaque PC
- Windows PowerShell 5.1 ou PowerShell 7.
- Docker Desktop installÃ© et dÃ©marrÃ© (`docker info` doit rÃ©ussir).
- Copie complÃ¨te du dÃ©pÃ´t dans la mÃªme structure de dossiers.
- Les PC doivent pouvoir communiquer sur le mÃªme LAN/VPN privÃ©.
- Les ports autorisÃ©s par le pare-feu Windows.

## PrÃ©paration maintenant (sans les 4 PC)
1. DÃ©compresser `deployment\lot4\automation` Ã  la racine du dÃ©pÃ´t `Collaborative-Fog-Computing`.
2. VÃ©rifier les scripts PowerShell :
   ```powershell
   Get-ChildItem .\deployment\lot4\automation\*.ps1 | ForEach-Object {
     $e=$null
     [System.Management.Automation.Language.Parser]::ParseFile($_.FullName,[ref]$null,[ref]$e) | Out-Null
     if($e.Count){$e; throw "Syntax error: $($_.Name)"}
     "PASS: $($_.Name)"
   }
   ```
3. ExÃ©cuter `Install-Lot4.ps1 -Role central` et pour prÃ©parer un Fog `-Role fog-a`, `fog-b` ou `fog-c`. Cette prÃ©paration ne dÃ©marre pas les conteneurs.

## Jour du dÃ©ploiement
1. RÃ©server des adresses IPv4 stables sur le routeur ou configurer des IP statiques.
2. Depuis la racine du dÃ©pÃ´t, sur une machine d'administration, gÃ©nÃ©rer les fichiers d'environnement :
   ```powershell
   .\deployment\lot4\automation\Set-Lot4Config.ps1 -CentralIP 192.168.1.10 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192.168.1.13
   ```
   Remplacer les exemples par les vraies IP. Copier `central\.env` uniquement sur Central et `fog-node\.env.fog` sur les trois Fog (ou exÃ©cuter le script sur chaque clone).
3. Sur Central :
   ```powershell
   .\deployment\lot4\automation\Install-Lot4.ps1 -Role central
   .\deployment\lot4\automation\Configure-Firewall.ps1 -Role central
   .\deployment\lot4\automation\Deploy-Lot4.ps1 -Role central
   ```
4. Sur chaque Fog :
   ```powershell
   .\deployment\lot4\automation\Install-Lot4.ps1 -Role fog-a
   .\deployment\lot4\automation\Configure-Firewall.ps1 -Role fog-a
   .\deployment\lot4\automation\Deploy-Lot4.ps1 -Role fog-a
   ```
   Adapter le rÃ´le sur les deux autres machines.
5. Depuis Central :
   ```powershell
   .\deployment\lot4\automation\Register-FogNodes.ps1 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192.168.1.13
   .\deployment\lot4\automation\Test-Lot4.ps1 -CentralIP 192.168.1.10 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192.168.1.13
   ```

## GÃ©nÃ©rer les cibles Prometheus
```powershell
.\\deployment\lot4\automation\\Configure-Monitoring.ps1 -CentralIP 192.168.1.10 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192.168.1.13
```
Cette commande gÃ©nÃ¨re le fichier de cibles LAN. Le dÃ©ploiement Prometheus et la disponibilitÃ© de `/metrics` restent Ã  confirmer.

## ArrÃªt
- Central : `.\deployment\lot4\automation\Stop-Lot4.ps1 -Role central`
- Chaque Fog : `.\deployment\lot4\automation\Stop-Lot4.ps1 -Role fog-a` (adapter le rÃ´le).

## Limites connues Ã  valider
- Le script Register-FogNodes vÃ©rifie les endpoints `/health`; il ne crÃ©e pas une inscription persistante cÃ´tÃ© Scheduler si l'application MP2 ne fournit pas cette API. Les URL des Fog sont injectÃ©es dans le Scheduler via l'overlay Compose.
- L'API Scheduler et Fog doit rÃ©ellement exposer `/health` (dÃ©jÃ  observÃ© en simulation pour Scheduler et les Fog).
- Le template Prometheus existant contient des cibles HTTP ; confirmer que les applications exposent `/metrics` avant d'activer ces jobs. Le template est une configuration, pas un dÃ©ploiement Prometheus complet.
- Le Mosquitto de base utilise une configuration permissive. Limiter le pare-feu au rÃ©seau privÃ© de confiance et ne jamais publier MQTT sur Internet.
- Docker Desktop, Ã©lÃ©vation administrateur et Ã©ventuel redÃ©marrage Windows ne peuvent pas Ãªtre entiÃ¨rement automatisÃ©s par ces scripts.

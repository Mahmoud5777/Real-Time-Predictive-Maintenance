# Lot4 Automation Pack

Pack de préparation et de déploiement pour l'architecture 4 PC :
Central + Fog A + Fog B + Fog C. Il réutilise les fichiers Compose MP2/Lot4 existants et ne modifie pas les tests fonctionnels MP2.

## Prérequis sur chaque PC
- Windows PowerShell 5.1 ou PowerShell 7.
- Docker Desktop installé et démarré (`docker info` doit réussir).
- Copie complète du dépôt dans la même structure de dossiers.
- Les PC doivent pouvoir communiquer sur le même LAN/VPN privé.
- Les ports autorisés par le pare-feu Windows.

## Préparation maintenant (sans les 4 PC)
1. Décompresser `Lot4_Automation` à la racine du dépôt `Collaborative-Fog-Computing`.
2. Vérifier les scripts PowerShell :
   ```powershell
   Get-ChildItem .\Lot4_Automation\*.ps1 | ForEach-Object {
     $e=$null
     [System.Management.Automation.Language.Parser]::ParseFile($_.FullName,[ref]$null,[ref]$e) | Out-Null
     if($e.Count){$e; throw "Syntax error: $($_.Name)"}
     "PASS: $($_.Name)"
   }
   ```
3. Exécuter `Install-Lot4.ps1 -Role central` et pour préparer un Fog `-Role fog-a`, `fog-b` ou `fog-c`. Cette préparation ne démarre pas les conteneurs.

## Jour du déploiement
1. Réserver des adresses IPv4 stables sur le routeur ou configurer des IP statiques.
2. Depuis la racine du dépôt, sur une machine d'administration, générer les fichiers d'environnement :
   ```powershell
   .\Lot4_Automation\Set-Lot4Config.ps1 -CentralIP 192.168.1.10 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192.168.1.13
   ```
   Remplacer les exemples par les vraies IP. Copier `central\.env` uniquement sur Central et `fog-node\.env.fog` sur les trois Fog (ou exécuter le script sur chaque clone).
3. Sur Central :
   ```powershell
   .\Lot4_Automation\Install-Lot4.ps1 -Role central
   .\Lot4_Automation\Configure-Firewall.ps1 -Role central
   .\Lot4_Automation\Deploy-Lot4.ps1 -Role central
   ```
4. Sur chaque Fog :
   ```powershell
   .\Lot4_Automation\Install-Lot4.ps1 -Role fog-a
   .\Lot4_Automation\Configure-Firewall.ps1 -Role fog-a
   .\Lot4_Automation\Deploy-Lot4.ps1 -Role fog-a
   ```
   Adapter le rôle sur les deux autres machines.
5. Depuis Central :
   ```powershell
   .\Lot4_Automation\Register-FogNodes.ps1 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192.168.1.13
   .\Lot4_Automation\Test-Lot4.ps1 -CentralIP 192.168.1.10 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192.168.1.13
   ```

## Générer les cibles Prometheus
```powershell
.\\Lot4_Automation\\Configure-Monitoring.ps1 -CentralIP 192.168.1.10 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192.168.1.13
```
Cette commande génère le fichier de cibles LAN. Le déploiement Prometheus et la disponibilité de `/metrics` restent à confirmer.

## Arrêt
- Central : `.\Lot4_Automation\Stop-Lot4.ps1 -Role central`
- Chaque Fog : `.\Lot4_Automation\Stop-Lot4.ps1 -Role fog-a` (adapter le rôle).

## Limites connues à valider
- Le script Register-FogNodes vérifie les endpoints `/health`; il ne crée pas une inscription persistante côté Scheduler si l'application MP2 ne fournit pas cette API. Les URL des Fog sont injectées dans le Scheduler via l'overlay Compose.
- L'API Scheduler et Fog doit réellement exposer `/health` (déjà observé en simulation pour Scheduler et les Fog).
- Le template Prometheus existant contient des cibles HTTP ; confirmer que les applications exposent `/metrics` avant d'activer ces jobs. Le template est une configuration, pas un déploiement Prometheus complet.
- Le Mosquitto de base utilise une configuration permissive. Limiter le pare-feu au réseau privé de confiance et ne jamais publier MQTT sur Internet.
- Docker Desktop, élévation administrateur et éventuel redémarrage Windows ne peuvent pas être entièrement automatisés par ces scripts.

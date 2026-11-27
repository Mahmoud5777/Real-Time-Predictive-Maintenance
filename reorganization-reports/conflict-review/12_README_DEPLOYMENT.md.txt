CONFLICT 12
Source: C:\Users\ayedi\Desktop\projets\Collaborative-Fog-Computing\Lot4_Automation\README_DEPLOYMENT.md
Target: C:\Users\ayedi\Desktop\projets\Collaborative-Fog-Computing\deployment\lot4\automation\README_DEPLOYMENT.md

Source SHA256: 2FA54F6A13C5C00E92A8B90D62DE99E6D2B59E91300A32A17E1299AE9086C5E8
Target SHA256: A9C2AD194664EB971806D3B6B07CB5708E9903E99BC52426CA48D6DD59787ADA

git : warning: in the working copy of 
'C:\Users\ayedi\Desktop\projets\Collaborative-Fog-Computing\Lot4_Automation\README_DEPLOYMENT.md', LF will be replaced by 
CRLF the next time Git touches it
Au caractère Ligne:34 : 21
+ ...          $Diff = git diff --no-index -- $SourceFile $Destination 2>&1
+                      ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (warning: in the... Git touches it:String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 
warning: in the working copy of 
'C:\Users\ayedi\Desktop\projets\Collaborative-Fog-Computing\deployment\lot4\automation\README_DEPLOYMENT.md', LF will be 
replaced by CRLF the next time Git touches it
diff --git "a/C:\\Users\\ayedi\\Desktop\\projets\\Collaborative-Fog-Computing\\Lot4_Automation\\README_DEPLOYMENT.md" "b/C:\\Users\\ayedi\\Desktop\\projets\\Collaborative-Fog-Computing\\deployment\\lot4\\automation\\README_DEPLOYMENT.md"
index 9c0152c..bd68ee0 100644
--- "a/C:\\Users\\ayedi\\Desktop\\projets\\Collaborative-Fog-Computing\\Lot4_Automation\\README_DEPLOYMENT.md"
+++ "b/C:\\Users\\ayedi\\Desktop\\projets\\Collaborative-Fog-Computing\\deployment\\lot4\\automation\\README_DEPLOYMENT.md"
@@ -1,67 +1,67 @@
-# Lot4 Automation Pack
+´╗┐# Lot4 Automation Pack
 
-Pack de pr├®paration et de d├®ploiement pour l'architecture 4 PC :
-Central + Fog A + Fog B + Fog C. Il r├®utilise les fichiers Compose MP2/Lot4 existants et ne modifie pas les tests fonctionnels MP2.
+Pack de pr├â┬®paration et de d├â┬®ploiement pour l'architecture 4 PC :
+Central + Fog A + Fog B + Fog C. Il r├â┬®utilise les fichiers Compose MP2/Lot4 existants et ne modifie pas les tests fonctionnels MP2.
 
-## Pr├®requis sur chaque PC
+## Pr├â┬®requis sur chaque PC
 - Windows PowerShell 5.1 ou PowerShell 7.
-- Docker Desktop install├® et d├®marr├® (`docker info` doit r├®ussir).
-- Copie compl├¿te du d├®p├┤t dans la m├¬me structure de dossiers.
-- Les PC doivent pouvoir communiquer sur le m├¬me LAN/VPN priv├®.
-- Les ports autoris├®s par le pare-feu Windows.
+- Docker Desktop install├â┬® et d├â┬®marr├â┬® (`docker info` doit r├â┬®ussir).
+- Copie compl├â┬¿te du d├â┬®p├â┬┤t dans la m├â┬¬me structure de dossiers.
+- Les PC doivent pouvoir communiquer sur le m├â┬¬me LAN/VPN priv├â┬®.
+- Les ports autoris├â┬®s par le pare-feu Windows.
 
-## Pr├®paration maintenant (sans les 4 PC)
-1. D├®compresser `Lot4_Automation` ├á la racine du d├®p├┤t `Collaborative-Fog-Computing`.
-2. V├®rifier les scripts PowerShell :
+## Pr├â┬®paration maintenant (sans les 4 PC)
+1. D├â┬®compresser `deployment\lot4\automation` ├â┬á la racine du d├â┬®p├â┬┤t `Collaborative-Fog-Computing`.
+2. V├â┬®rifier les scripts PowerShell :
    ```powershell
-   Get-ChildItem .\Lot4_Automation\*.ps1 | ForEach-Object {
+   Get-ChildItem .\deployment\lot4\automation\*.ps1 | ForEach-Object {
      $e=$null
      [System.Management.Automation.Language.Parser]::ParseFile($_.FullName,[ref]$null,[ref]$e) | Out-Null
      if($e.Count){$e; throw "Syntax error: $($_.Name)"}
      "PASS: $($_.Name)"
    }
    ```
-3. Ex├®cuter `Install-Lot4.ps1 -Role central` et pour pr├®parer un Fog `-Role fog-a`, `fog-b` ou `fog-c`. Cette pr├®paration ne d├®marre pas les conteneurs.
+3. Ex├â┬®cuter `Install-Lot4.ps1 -Role central` et pour pr├â┬®parer un Fog `-Role fog-a`, `fog-b` ou `fog-c`. Cette pr├â┬®paration ne d├â┬®marre pas les conteneurs.
 
-## Jour du d├®ploiement
-1. R├®server des adresses IPv4 stables sur le routeur ou configurer des IP statiques.
-2. Depuis la racine du d├®p├┤t, sur une machine d'administration, g├®n├®rer les fichiers d'environnement :
+## Jour du d├â┬®ploiement
+1. R├â┬®server des adresses IPv4 stables sur le routeur ou configurer des IP statiques.
+2. Depuis la racine du d├â┬®p├â┬┤t, sur une machine d'administration, g├â┬®n├â┬®rer les fichiers d'environnement :
    ```powershell
-   .\Lot4_Automation\Set-Lot4Config.ps1 -CentralIP 192.168.1.10 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192.168.1.13
+   .\deployment\lot4\automation\Set-Lot4Config.ps1 -CentralIP 192.168.1.10 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192.168.1.13
    ```
-   Remplacer les exemples par les vraies IP. Copier `central\.env` uniquement sur Central et `fog-node\.env.fog` sur les trois Fog (ou ex├®cuter le script sur chaque clone).
+   Remplacer les exemples par les vraies IP. Copier `central\.env` uniquement sur Central et `fog-node\.env.fog` sur les trois Fog (ou ex├â┬®cuter le script sur chaque clone).
 3. Sur Central :
    ```powershell
-   .\Lot4_Automation\Install-Lot4.ps1 -Role central
-   .\Lot4_Automation\Configure-Firewall.ps1 -Role central
-   .\Lot4_Automation\Deploy-Lot4.ps1 -Role central
+   .\deployment\lot4\automation\Install-Lot4.ps1 -Role central
+   .\deployment\lot4\automation\Configure-Firewall.ps1 -Role central
+   .\deployment\lot4\automation\Deploy-Lot4.ps1 -Role central
    ```
 4. Sur chaque Fog :
    ```powershell
-   .\Lot4_Automation\Install-Lot4.ps1 -Role fog-a
-   .\Lot4_Automation\Configure-Firewall.ps1 -Role fog-a
-   .\Lot4_Automation\Deploy-Lot4.ps1 -Role fog-a
+   .\deployment\lot4\automation\Install-Lot4.ps1 -Role fog-a
+   .\deployment\lot4\automation\Configure-Firewall.ps1 -Role fog-a
+   .\deployment\lot4\automation\Deploy-Lot4.ps1 -Role fog-a
    ```
-   Adapter le r├┤le sur les deux autres machines.
+   Adapter le r├â┬┤le sur les deux autres machines.
 5. Depuis Central :
    ```powershell
-   .\Lot4_Automation\Register-FogNodes.ps1 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192.168.1.13
-   .\Lot4_Automation\Test-Lot4.ps1 -CentralIP 192.168.1.10 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192.168.1.13
+   .\deployment\lot4\automation\Register-FogNodes.ps1 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192.168.1.13
+   .\deployment\lot4\automation\Test-Lot4.ps1 -CentralIP 192.168.1.10 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192.168.1.13
    ```
 
-## G├®n├®rer les cibles Prometheus
+## G├â┬®n├â┬®rer les cibles Prometheus
 ```powershell
-.\\Lot4_Automation\\Configure-Monitoring.ps1 -CentralIP 192.168.1.10 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192.168.1.13
+.\\deployment\lot4\automation\\Configure-Monitoring.ps1 -CentralIP 192.168.1.10 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192.168.1.13
 ```
-Cette commande g├®n├¿re le fichier de cibles LAN. Le d├®ploiement Prometheus et la disponibilit├® de `/metrics` restent ├á confirmer.
+Cette commande g├â┬®n├â┬¿re le fichier de cibles LAN. Le d├â┬®ploiement Prometheus et la disponibilit├â┬® de `/metrics` restent ├â┬á confirmer.
 
-## Arr├¬t
-- Central : `.\Lot4_Automation\Stop-Lot4.ps1 -Role central`
-- Chaque Fog : `.\Lot4_Automation\Stop-Lot4.ps1 -Role fog-a` (adapter le r├┤le).
+## Arr├â┬¬t
+- Central : `.\deployment\lot4\automation\Stop-Lot4.ps1 -Role central`
+- Chaque Fog : `.\deployment\lot4\automation\Stop-Lot4.ps1 -Role fog-a` (adapter le r├â┬┤le).
 
-## Limites connues ├á valider
-- Le script Register-FogNodes v├®rifie les endpoints `/health`; il ne cr├®e pas une inscription persistante c├┤t├® Scheduler si l'application MP2 ne fournit pas cette API. Les URL des Fog sont inject├®es dans le Scheduler via l'overlay Compose.
-- L'API Scheduler et Fog doit r├®ellement exposer `/health` (d├®j├á observ├® en simulation pour Scheduler et les Fog).
-- Le template Prometheus existant contient des cibles HTTP ; confirmer que les applications exposent `/metrics` avant d'activer ces jobs. Le template est une configuration, pas un d├®ploiement Prometheus complet.
-- Le Mosquitto de base utilise une configuration permissive. Limiter le pare-feu au r├®seau priv├® de confiance et ne jamais publier MQTT sur Internet.
-- Docker Desktop, ├®l├®vation administrateur et ├®ventuel red├®marrage Windows ne peuvent pas ├¬tre enti├¿rement automatis├®s par ces scripts.
+## Limites connues ├â┬á valider
+- Le script Register-FogNodes v├â┬®rifie les endpoints `/health`; il ne cr├â┬®e pas une inscription persistante c├â┬┤t├â┬® Scheduler si l'application MP2 ne fournit pas cette API. Les URL des Fog sont inject├â┬®es dans le Scheduler via l'overlay Compose.
+- L'API Scheduler et Fog doit r├â┬®ellement exposer `/health` (d├â┬®j├â┬á observ├â┬® en simulation pour Scheduler et les Fog).
+- Le template Prometheus existant contient des cibles HTTP ; confirmer que les applications exposent `/metrics` avant d'activer ces jobs. Le template est une configuration, pas un d├â┬®ploiement Prometheus complet.
+- Le Mosquitto de base utilise une configuration permissive. Limiter le pare-feu au r├â┬®seau priv├â┬® de confiance et ne jamais publier MQTT sur Internet.
+- Docker Desktop, ├â┬®l├â┬®vation administrateur et ├â┬®ventuel red├â┬®marrage Windows ne peuvent pas ├â┬¬tre enti├â┬¿rement automatis├â┬®s par ces scripts.

# Phase 3 - Correctifs ciblés et validation

## But
- Corriger l'interpolation PowerShell dans les deux copies de `Test-LanDeployment.ps1` (`$CentralHost:` devient `${CentralHost}:`).
- Sauvegarder les deux fichiers avant toute modification.
- Revalider la syntaxe PowerShell dans `projects`, `deployment`, `.github` (le validateur Phase 3 précédent est exclu pour éviter son auto-signalement).
- Revalider les JSON dans ces racines avec `ConvertFrom-Json`.
- Produire un rapport de références historiques à examiner, sans les modifier.

## Utilisation
1. Extraire le ZIP à la racine du dépôt. Le script sera dans `Fog-Phase3-Validation-Pack`.
2. Depuis la racine du dépôt, exécuter :
   `./Fog-Phase3-Validation-Pack/Apply-Phase3-Fixes-And-Validate.ps1`
3. Rapports : `reorganization-reports/phase3-validation-reliable/`.

## Sécurité
- Sauvegardes Desktop avant patch exact des deux scripts LAN.
- Aucun Docker, aucun service, aucune commande Git.
- Aucun fichier historique n'est supprimé ou modifié.
- Les références héritées sont seulement rapportées (review).
- Le script ne répare pas automatiquement d'autres erreurs syntaxiques/JSON.

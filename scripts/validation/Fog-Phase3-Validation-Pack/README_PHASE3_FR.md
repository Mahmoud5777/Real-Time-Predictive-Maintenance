# Phase 3 – Validation statique de la réorganisation

## But
Vérifier la structure migrée, parser les scripts PowerShell, valider les JSON et produire un inventaire des références historiques à examiner.

## Sécurité
- Aucune commande Docker/Compose n'est exécutée.
- Aucun service n'est démarré ou arrêté.
- Aucune commande Git n'est exécutée.
- Le script ne modifie pas les fichiers source; il crée seulement les rapports dans `reorganization-reports/phase3-validation/`.

## Exécution (PowerShell à la racine du repo)
1. Extraire ce pack à la racine du dépôt.
2. Exécuter:
   ```powershell
   .\Validate-Reorganization-Phase3.ps1
   ```
3. Envoyer les trois fichiers générés:
   - `phase3-validation-summary.txt`
   - `phase3-validation-checks.csv`
   - `phase3-validation-issues.csv`

Le scan des anciens tokens est volontairement marqué REVIEW: certaines occurrences restent valides (mounts Docker, chemins de fallback, documentation). Ne les supprimez pas automatiquement.

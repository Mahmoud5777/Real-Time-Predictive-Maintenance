# Phase 3 - Validation statique (pack corrige)

## Installation
Extraire le ZIP a la racine du depot. Il contient le dossier `Fog-Phase3-Validation-Pack`.
Si ce dossier existe deja, remplacer uniquement le script `Validate-Reorganization-Phase3.ps1`.

## Execution
Depuis la racine du depot, lancer:

```powershell
.\Fog-Phase3-Validation-Pack\Validate-Reorganization-Phase3.ps1
```

Le script est ASCII-only et effectue des controles statiques:
- presence de dossiers et fichiers attendus;
- analyse syntaxique PowerShell (les scripts sont parses, jamais executes);
- validation JSON;
- revue des references historiques dans `projects`, `deployment` et `.github` (aucune correction automatique).

Les rapports sont generes dans `reorganization-reports\phase3-validation\`:
- `phase3-validation-summary.txt`
- `phase3-validation-checks.csv`
- `phase3-validation-issues.csv`

Le script ne lance ni Docker, ni service, ni commande Git. Il ne supprime et ne modifie aucun fichier du projet; seuls les rapports sont ecrits.

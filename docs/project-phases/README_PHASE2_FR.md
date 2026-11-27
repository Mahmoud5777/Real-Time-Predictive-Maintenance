# Phase 2 — Audit des chemins après copie

Ce pack est **un audit non destructif**, pas encore le correctif automatique des chemins.

## Installation
Extraire `Audit-Reorganization-Phase2.ps1` à la racine du dépôt `Collaborative-Fog-Computing`.

## Exécution
Depuis PowerShell à la racine :

```powershell
.\Audit-Reorganization-Phase2.ps1
```
Ou en indiquant explicitement la racine :

```powershell
.\Audit-Reorganization-Phase2.ps1 -RepositoryRoot "C:\Users\ayedi\Desktop\projets\Collaborative-Fog-Computing"
```

## Résultats
Les rapports seront générés dans `reorganization-reports\phase2-path-audit\` :
- `legacy-path-findings.csv`
- `legacy-path-audit.txt`

Le script parcourt les fichiers textuels des dossiers migrés, `.github` et `docs`, exclut les environnements, caches et `.env`, puis inventorie les lignes qui mentionnent les anciens noms. Il ne modifie aucun fichier, ne lance Git, Docker, les tests, ni les services.

Les correspondances peuvent être des mentions documentaires ou historiques; elles ne sont pas toutes des chemins cassés. L'inventaire servira à construire le correctif ciblé, puis à valider les chemins Compose, Python, PowerShell et CI.

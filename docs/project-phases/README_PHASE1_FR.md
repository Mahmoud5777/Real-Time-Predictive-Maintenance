# Réorganisation Collaborative Fog Computing — Phase 1 (copie non destructive)

## Objectif
Créer la nouvelle arborescence proposée **en copie**, sans déplacer ni supprimer les dossiers originaux. La correction des références de chemins est une phase distincte, après vérification des copies.

## Sécurité
- Le script est en mode simulation (dry-run) par défaut.
- Il ne supprime aucun dossier source.
- Il refuse d'écraser une destination qui existe déjà.
- Il ne lance aucune commande Git ni Docker.
- Les fichiers `.env` présents sur le PC local sont copiés sans afficher leur contenu. Ils ne figurent pas dans le ZIP d'audit fourni à ChatGPT.
- En cas de destination déjà créée, le script s'arrête : examiner avant de poursuivre.

## Étapes PowerShell
Depuis le répertoire racine du dépôt :

```powershell
# 1. Simulation (aucune copie)
.\Prepare-Reorganization.ps1

# 2. Si le plan affiché est correct, lancer les copies
.\Prepare-Reorganization.ps1 -Execute
```

On ne passe pas encore à la correction des chemins ni à la suppression des anciens dossiers. Après cette phase, vérifier la présence des nouvelles copies. Phase 2 mettra à jour les chemins de façon contrôlée et préparera une validation statique/tests.

## Mapping
- `mp1-simulator` -> `projects/mp1/simulator`
- `MP1_Industrial_Simulation` -> `projects/mp1/industrial-simulation`
- `Real-Time-Predictive-Maintenance` -> `projects/mp2`
- `MP3_Backend_Source` -> `projects/mp3`
- `Project_Monitoring` -> `projects/mp4`
- `Lot4_Automation` -> `deployment/lot4/automation`
- `Lot4_LAN_Integration` -> `deployment/lot4/core`
- `Lot4_LAN_Deployment` -> `deployment/lot4/alternative-deployment`
- `lot4v3`, `lot4_patch31` -> `archive/lot4/`
- infrastructure racine `central`, `fog-node`, `monitoring`, `scripts` -> `archive/lot4/legacy-infrastructure/`

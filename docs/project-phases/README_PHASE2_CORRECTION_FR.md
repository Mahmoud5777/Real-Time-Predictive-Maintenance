# Pack correctif — Phase 2 (chemins après réorganisation)

## Périmètre

Ce pack corrige uniquement les chemins actifs hérités de l'ancienne arborescence, dans les copies migrées :
- MP2 -> MP1 (volume Docker + résolution du modèle ML)
- MP2 -> MP3 (test d'adaptateur)
- Workflow CI MP4
- Lot4 Automation : chemins vers MP2, MP1, le Core, racine du dépôt et fichiers de monitoring
- Lot4 Core : scripts, Compose fog remote/local et commandes documentées

Les archives `archive/` et les dossiers sources historiques ne sont pas parcourus.

## Précautions

- Le script fonctionne en simulation par défaut.
- Il ne lance aucune commande Git ou Docker.
- En mode `-Apply`, les fichiers ciblés sont sauvegardés sur le Bureau sous `Fog-Reorg-Phase2-Backups\<timestamp>` avant modification.
- Exécuter depuis la racine du repository.
- Ne lance pas encore de déploiement Docker après application; la validation compose et tests viendront ensuite.

## Étapes

1. Extraire `Apply-Phase2PathCorrections.ps1` et ce README à la racine du projet, sans écraser de fichiers.
2. Ouvrir PowerShell dans la racine du repository.
3. Simulation :
   ```powershell
   .\Apply-Phase2PathCorrections.ps1
   ```
4. Envoyer le résultat de simulation pour contrôle.
5. Si le plan est validé, appliquer :
   ```powershell
   .\Apply-Phase2PathCorrections.ps1 -Apply
   ```

## Note importante

Le pack cible la nouvelle arborescence de Phase 1. Il ne supprime ni ne déplace aucun dossier et ne touche pas aux fichiers `.env`.

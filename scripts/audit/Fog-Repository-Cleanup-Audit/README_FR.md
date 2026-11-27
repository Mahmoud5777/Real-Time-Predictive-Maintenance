# Audit de nettoyage du dépôt — lecture seule

Ce pack réalise un inventaire initial de la qualité du dépôt local :
- fichiers suivis par Git vs fichiers non suivis/ignorés ;
- fichiers dont le nom mérite revue (espaces, majuscules, caractères non ASCII, marqueurs de backup/temp/version) ;
- fichiers identiques détectés par SHA-256 ;
- fichiers potentiellement générés/temporaire (classification indicative) ;
- résumé des dossiers de premier niveau ;
- `git status`, fichiers non suivis et ignorés.

**Aucune suppression, modification, renommage, déplacement, commande Docker ou opération Git de modification n'est effectuée.**

## Exécution
À la racine du dépôt `Collaborative-Fog-Computing`, dans PowerShell :

```powershell
.\Fog-Repository-Cleanup-Audit\Audit-Repository-Cleanup.ps1
```

Rapports générés dans :

`reorganization-reports\repository-cleanup-audit`

La classification est un indicateur d'audit, pas une autorisation de supprimer. Les rapports seront utilisés pour construire une liste de nettoyage validée, puis un script de nettoyage avec sauvegarde et dry-run.

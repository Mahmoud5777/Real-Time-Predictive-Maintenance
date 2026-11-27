# Lot 3 — Intégration des Analytics MP3 dans le dashboard MP4

## Installation
1. Décompresser l'archive à la racine du dépôt `Collaborative-Fog-Computing` (elle contient le dossier `Project_Monitoring`).
2. Depuis PowerShell :

```powershell
Set-Location "C:\Users\ayedi\Desktop\projets\Collaborative-Fog-Computing\Project_Monitoring"
powershell -ExecutionPolicy Bypass -File .\apply_lot3.ps1
Set-Location .\frontend
npm run build
```

3. Vérifier que le backend MP3 et le réseau Docker `mp3-cloud_default` sont actifs.
4. Depuis la racine du dépôt, démarrer MP4 :

```powershell
Set-Location "C:\Users\ayedi\Desktop\projets\Collaborative-Fog-Computing"
docker compose -f Project_Monitoring\docker-compose.yml up -d --build
```

5. Ouvrir `http://localhost:3001`.

## Contenu et fonctions
- `AnalyticsPanel.jsx` : panneau React relié aux endpoints `/analytics/kpis`, `/analytics/risk-ranking` et `/analytics/model-comparison`.
- `analytics.css` : présentation responsive des KPI et classements.
- `apply_lot3.ps1` : intègre le panneau dans la vue d'ensemble et corrige le `#root` Vite limité à 1126 px.
- Sélection d'une heure complète. La période initiale correspond aux données présentes dans la base : 1er novembre 2026, 00:00–01:00 UTC (01:00–02:00 heure de Tunis).
- Les métriques non calculables sont explicitement signalées ; elles ne sont pas remplacées par zéro.

## Contrat et limites
- Les endpoints de classement et de comparaison sont interrogés sur une heure complète, conformément au contrat du backend.
- Les distributions de prédictions par version ne représentent pas la précision du modèle.
- Les métriques nécessitant des labels de vérité terrain ou des événements de panne confirmés restent indisponibles tant que ces données ne sont pas collectées.
- Aucun fichier backend MP3 n'est modifié.
- Le script d'intégration peut être relancé sans dupliquer l'import ni le panneau.

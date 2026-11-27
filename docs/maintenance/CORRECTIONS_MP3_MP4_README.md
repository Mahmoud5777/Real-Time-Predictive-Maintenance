# Corrections MP3 / MP4

## Fichiers à remplacer
Depuis la racine du dépôt `Collaborative-Fog-Computing` :

- `Project_Monitoring/frontend/src/App.jsx`
- `Project_Monitoring/frontend/src/components/AnalyticsPanel.jsx`

Les chemins dans cette archive sont déjà ceux du dépôt.

## Corrections incluses
1. Réparation des textes français et des icônes corrompus dans `App.jsx`.
2. Clarification dans Analytics : les volumes affichés sont ceux de la fenêtre horaire sélectionnée, pas le total de l'historique conservé.
3. Clarification près des alertes : le flux de prédictions et le flux d'alertes MP3 sont distincts. Une prédiction CRITICAL ne crée pas automatiquement une alerte.

## Points d'analyse importants
- L'API `/measurements?limit=1000` renvoie une page de mesures, tandis que le panneau Analytics interroge le cache KPI sur une fenêtre UTC horaire complète. Les 963 mesures historiques et les 903 échantillons d'une fenêtre analytique ne sont donc pas directement comparables.
- Les sept métriques indisponibles sont explicitement déclarées dans `app/analytics/catalogue.py` avec leurs raisons. Elles ne doivent pas être remplacées par des zéros.
- `app/services/ingest.py` persiste les prédictions et les alertes via deux types de messages distincts. Aucun code du backend inspecté ne transforme automatiquement une prédiction CRITICAL en alerte. Cette règle métier n'a pas été inventée/modifiée dans ce correctif.

## Intégration
1. Extraire cette archive à la racine du dépôt et accepter le remplacement des deux fichiers.
2. Dans `Project_Monitoring/frontend`, exécuter `npm run build`.
3. Si MP4 tourne dans Docker, reconstruire/redémarrer le service frontend selon le compose réellement utilisé.
4. Recharger le dashboard avec `Ctrl+F5`.

Aucun fichier backend, aucune donnée PostgreSQL et aucune migration ne sont modifiés par cette archive.

# Lot 1 — Correction du test d'intégration MP1

## Fichier remplacé
`Real-Time-Predictive-Maintenance/tests/test_processor.py`

## Pourquoi ?
`TaskRequest` est un modèle Pydantic. Lors de sa construction, Pydantic peut normaliser/copier le dictionnaire fourni dans le champ `payload`. Le test comparait donc `task.payload` à l'objet d'origine avec `is`, ce qui vérifiait une identité qui n'est pas garantie par Pydantic.

Le test corrigé vérifie :
- que le prédicteur reçoit exactement l'objet `task.payload` ;
- que son contenu reste identique au payload source.

Aucun code applicatif n'est modifié.

## Intégration
Extraire cette archive à la racine du dépôt `Collaborative-Fog-Computing`, en conservant les chemins et en acceptant le remplacement du seul fichier indiqué.

Puis exécuter depuis `Real-Time-Predictive-Maintenance` :

```powershell
python -m pytest -q tests/test_processor.py tests/test_mp3_adapter.py tests/test_mp1_ml_integration.py
```

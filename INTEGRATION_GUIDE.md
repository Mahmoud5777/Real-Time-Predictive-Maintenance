# Lot 1 — Brancher le modèle ML MP1 dans les Fog nodes MP2

## Objectif

Les Fog nodes utilisent désormais le véritable `Predictor` de `mp1-simulator` pour chaque tâche `FAILURE_PREDICTION` qui contient le contrat capteur complet. Chaque processus Fog possède sa propre instance du prédicteur et donc ses propres buffers temporels par machine.

Les tâches manuelles/incomplètes restent compatibles avec l'ancien traitement par seuils, mais le résultat est explicitement identifié par `method=RULE_BASED_FALLBACK` et `model_version=mp2-rule-fallback-v1`. Le flux normal du simulateur MP1 utilise `method=MP1_ML` et la version réelle du modèle.

## Contenu de l'archive

- `Real-Time-Predictive-Maintenance/fog_nodes/common/mp1_inference.py` : charge le package MP1 et son modèle sans dépendre du répertoire courant.
- `Real-Time-Predictive-Maintenance/fog_nodes/common/processor.py` : branche l'inférence ML, conserve les tâches existantes et publie les prédictions ML vers MP3.
- `Real-Time-Predictive-Maintenance/requirements.txt` : ajoute les dépendances ML compatibles avec MP1.
- `Real-Time-Predictive-Maintenance/docker-compose.yml` : monte le code et le modèle MP1 en lecture seule dans les trois Fog nodes.
- `Real-Time-Predictive-Maintenance/tests/test_processor.py` : actualise les tests du fallback et couvre le branchement ML.
- `Real-Time-Predictive-Maintenance/tests/test_mp1_ml_integration.py` : smoke test optionnel avec le véritable modèle sauvegardé.

## Installation

1. Extraire le ZIP **à la racine** du dépôt `Collaborative-Fog-Computing` en conservant l'arborescence et en acceptant le remplacement des fichiers indiqués.
2. Ne pas déplacer ni copier manuellement `mp1-simulator`. Le dossier existant et le fichier `mp1-simulator/models/mp1_model.joblib` sont montés dans chaque conteneur Fog.
3. Ne pas remplacer les fichiers `.env` ni les autres configurations personnelles.

## Validation locale

Depuis PowerShell, à la racine du dépôt :

```powershell
cd "C:\Users\ayedi\Desktop\projets\Collaborative-Fog-Computing\Real-Time-Predictive-Maintenance"

python -m compileall -q fog_nodes tests
python -m pip install -r requirements.txt
python -m pytest -q tests/test_processor.py tests/test_mp3_adapter.py tests/test_mp1_ml_integration.py
```

Le smoke test du modèle est ignoré automatiquement si les dépendances ML ne sont pas installées. Pour valider réellement le modèle, installer les dépendances via `requirements.txt` et vérifier que `mp1-simulator/models/mp1_model.joblib` existe.

## Validation Docker

Après validation locale, depuis le dossier `Real-Time-Predictive-Maintenance` :

```powershell
docker compose config
docker compose build --no-cache fog-a fog-b fog-c
```

Pour le mode intégré MP2–MP3, le réseau externe `mp3-cloud_default` doit déjà exister. La commande de démarrage globale sera fournie dans le lot d'orchestration, après validation des autres composants ; ne pas démarrer toute la plateforme à ce stade.

## Résultat attendu

- Les tâches `ANOMALY_DETECTION` et `DATA_PREPROCESSING` conservent leur comportement.
- Une tâche `FAILURE_PREDICTION` contenant `machine_id`, `timestamp`, `temperature`, `vibration`, `speed` et `current` passe par MP1.
- Les 300 premières mesures par machine servent au warm-up du modèle, conformément à l'implémentation MP1.
- Les messages publiés vers MP3 conservent le contrat existant et transmettent la véritable `model_version`.
- Les tâches incomplètes restent traitées par le fallback explicitement identifié.

## Important

Ce lot ne prétend pas valider l'intégration complète MP1→MP4. Il branche le modèle ML et prépare son chargement dans Docker. La validation MQTT de bout en bout et l'orchestration globale seront traitées dans les lots suivants.

MP3 - GENERATION AUTOMATIQUE DES ALERTES DE DEFAILLANCE

Contenu a copier dans le depot existant :

1) MP3_Backend_Source/mp3-cloud/app/services/ingest.py
   -> mp3-cloud/app/services/ingest.py

2) MP3_Backend_Source/mp3-cloud/tests/test_ingest_database.py
   -> mp3-cloud/tests/test_ingest_database.py

Comportement ajoute
- Une prediction CRITICAL la plus recente cree une alerte PREDICTED_FAILURE.
- Les predictions CRITICAL suivantes de la meme machine reutilisent l'alerte active.
- Une prediction NORMAL la plus recente resout l'alerte automatique active.
- Une prediction NORMAL arrivee en retard ne resout pas une alerte si une prediction
  CRITICAL plus recente est deja en base.
- Une fois l'alerte resolue, un nouvel episode CRITICAL cree une nouvelle alerte.
- Les alertes non generees automatiquement ne sont pas modifiees.
- Le verrouillage de la ligne machine serialise les traitements concurrents.
- Aucun changement de schema ni migration Alembic n'est necessaire.

Validation
- Compilation Python effectuee avec python -m compileall.
- La suite pytest n'a pas pu etre lancee dans l'environnement de preparation :
  le module asyncpg est absent. Executer les tests PostgreSQL dans l'environnement
  habituel du projet avec pytest -q --postgres.

Apres integration, reconstruire/redeployer MP3 avec la procedure habituelle du depot.
Ne pas supprimer les volumes PostgreSQL.

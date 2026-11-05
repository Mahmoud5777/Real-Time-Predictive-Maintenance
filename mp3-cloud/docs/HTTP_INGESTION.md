# Etape 3 - ingestion HTTP persistante

L'entree `POST /api/v1/ingest/batch` enregistre les messages dans PostgreSQL. Le service
commun `app/services/ingest.py::persist_batch` est aussi appele par le worker MQTT
depuis l'etape 4. MP3 conserve les observations ; MP2 execute et ordonnance les taches.

## 3.1 - Validation et bilan

Le lot contient de 1 a 5000 elements `{kind, payload}` et exige le bearer token configure.
Pydantic valide les cinq payloads : types, identifiants, bornes, dates avec fuseau et
champs inconnus. Les dates sont normalisees en UTC ; la base verifie ensuite les
references de catalogue, l'unicite et les contraintes de coherence.

Le bilan `accepted / duplicates / rejected / errors` porte sur les elements du lot.
Les index d'erreur commencent a zero. `accepted` ne signifie plus seulement "valide" :
il compte les nouvelles ecritures apres confirmation de la transaction.

## 3.2 - Correspondance messages et tables

- `sensor` : insertion dans `sensor_data` ; association machine/zone conforme au catalogue.
- `prediction` : insertion dans `predictions`, score Decimal conserve sans arrondi impose.
  Un Fog peut analyser une machine d'une autre zone.
- `alert` : insertion dans `alerts`, etat initial OPEN. Une retransmission ne modifie pas
  un acquittement ou une resolution effectue apres la creation.
- `fog_status` : observation dans `fog_status_history` et mise a jour conditionnelle de `fog_nodes`.
- `task_event` : evenement dans `task_events` et projection des informations connues dans `tasks`.

## 3.3 - Transaction et deduplication

Le service possede la transaction du lot ; l'appelant fournit une session sans transaction
ouverte. Chaque element est traite dans un savepoint. Une erreur metier annule toutes
les ecritures de cet element, puis le traitement passe au suivant. Une erreur globale
avant confirmation du commit empeche de renvoyer un bilan de succes.

La contrainte unique de chaque table et `ON CONFLICT (message_id) DO NOTHING` arbitrent
les envois concurrents. L'unicite est par type de message. Apres un conflit, le service
compare le contenu valide avec la ligne existante : identique = doublon ; different =
MESSAGE_ID_CONFLICT. Les dates de reception Cloud ne participent pas a cette comparaison.
La casse du UUID de tache est normalisee avant stockage et comparaison.

Le meme `task_id` peut produire plusieurs evenements, avec des `message_id` distincts.
La contrainte `alert_id` est differente : un nouveau message reutilisant cet identifiant
est rejete, sans remplacer le contenu ou le cycle de l'alerte.

## 3.4 - Observations Fog

Un verrou sur le Fog protege ensemble l'historique et son etat courant. Toute nouvelle
observation valide reste dans l'historique. L'etat courant change seulement si
`last_heartbeat` est strictement plus recent. A date egale, la premiere observation
enregistree reste courante ; une observation ancienne ne fait pas regresser l'etat.
Un doublon ne rafraichit pas `last_received_at`.

Une transition OFFLINE explicitement rapportee renseigne `offline_since`. Une observation
ulterieure active efface cet intervalle courant et renseigne `recovered_at` si une
observation precedente existait. Le premier heartbeat actif ne transforme pas l'etat
OFFLINE initial du catalogue en fausse panne/reprise.

Ces dates concernent des observations. Le service ne detecte pas encore automatiquement
un heartbeat absent et ne calcule pas de disponibilite sur les intervalles sans donnees.

## 3.5 - Journal et projection des taches

Le parent `tasks` et son evenement sont ecrits dans le meme savepoint. Un rejet ne laisse
aucune nouvelle tache orpheline. Un verrou par tache serialise les mises a jour concurrentes.
Le type et la date de creation d'une tache restent stables.

Un evenement CREATED identifie l'origine. Une migration recue sans creation conserve une
origine NULL. Une creation tardive peut completer cette origine mais ne remplace pas
l'affectation deja observee. Une origine connue ne peut plus etre changee.

Pour MIGRATED ou RECOVERED, la destination donne l'affectation observee ; une destination
absente laisse cette affectation inconnue. Pour les autres statuts, la source rapporte
l'affectation. Les evenements FAILED -> RECOVERED -> RUNNING peuvent etre conserves,
y compris une reprise critique sur un autre Fog selon la politique de MP2.

COMPLETED reste terminal pour ce task_id. Un evenement RUNNING tardif reste dans le journal
mais ne remplace pas cet etat final. Une date de fin connue ne peut pas etre remplacee par
une autre date. Le contrat ne distingue pas encore les tentatives : une nouvelle execution
apres completion exige une convention supplementaire avec MP2.

`occurred_at`, `started_at` et `last_event_at` restent inconnus pour les messages actuels.
Le Cloud ne les fabrique pas a partir de `created_at` ou `received_at`. Une date
`completed_at` rapportee avec COMPLETED est conservee. `machine_id` reste inconnu car il
ne figure pas dans le message de tache actuel.

Hors des protections sur CREATED et COMPLETED, la projection reflete les observations
traitees, pas une preuve de chronologie reelle. Les sequences, dates d'evenement, tentatives
et origine explicite doivent etre convenues avec MP2 pour traiter completement le hors ordre.

## 3.6 - Reponses HTTP

- 207 : au moins une insertion ou un doublon ; bilan complet, meme avec des rejets.
- 422 / NO_VALID_MESSAGE : tous les elements rejetes ; probleme et bilan au premier niveau.
- 422 de FastAPI : enveloppe invalide, corps avec `detail`, avant appel au service.
- 401 : token absent ou invalide, format existant de la dependance d'authentification.
- 503 : transaction non confirmee, probleme sans bilan de succes ni details SQL.
- 500 : erreur inattendue, gestionnaire global existant.

Pour un bilan confirme, `accepted + duplicates + rejected` egale le nombre d'elements.
Apres 503, rejouer les memes identifiants. Une confirmation perdue peut cacher un commit
reussi ; les contraintes de deduplication rendent ce rejeu sans nouvelle insertion.
Les deadlocks ou conflits de transaction remontent comme erreurs globales : le client
reessaie le lot. Le service ne retente pas silencieusement une partie du lot.

## 3.7 - Verification reproductible

Depuis le dossier mp3-cloud, dans PowerShell :

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pytest --postgres
.\.venv\Scripts\python.exe scripts/check_contract.py
```

Les tests locaux HTTP utilisent un writer simule et une dependance de session remplacee.
Ils ne se connectent jamais a fog_cloud. Les tests PostgreSQL utilisent uniquement des
bases `mp3_test_<UUID>`, creees et supprimees par les fixtures. Les tests multi-connexions
ont une autre base dediee pour ne pas contaminer les tests du schema.

La verification couvre les cinq types, le rejeu, les contenus conflictuels, les lots mixtes,
les contraintes, les projections atomiques, les anciennes observations, les journaux
partiels, la concurrence, les echecs avant commit et le commit HTTP visible depuis une
autre connexion. Les donnees de ces scenarios sont synthetiques ; elles ne prouvent pas
que les trois environnements Fog reels sont demarres.

Le transport MQTT est realise a l'etape 4 : voir [MQTT_INGESTION.md](MQTT_INGESTION.md).
Les API de lecture complementaires, les jobs KPI et les mesures de performance restent
dans leurs etapes respectives. Cette ingestion utilise le schema 0001_mp3_schema.

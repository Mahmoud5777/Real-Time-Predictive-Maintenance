# Lectures pour le dashboard - etapes 5 a 7

MP4 peut lire les observations stockees sans acceder directement a PostgreSQL.
Les routes ci-dessous sont implementees sous `/api/v1`. Les lectures sont publiques
dans l'environnement de demonstration actuel ; l'ingestion conserve son bearer token.
Swagger expose les schemas de reponse et le bouton **Authorize** pour l'ingestion.

## Routes disponibles

- `GET /machines` : catalogue, filtre zone, tri par machine_id / name / zone.
- `GET /machines/{machine_id}` : une machine du catalogue.
- `GET /machines/{machine_id}/latest` : derniere mesure, departagee par id si dates egales.
- `GET /measurements` : mesures brutes, filtres machine_id / zone / periode.
- `GET /predictions` : filtres machine_id / zone / fog_id / anomaly / severity / model_version / periode.
- `GET /alerts` : filtres machine_id / zone / fog_id / status / severity / periode.
- `GET /alerts/{alert_id}` : detail par identifiant metier, avec dates connues du cycle de vie.
- `GET /fog/nodes` : catalogue, etat rapporte et supervision distincte ; filtres zone / status / supervision_status.
- `GET /fog/nodes/{fog_id}` : detail d'un Fog et age de son dernier heartbeat.
- `GET /fog/status-history` : observations de charge, filtres fog_id / zone / status / periode.
- `GET /fog/supervision-history` : decisions Cloud, filtres fog_id / zone / supervision_status / periode.

- `GET /tasks` : projections, filtres origin_fog_id / current_fog_id / machine_id / zone /
  status / task_type / priority / critical / periode.
- `GET /tasks/{task_id}` : dernier etat observe d'une tache UUIDv4.
- `GET /tasks/events` : journal, filtres task_id / source_fog / destination_fog / zone /
  status / critical / periode.

L'etat effectif de supervision devient UNKNOWN si le dernier scan est absent, trop
ancien ou dans le futur. Le filtre supervision_status porte sur l'etat stocke.
Le journal de supervision ne contient aucune charge inventee ; voir
[FOG_SUPERVISION.md](FOG_SUPERVISION.md) pour les preuves, horloges et lacunes.

Les champs et enums exacts sont dans le Swagger et dans
[openapi.yaml](../../contracts/openapi.yaml). Le contrat producteur reste identique.
Les migrations 0002/0003 ajoutent analytics et supervision ; les KPI sont decrits dans
[KPI_FORMULAS.md](KPI_FORMULAS.md). Acquittement d'alertes et SSE restent des jalons ulterieurs.

## Pagination et tri

Chaque collection renvoie `items` et `meta` :

```json
{"items": [], "meta": {"limit": 50, "offset": 0, "total": 0}}
```

`limit` vaut 50 par defaut, de 1 a 1000 ; `offset` commence a 0. `total` compte les lignes
qui satisfont tous les filtres, avant pagination. Au-dela du total, la page reste vide
avec son total. Une liste filtree vide n'est pas une erreur 404.

`sort` accepte uniquement les champs annonces dans Swagger ; le prefixe `-` descend.
Un second tri sur la cle primaire departage les valeurs identiques. Les dates NULL sont
toujours placees a la fin, sans remplacement par une date de reception ou de creation.

Defaults : machines par `machine_id`, Fog par `fog_id`, mesures / predictions / alertes par
`-timestamp`, historique Fog par `-observed_at`, taches par `-created_at` et evenements par
`-received_at`. Les predictions permettent aussi le tri par risque.

L'offset convient aux pages de demonstration. Sous ingestion concurrente, des lignes
peuvent se deplacer entre deux pages. Le total et les items utilisent deux requetes en
isolation PostgreSQL READ COMMITTED : une ecriture entre elles peut aussi changer le total.
Ce contrat ne garantit ni un snapshot multi-page ni une pagination par curseur.
Les optimisations et mesures de charge restent dans le jalon de performance.

## Periodes, zones et observations incompletes

`from` et `to` sont inclusifs, acceptent un timestamp ISO-8601 avec fuseau et sont normalises
en UTC. Une date naive, une borne invalide ou `from > to` donne 422. Les reponses utilisent
des timestamps UTC avec `Z`. Les UUID de tache valides sont normalises.

- Mesures / predictions / alertes : periode sur `timestamp` du producteur.
- Historique de charge Fog : periode sur observed_at producteur ; journal de supervision :
  periode sur observed_at Cloud, dates de decisions.
- Taches : periode sur `created_at`.
- Evenements : `time_field=created_at` par defaut pour conserver le contrat existant.
  Choisir `received_at` pour la reception Cloud, ou `occurred_at` pour une date d'evenement
  connue. Filtrer une periode sur `occurred_at` exclut les dates inconnues ; sans borne,
  les lignes sans cette date restent consultables.

La zone des predictions et alertes est celle de la machine, pas celle du Fog executant.
Ainsi une prediction de FOG_B pour M01 reste en zone A. La zone des taches et de leur journal
est celle du Fog d'origine connu ; les journaux partiels sans origine ne satisfont pas ce filtre.
`origin_fog_id` et `current_fog_id` restent distincts apres une migration.

## Dernier etat Fog

`status` conserve le dernier etat rapporte. Une lecture ne met pas ce statut a OFFLINE
lorsque le heartbeat est vieux et ne cree aucun historique de panne.

La liste ajoute `as_of` (heure du calcul) et `heartbeat_timeout_seconds`. Chaque Fog expose
`heartbeat_age_seconds` et `heartbeat_stale` : vrai lorsque l'age depasse strictement le
timeout configure. Sans heartbeat, ces deux valeurs restent NULL. Un age negatif indique
une date producteur future, donc un possible decalage d'horloge ; il n'est pas ramene a zero.
Un vieux etat ONLINE peut ainsi etre affiche avec `heartbeat_stale=true`.
La supervision persistante de joignabilite est realisee par le worker distinct de
l'etape 7. Les KPI de disponibilite restent indisponibles sans preuves suffisantes.
Les references d'environnement et endpoints internes du catalogue ne sont pas exposes.

## Erreurs et compatibilite

- 404 : detail inconnu ou machine connue sans mesure, avec un objet Problem au premier niveau
  (`type`, `title`, `status`, `detail`, `instance`).
- 422 : parametre / enum / UUID invalide, borne incorrecte ou tri non autorise ; format FastAPI
  existant avec une liste `detail`. Les erreurs sont detectees avant la requete SQL.
- 503 : lecture PostgreSQL indisponible, Problem sans SQL, mot de passe ni URL de connexion.

Le succes des lectures existantes conserve ses champs ; la derniere mesure expose maintenant
aussi son id, message_id, received_at, pression, puissance et frequence. Les details manquants
utilisent desormais le Problem annonce dans le contrat, au lieu de l'ancien wrapper `detail`.
Les tris et zones auparavant ignores ou non verifies sont controles et peuvent retourner 422.
Les erreurs et regles de l'ingestion restent celles de
[HTTP_INGESTION.md](HTTP_INGESTION.md).

## Essai local sous PowerShell

Depuis `mp3-cloud`, lancer l'API locale :

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Ou utiliser l'API Docker, une fois migration et catalogue prepares :

```powershell
docker compose up -d --build api
```

Ces deux lancements utilisent le meme port par defaut : choisir un seul mode.
Dans un autre terminal :

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/machines?zone=A&limit=2&sort=-machine_id'
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/measurements?machine_id=M01&sort=-timestamp'
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/predictions?zone=A&anomaly=true'
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/alerts?status=OPEN&severity=CRITICAL'
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/fog/nodes'
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/tasks/events?time_field=received_at&sort=received_at'
```

Une base contenant seulement les catalogues renvoie des historiques vides. Pour injecter
volontairement des donnees de demonstration, suivre
[GUIDE_AUTONOMIE_MP3.md](../../GUIDE_AUTONOMIE_MP3.md). Les fixtures synthetiques ne prouvent
pas que les trois environnements Fog reels fonctionnent.

## Verifications et entretien du contrat

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest --mqtt
.\.venv\Scripts\python.exe scripts/check_contract.py
.\.venv\Scripts\python.exe -m scripts.export_openapi --check
docker compose config --quiet
```

Apres une modification de lecture, regenerer le contrat avec
`python -m scripts.export_openapi`. Il reste en OpenAPI 3.0.3 et est valide par
openapi-spec-validator. Les GET implementes et schemas accessibles sont synchronises
avec FastAPI (3.1 au runtime). Les operations futures restent presentes avec
`x-implementation-status: planned`, pour distinguer contrat livre et feuille de route.

Verification complete le 7 novembre 2026 : 247 tests reussis avec --mqtt, Ruff valide,
11 fixtures conformes, contrat synchronise et Compose valide. Un avertissement de
deprecation Starlette / AnyIO deja present reste sans echec de test.

L'image API Python 3.12 a ete construite et demarree dans Compose. Les 13 GET ont ete
verifies par HTTP sur le port 8000, avec leurs succes ou 404 attendus sur une base sans
mesures ; les parametres invalides donnent 422 et Swagger repond. La base de travail
conserve 12 machines, 3 Fog et zero ligne dans les sept tables d'observations / taches / KPI.
Aucune base ou ressource MQTT jetable ne reste apres les tests.

Les tests PostgreSQL verifient les huit collections, leurs pages, filtres et tris, les
dates egales, les valeurs NULL, les migrations de taches et le parcours HTTP ecriture ->
lecture depuis une autre connexion. Les reponses sont aussi validees avec les schemas
OpenAPI 3.0 publies. Les tests locaux couvrent les parametres rejetes avant SQL, les erreurs
de base sans fuite de details et la synchronisation du contrat. Toutes les donnees de test
restent dans des bases et brokers jetables ; aucune mesure n'est ajoutee a `fog_cloud`.

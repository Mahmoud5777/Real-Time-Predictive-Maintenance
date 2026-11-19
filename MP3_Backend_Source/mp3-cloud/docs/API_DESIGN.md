# MP3 - Decisions de conception backend

## Pourquoi une double ingestion MQTT + HTTP

Le contrat d equipe fait circuler les donnees en MQTT. Si je n accepte que du HTTP, je
force MP2 a ecrire un client Cloud : ca casse son design et rend mon module dependant de son
planning. Si je n accepte que du MQTT, je ne peux ni seed ni tester seul.

**Decision** : `app/ingest/worker.py` (MQTT, chemin principal) et `POST /api/v1/ingest/batch`
(HTTP, secours + seed + tests) partagent le **mem**e pipeline `app/services/ingest.py`.
Un seul code de validation/dedup = pas de divergence possible entre les deux transports.

## Pourquoi la deduplication est une contrainte de base

MQTT QoS 1 garantit *au moins une fois* : les retransmissions sont possibles et doivent
etre gerees. Un controle applicatif (« ai-je deja vu cet id ? ») seul laisse une course
sous concurrence : deux insertions paralleles peuvent passer le test. La contrainte unique
par type et `INSERT ... ON CONFLICT (message_id) DO NOTHING` arbitrent atomiquement.
Le contenu est ensuite compare : identique = doublon, different = conflit rejete.

Le bilan HTTP compte les doublons depuis l'etape 3. Le worker MQTT expose depuis l'etape 4
ses compteurs d'ingestion sur le port 8001 ; les compteurs ne prouvent pas seuls toutes les
formes de coherence de donnees. Le pipeline est dans [HTTP_INGESTION.md](HTTP_INGESTION.md)
et la reprise MQTT dans [MQTT_INGESTION.md](MQTT_INGESTION.md).

## Pourquoi les KPI sont pre-calculés

Un endpoint qui agreege 1 M lignes par requete ne tient pas le critere « query performance »
et fait souffrir le dashboard. Au jalon 6, les jobs periodiques ecriront dans `kpi_records` ;
l'API lit cette table indexee depuis l'etape 6. Le worker distinct analytics effectue
un refresh transactionnel periodique des heures terminees. Les formules, perimetres,
limites et commandes sont dans [KPI_FORMULAS.md](KPI_FORMULAS.md).

## Pourquoi le partitionnement et la purge sont prevus

12 machines x 1 Hz = ~1,04 M lignes/jour. Apres 3 jours de demo, une requete d historique scanne
des millions de lignes. Le jalon de performance devra mesurer le besoin et definir une
strategie compatible avec l'unicite globale des messages. Les tables actuelles sont indexees
mais non partitionnees ; aucune purge automatique n'est active.

## Convention temporelle

Base `timestamptz`, payloads ISO-8601 avec `Z`, refus explicite des timestamps naifs (`WrapValidator`).
Sans cette durete, trois conteneurs a trois fuseaux produisent des KPI silencieusement faux.

## Erreurs normalisees

Les erreurs 404 / 503 des lectures utilisent un Problem au premier niveau
(`type/title/status/detail/instance`). Les erreurs 422 de parametres conservent le format
FastAPI avec une liste `detail`. Les erreurs de l'ingestion gardent leur contrat existant.
Ces distinctions sont explicites dans OpenAPI pour le gestionnaire d'erreurs de MP4.

## Lectures livrees a l'etape 5

La pagination reste limit/offset (50 par defaut, maximum 1000) et les tris sont limites aux
champs annonces, avec departage par cle primaire. Les filtres temporels sont inclusifs et UTC.
Les zones de machines et Fog executants sont distinctes ; les taches gardent leur origine.
Un vieux heartbeat est indique par heartbeat_stale sans fabriquer une panne persistante.
Le guide [READ_API.md](READ_API.md) explique les limites de concurrence, les dates inconnues
et la synchronisation des schemas publies avec FastAPI.

## Lectures analytics de l'etape 6

Les lectures analytics utilisent des bornes horaires UTC [from, to), avec to exclusif,
contrairement aux filtres inclusifs d'observations brutes. Elles consultent le cache,
sans lancer de calcul dans une requete HTTP. Les heures et effectifs restent distincts.
La comparaison de modeles porte sur des distributions observees, sans labels de precision.

## Ce que je refuse volontairement

- Le calcul temps reel critique : si mon API tombe, l usine doit continuer a alerter (responsabilite MP2).
- L entree directe du dashboard dans PostgreSQL : ca detruit la frontiere et rend tout test impossible.
